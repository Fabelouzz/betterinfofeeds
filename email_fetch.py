"""
Gmail API integration for fetching newsletter emails
"""

import os
import pickle
import base64
import email
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from sqlalchemy.exc import IntegrityError
from loguru import logger
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import (
    GMAIL_CREDENTIALS_PATH,
    GMAIL_TOKEN_PATH,
    GMAIL_SCOPES,
    EMAIL_SOURCES,
    EMAIL_FETCH_INTERVAL_MINUTES,
    EMAIL_FETCH_ALL_NEWSLETTERS,
    EMAIL_FETCH_DAYS_BACK,
)
from models import Item, get_db_session

# Set up logging
logger.add("email_fetch.log", rotation="1 day", retention="7 days", level="INFO")


class GmailFetcher:
    """Handles Gmail API authentication and email fetching"""

    def __init__(self):
        self.service = None
        self.scheduler = None
        self.authenticated = False

    def authenticate(self):
        """
        Authenticate with Gmail API using OAuth2

        Returns:
            bool: True if authentication successful
        """
        creds = None

        # Load existing token if available
        if os.path.exists(GMAIL_TOKEN_PATH):
            with open(GMAIL_TOKEN_PATH, "rb") as token:
                creds = pickle.load(token)

        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Gmail credentials refreshed")
                except Exception as e:
                    logger.error(f"Failed to refresh credentials: {e}")
                    creds = None

            if not creds:
                if not os.path.exists(GMAIL_CREDENTIALS_PATH):
                    logger.error(
                        f"Gmail credentials file not found: {GMAIL_CREDENTIALS_PATH}"
                    )
                    logger.error(
                        "Please download credentials.json from Google Cloud Console"
                    )
                    return False

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        GMAIL_CREDENTIALS_PATH, GMAIL_SCOPES
                    )

                    print("\n" + "=" * 60)
                    print("GMAIL AUTHENTICATION REQUIRED")
                    print("=" * 60)
                    print("1. A browser will open with Google's authorization page")
                    print("2. Sign in with: betterinfofeeds@gmail.com")
                    print("3. Grant permission to read Gmail")
                    print("4. If localhost fails, manually copy the code")
                    print("=" * 60 + "\n")

                    # Try local server first, but with better error handling
                    try:
                        creds = flow.run_local_server(port=0, open_browser=True)
                        logger.info("Gmail authentication completed via local server")
                    except Exception as local_error:
                        print(f"Local server failed: {local_error}")
                        print("\nTrying manual authentication...")
                        print("Please go to this URL and authorize the application:")

                        # Get the authorization URL manually
                        auth_url, _ = flow.authorization_url(prompt="consent")
                        print(f"\n{auth_url}\n")

                        # Get the authorization code from user
                        auth_code = input("Enter the authorization code: ").strip()
                        flow.fetch_token(code=auth_code)
                        creds = flow.credentials
                        logger.info("Gmail authentication completed via manual flow")

                except Exception as e:
                    logger.error(f"Failed to authenticate with Gmail: {e}")
                    print(f"\nAuthentication failed: {e}")
                    print("Please make sure you:")
                    print("1. Sign in with betterinfofeeds@gmail.com")
                    print("2. Grant all requested permissions")
                    print("3. Copy the full authorization code if using manual method")
                    return False

            # Save the credentials for the next run
            with open(GMAIL_TOKEN_PATH, "wb") as token:
                pickle.dump(creds, token)

        try:
            self.service = build("gmail", "v1", credentials=creds)
            self.authenticated = True
            logger.info("Gmail service initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to build Gmail service: {e}")
            return False

    def search_emails(self, query: str, max_results: int = 50) -> List[Dict]:
        """
        Search for emails matching the given query

        Args:
            query (str): Gmail search query
            max_results (int): Maximum number of results to return

        Returns:
            List[Dict]: List of email message metadata
        """
        if not self.authenticated:
            logger.error("Gmail not authenticated. Call authenticate() first.")
            return []

        try:
            # Search for messages
            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )

            messages = results.get("messages", [])
            logger.info(f"Found {len(messages)} emails matching query: {query}")
            return messages

        except HttpError as e:
            logger.error(f"Gmail API error searching emails: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error searching emails: {e}")
            return []

    def get_message_details(self, message_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific email message

        Args:
            message_id (str): Gmail message ID

        Returns:
            Optional[Dict]: Email message details or None if error
        """
        if not self.authenticated:
            return None

        try:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            return message
        except HttpError as e:
            logger.error(f"Gmail API error getting message {message_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting message {message_id}: {e}")
            return None

    def parse_email_content(self, message: Dict) -> Dict:
        """
        Parse email message to extract relevant content

        Args:
            message (Dict): Gmail message object

        Returns:
            Dict: Parsed email data
        """
        # Extract headers
        headers = {h["name"]: h["value"] for h in message["payload"].get("headers", [])}

        subject = headers.get("Subject", "No Subject")
        sender = headers.get("From", "Unknown Sender")
        date_str = headers.get("Date", "")

        # Parse date
        try:
            # Try to parse the date from the email header
            from email.utils import parsedate_to_datetime

            published = parsedate_to_datetime(date_str)
        except:
            # Fallback to message internal date
            internal_date = int(message.get("internalDate", 0)) / 1000
            published = (
                datetime.fromtimestamp(internal_date)
                if internal_date
                else datetime.utcnow()
            )

        # Extract body content
        body = self._extract_email_body(message["payload"])

        # Create a local email link that can be handled by our app
        message_id = message["id"]
        link = f"local://email/{message_id}"  # Use local protocol for internal handling

        return {
            "title": subject,
            "link": link,
            "published": published,
            "summary": body if body else "",  # Store full email content
            "source": "email",
            "sender": sender,
            "message_id": message_id,  # Store message ID for reference
        }

    def _extract_email_body(self, payload: Dict) -> str:
        """
        Extract text content from email payload with better formatting

        Args:
            payload (Dict): Email payload from Gmail API

        Returns:
            str: Extracted and formatted text content
        """
        body = ""
        html_body = ""

        if "parts" in payload:
            # Multi-part email - prefer plain text, fallback to HTML
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part["body"].get("data", "")
                    if data:
                        body += base64.urlsafe_b64decode(data).decode(
                            "utf-8", errors="ignore"
                        )
                elif part["mimeType"] == "text/html":
                    data = part["body"].get("data", "")
                    if data:
                        html_body += base64.urlsafe_b64decode(data).decode(
                            "utf-8", errors="ignore"
                        )
        else:
            # Single part email
            if payload["mimeType"] in ["text/plain", "text/html"]:
                data = payload["body"].get("data", "")
                if data:
                    content = base64.urlsafe_b64decode(data).decode(
                        "utf-8", errors="ignore"
                    )
                    if payload["mimeType"] == "text/html":
                        html_body = content
                    else:
                        body = content

        # Use plain text if available, otherwise process HTML
        if body:
            final_body = body
        elif html_body:
            final_body = self._html_to_text(html_body)
        else:
            final_body = ""

        return final_body.strip()

    def _html_to_text(self, html_content: str) -> str:
        """
        Convert HTML content to clean, readable text using BeautifulSoup

        Args:
            html_content (str): HTML content

        Returns:
            str: Clean, well-formatted text content
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            # Fallback to basic text if BeautifulSoup not available
            import re

            text = re.sub(r"<[^>]+>", "", html_content)
            return text.strip()

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove unwanted elements completely
        unwanted_tags = ["script", "style", "meta", "link", "head", "title"]
        for tag in unwanted_tags:
            for element in soup.find_all(tag):
                element.decompose()

        # Remove tracking images and pixels
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if any(
                track in src.lower() for track in ["tracking", "pixel", "beacon", "1x1"]
            ):
                img.decompose()
            elif img.get("width") == "1" or img.get("height") == "1":
                img.decompose()

        # Remove or clean up links
        for link in soup.find_all("a"):
            href = link.get("href", "")
            text = link.get_text().strip()

            # Remove tracking and unsubscribe links
            if any(
                skip in href.lower()
                for skip in ["tracking", "pixel", "beacon", "unsubscribe"]
            ):
                link.decompose()
                continue
            elif any(
                skip in text.lower()
                for skip in ["view in browser", "view image", "unsubscribe"]
            ):
                link.decompose()
                continue

            # Clean up long tracking URLs
            if len(href) > 100 and ("beehiiv" in href or "mail" in href):
                domain = self._extract_domain(href)
                if text and len(text) > 3:
                    link.replace_with(f"{text} [{domain}]")
                else:
                    link.replace_with(f"[{domain}]")
            elif text:
                # Keep meaningful link text
                link.replace_with(text)
            else:
                link.decompose()

        # Convert headings to markdown
        for i in range(1, 7):
            for heading in soup.find_all(f"h{i}"):
                heading.replace_with(
                    f"\n{'#' * min(i, 4)} {heading.get_text().strip()}\n\n"
                )

        # Handle lists
        for ul in soup.find_all(["ul", "ol"]):
            items = []
            for li in ul.find_all("li"):
                items.append(f"• {li.get_text().strip()}")
            ul.replace_with("\n" + "\n".join(items) + "\n")

        # Handle paragraphs and breaks
        for p in soup.find_all("p"):
            p.replace_with(f"\n{p.get_text().strip()}\n")

        for br in soup.find_all("br"):
            br.replace_with("\n")

        # Handle bold and italic
        for strong in soup.find_all(["strong", "b"]):
            strong.replace_with(f"**{strong.get_text().strip()}**")

        for em in soup.find_all(["em", "i"]):
            em.replace_with(f"*{em.get_text().strip()}*")

        # Get final text
        text = soup.get_text()

        # Clean up whitespace
        import re

        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)  # Max 2 consecutive newlines
        text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces to single space
        text = re.sub(r"^\s+|\s+$", "", text, flags=re.MULTILINE)  # Trim lines

        # Remove remaining newsletter cruft more aggressively
        lines = text.split("\n")
        clean_lines = []
        for line in lines:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Skip lines with newsletter cruft (much more aggressive)
            if any(
                skip in line.lower()
                for skip in [
                    "view in browser",
                    "view image:",
                    "view image",
                    "follow image link:",
                    "follow image link",
                    "unsubscribe",
                    "forwarded this email",
                    "you received this email",
                    "caption:",
                    "download your kit here",
                    "click here",
                    "read more",
                    "beehiiv.com",
                    "mail.beehiiv.com",
                    "link.mail.beehiiv.com",
                ]
            ):
                continue

            # Skip lines that are just long tracking URLs
            if line.startswith("https://") and len(line) > 100:
                continue
            if line.startswith("(https://") and len(line) > 100:
                continue

            # Skip lines that are mostly tracking URLs with minimal text
            if ("beehiiv.com" in line or "mail." in line) and len(line) > 150:
                continue

            # Skip lines that contain mostly URL-like content
            url_chars = (
                line.count("/") + line.count("=") + line.count("&") + line.count("?")
            )
            if url_chars > 10:  # Likely a tracking URL
                continue

            # Clean up any remaining long URLs within the line
            words = line.split()
            cleaned_words = []
            skip_line = False

            for word in words:
                # Remove parentheses around URLs
                word = word.strip("()")

                if word.startswith("https://") and len(word) > 50:
                    # If more than half the line is URL, skip the entire line
                    if len(word) > len(line) / 2:
                        skip_line = True
                        break
                    # Replace long URLs with just the domain
                    domain = self._extract_domain(word)
                    cleaned_words.append(f"[{domain}]")
                elif "beehiiv.com" in word or "mail.beehiiv.com" in word:
                    # Skip beehiiv tracking words entirely
                    continue
                else:
                    cleaned_words.append(word)

            if skip_line:
                continue

            cleaned_line = " ".join(cleaned_words)

            # Skip lines that are just formatting or separators
            if cleaned_line in ["----------", "======", "------", "====="]:
                continue

            # Only add lines with meaningful content (not just domains/links)
            if (
                cleaned_line
                and len(cleaned_line.replace("[", "").replace("]", "").strip()) > 10
            ):
                clean_lines.append(cleaned_line)

        return "\n".join(clean_lines).strip()

    def _extract_domain(self, url: str) -> str:
        """Extract clean domain name from URL"""
        import re

        match = re.search(r"https?://(?:www\.)?([^/]+)", url)
        if match:
            domain = match.group(1)
            # Clean up common tracking domains and subdomains
            tracking_prefixes = [
                "mail.",
                "link.",
                "click.",
                "track.",
                "go.",
                "em.",
                "newsletter.",
                "news.",
            ]

            for prefix in tracking_prefixes:
                if domain.startswith(prefix):
                    # Remove the tracking prefix
                    clean_domain = domain[len(prefix) :]
                    if clean_domain:
                        return clean_domain

            # For other tracking domains, try to get the main domain
            if any(
                track in domain
                for track in ["beehiiv", "mailchimp", "constantcontact", "sendgrid"]
            ):
                # For newsletter services, just return the service name
                if "beehiiv" in domain:
                    return "beehiiv.com"
                elif "mailchimp" in domain:
                    return "mailchimp.com"
                elif "constantcontact" in domain:
                    return "constantcontact.com"
                elif "sendgrid" in domain:
                    return "sendgrid.com"

            return domain
        return "Link"

    def fetch_newsletter_emails(self, days_back: int = None) -> List[Item]:
        """
        Fetch newsletter emails from configured sources

        Args:
            days_back (int): Number of days to look back for emails (defaults to config value)

        Returns:
            List[Item]: List of new email items added to database
        """
        if not self.authenticated:
            logger.error("Gmail not authenticated")
            return []

        if days_back is None:
            days_back = EMAIL_FETCH_DAYS_BACK

        logger.info(f"Fetching newsletter emails from last {days_back} days")
        new_items = []

        # Build search query based on configuration
        if EMAIL_FETCH_ALL_NEWSLETTERS:
            # For dedicated newsletter accounts, fetch ALL emails
            query = f"newer_than:{days_back}d"
            logger.info("Fetching ALL emails from dedicated newsletter account")
        else:
            # Filter by specific sender sources
            sender_queries = [f"from:{source}" for source in EMAIL_SOURCES]
            query = f"({' OR '.join(sender_queries)}) newer_than:{days_back}d"
            logger.info(f"Fetching emails from {len(EMAIL_SOURCES)} configured sources")

        # Search for emails
        messages = self.search_emails(query, max_results=100)

        session = get_db_session()

        try:
            for msg_summary in messages:
                try:
                    # Get full message details
                    message = self.get_message_details(msg_summary["id"])
                    if not message:
                        continue

                    # Parse email content
                    email_data = self.parse_email_content(message)

                    # Create new item
                    item = Item(
                        title=email_data["title"],
                        link=email_data["link"],
                        published=email_data["published"],
                        summary=email_data["summary"],
                        source=email_data["source"],
                    )

                    # Add to session (will fail if duplicate link exists)
                    session.add(item)
                    session.commit()

                    new_items.append(item)
                    logger.info(
                        f"Added new email: {email_data['title']} from {email_data['sender']}"
                    )

                except IntegrityError:
                    # Item already exists (duplicate link)
                    session.rollback()
                    logger.debug(f"Duplicate email skipped: {msg_summary['id']}")
                    continue

                except Exception as e:
                    session.rollback()
                    logger.error(f"Error processing email {msg_summary['id']}: {e}")
                    continue

        finally:
            session.close()

        logger.info(f"Successfully processed {len(new_items)} new emails")
        return new_items

    def start_scheduler(self):
        """Start the background scheduler for automatic email fetching"""
        if not self.authenticated:
            logger.error("Cannot start scheduler: Gmail not authenticated")
            return

        if self.scheduler and self.scheduler.running:
            logger.warning("Email scheduler already running")
            return

        self.scheduler = BackgroundScheduler()

        # Add job to fetch emails at specified interval
        self.scheduler.add_job(
            func=self.fetch_newsletter_emails,
            trigger=IntervalTrigger(minutes=EMAIL_FETCH_INTERVAL_MINUTES),
            id="email_fetch_job",
            name="Fetch Newsletter Emails",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info(
            f"Email scheduler started. Will fetch emails every {EMAIL_FETCH_INTERVAL_MINUTES} minutes"
        )

        # Run initial fetch
        self.fetch_newsletter_emails()

    def stop_scheduler(self):
        """Stop the background scheduler"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Email scheduler stopped")


# Global Gmail fetcher instance
gmail_fetcher = GmailFetcher()


def authenticate_gmail():
    """Authenticate with Gmail API"""
    return gmail_fetcher.authenticate()


def fetch_emails_now(days_back: int = 1):
    """Fetch newsletter emails immediately"""
    return gmail_fetcher.fetch_newsletter_emails(days_back)


def start_email_scheduler():
    """Start the email scheduler"""
    gmail_fetcher.start_scheduler()


def stop_email_scheduler():
    """Stop the email scheduler"""
    gmail_fetcher.stop_scheduler()


if __name__ == "__main__":
    # Test email fetching when run directly
    logger.info("Testing Gmail email fetching...")

    # Initialize database
    from models import init_database

    init_database()

    # Authenticate and fetch emails
    if authenticate_gmail():
        emails = fetch_emails_now(7)  # Look back 7 days for testing
        print(f"\nFetched {len(emails)} new emails")
        if emails:
            print("Recent emails:")
            for email_item in emails[:5]:  # Show first 5
                print(f"- {email_item.title[:60]}...")
        else:
            print("No new emails found (emails may already be in database)")
    else:
        print("Failed to authenticate with Gmail")
