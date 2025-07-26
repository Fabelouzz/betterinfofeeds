"""
Main application entry point for RSS & Email Aggregator
Coordinates background scheduling and provides CLI interface
"""

import os
import sys
import time
import signal
import argparse
from datetime import datetime
from loguru import logger

# Import application modules
from models import init_database
from feeds import start_rss_scheduler, stop_rss_scheduler, fetch_feeds_now
from email_fetch import (
    authenticate_gmail,
    start_email_scheduler,
    stop_email_scheduler,
    fetch_emails_now,
)
from rss_export import generate_rss_feed, get_rss_feed_info
import config

# Configure main application logging
logger.add("main.log", rotation="1 day", retention="7 days", level=config.LOG_LEVEL)


class AggregatorApp:
    """Main application coordinator"""

    def __init__(self):
        self.running = False
        self.gmail_authenticated = False

    def initialize(self):
        """Initialize the application"""
        logger.info("Initializing RSS & Email Aggregator...")

        # Initialize database
        try:
            init_database()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False

        # Try to authenticate Gmail (optional)
        try:
            self.gmail_authenticated = authenticate_gmail()
            if self.gmail_authenticated:
                logger.info("Gmail authentication successful")
            else:
                logger.warning("Gmail authentication failed - email features disabled")
        except Exception as e:
            logger.warning(
                f"Gmail authentication error: {e} - continuing without email features"
            )
            self.gmail_authenticated = False

        return True

    def start_schedulers(self):
        """Start background schedulers"""
        logger.info("Starting background schedulers...")

        # Start RSS scheduler
        try:
            start_rss_scheduler()
            logger.info(
                f"RSS scheduler started (interval: {config.FETCH_INTERVAL_MINUTES} minutes)"
            )
        except Exception as e:
            logger.error(f"Failed to start RSS scheduler: {e}")

        # Start email scheduler if authenticated
        if self.gmail_authenticated:
            try:
                start_email_scheduler()
                logger.info(
                    f"Email scheduler started (interval: {config.EMAIL_FETCH_INTERVAL_MINUTES} minutes)"
                )
            except Exception as e:
                logger.error(f"Failed to start email scheduler: {e}")
        else:
            logger.info("Email scheduler not started (Gmail not authenticated)")

    def stop_schedulers(self):
        """Stop background schedulers"""
        logger.info("Stopping background schedulers...")

        try:
            stop_rss_scheduler()
            logger.info("RSS scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping RSS scheduler: {e}")

        if self.gmail_authenticated:
            try:
                stop_email_scheduler()
                logger.info("Email scheduler stopped")
            except Exception as e:
                logger.error(f"Error stopping email scheduler: {e}")

    def run_daemon(self):
        """Run the application in daemon mode with background scheduling"""
        if not self.initialize():
            logger.error("Failed to initialize application")
            return False

        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start schedulers
        self.start_schedulers()
        self.running = True

        logger.info("Application running in daemon mode. Press Ctrl+C to stop.")

        try:
            # Keep the main thread alive
            while self.running:
                time.sleep(10)

                # Optionally generate RSS feed periodically
                if os.path.exists("db.sqlite3"):  # Only if we have data
                    try:
                        generate_rss_feed()
                    except Exception as e:
                        logger.error(f"Error generating RSS feed: {e}")

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")

        finally:
            self.stop_schedulers()
            logger.info("Application shutdown complete")

        return True

    def run_once(self, include_email=True):
        """Run fetching once and exit"""
        if not self.initialize():
            return False

        logger.info("Running one-time fetch...")

        # Fetch RSS feeds
        try:
            results = fetch_feeds_now()
            total_rss = sum(r.get("new_items", 0) for r in results.values())
            logger.info(f"RSS fetch completed: {total_rss} new items")

            for source, result in results.items():
                if result["success"]:
                    print(f"✓ {source}: {result['new_items']} new items")
                else:
                    print(f"✗ {source}: {result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.error(f"RSS fetch failed: {e}")

        # Fetch emails if requested and authenticated
        if include_email and self.gmail_authenticated:
            try:
                emails = fetch_emails_now(1)  # Last 1 day
                logger.info(f"Email fetch completed: {len(emails)} new items")
                print(f"✓ Email: {len(emails)} new items")
            except Exception as e:
                logger.error(f"Email fetch failed: {e}")
                print(f"✗ Email: {e}")

        # Generate RSS feed
        try:
            generate_rss_feed()
            print(f"✓ RSS feed generated: {config.RSS_OUTPUT_FILE}")
        except Exception as e:
            logger.error(f"RSS generation failed: {e}")
            print(f"✗ RSS generation failed: {e}")

        return True


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="RSS & Email Aggregator")
    parser.add_argument(
        "--mode",
        choices=["daemon", "once", "streamlit"],
        default="streamlit",
        help="Run mode: daemon (background), once (single fetch), or streamlit (web UI)",
    )
    parser.add_argument(
        "--no-email", action="store_true", help="Skip email fetching (RSS only)"
    )
    parser.add_argument(
        "--info", action="store_true", help="Show application and feed information"
    )

    args = parser.parse_args()

    app = AggregatorApp()

    if args.info:
        # Show application info
        print(f"\n{config.APP_TITLE}")
        print("=" * len(config.APP_TITLE))
        print(f"Description: {config.APP_DESCRIPTION}")
        print(f"Database: {config.DATABASE_URL}")
        print(f"RSS Sources: {len(config.RSS_FEEDS)}")
        print(f"Email Sources: {len(config.EMAIL_SOURCES)}")
        print(f"RSS Interval: {config.FETCH_INTERVAL_MINUTES} minutes")
        print(f"Email Interval: {config.EMAIL_FETCH_INTERVAL_MINUTES} minutes")

        # Show feed info if database exists
        if os.path.exists("db.sqlite3"):
            try:
                info = get_rss_feed_info()
                print(f"\nDatabase Statistics:")
                print(f"Total Items: {info['total_items']}")
                print(f"Available Sources: {', '.join(info['sources'])}")
                if info["latest_item"]:
                    print(f"Latest Item: {info['latest_item'].title[:50]}...")
                    print(f"Published: {info['latest_item'].published}")
            except Exception as e:
                print(f"Error reading database: {e}")
        else:
            print("\nNo database found. Run the application to fetch data.")

        return

    if args.mode == "daemon":
        print("Starting in daemon mode...")
        success = app.run_daemon()
        sys.exit(0 if success else 1)

    elif args.mode == "once":
        print("Running one-time fetch...")
        success = app.run_once(include_email=not args.no_email)
        sys.exit(0 if success else 1)

    elif args.mode == "streamlit":
        print("Starting Streamlit web interface...")
        print("Make sure to run: streamlit run streamlit_app.py")
        print("Or use the --mode daemon to run background schedulers only")

        # Initialize app but don't start schedulers
        if app.initialize():
            print("✓ Application initialized successfully")
            print("✓ Run 'streamlit run streamlit_app.py' to start the web interface")
        else:
            print("✗ Application initialization failed")
            sys.exit(1)


if __name__ == "__main__":
    main()
