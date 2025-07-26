"""
RSS Feed fetching and parsing functionality
"""

import feedparser
import requests
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from loguru import logger
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import time

from config import RSS_FEEDS, FETCH_INTERVAL_MINUTES, REQUEST_TIMEOUT
from models import Item, engine, get_db_session

# Set up logging
logger.add("feeds.log", rotation="1 day", retention="7 days", level="INFO")


class RSSFeedManager:
    """Manages RSS feed fetching, parsing, and storage"""

    def __init__(self):
        self.session_factory = sessionmaker(bind=engine)
        self.scheduler = None

    def fetch_single_feed(self, source_name, feed_url):
        """
        Fetch and parse a single RSS feed

        Args:
            source_name (str): Name of the RSS source
            feed_url (str): URL of the RSS feed

        Returns:
            list: List of new items added to database
        """
        logger.info(f"Fetching RSS feed: {source_name} ({feed_url})")
        new_items = []

        try:
            # Fetch the RSS feed with timeout
            response = requests.get(feed_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            # Parse the RSS feed
            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.warning(
                    f"Feed {source_name} may have issues: {feed.bozo_exception}"
                )

            # Get database session
            session = get_db_session()

            try:
                # Process each entry in the feed
                for entry in feed.entries:
                    try:
                        # Extract item data
                        title = entry.get("title", "No Title")
                        link = entry.get("link", "")
                        summary = entry.get("summary", entry.get("description", ""))

                        # Parse published date
                        published = datetime.utcnow()  # Default to now
                        if (
                            hasattr(entry, "published_parsed")
                            and entry.published_parsed
                        ):
                            published = datetime(*entry.published_parsed[:6])
                        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                            published = datetime(*entry.updated_parsed[:6])

                        # Skip if no link (can't deduplicate)
                        if not link:
                            logger.warning(
                                f"Skipping item without link from {source_name}: {title}"
                            )
                            continue

                        # Create new item
                        item = Item(
                            title=title,
                            link=link,
                            published=published,
                            summary=summary,
                            source=source_name,
                        )

                        # Add to session (will fail if duplicate link exists)
                        session.add(item)
                        session.commit()

                        new_items.append(item)
                        logger.info(f"Added new item: {title} from {source_name}")

                    except IntegrityError:
                        # Item already exists (duplicate link)
                        session.rollback()
                        logger.debug(
                            f"Duplicate item skipped from {source_name}: {entry.get('title', 'No Title')}"
                        )
                        continue

                    except Exception as e:
                        session.rollback()
                        logger.error(f"Error processing item from {source_name}: {e}")
                        continue

            finally:
                session.close()

            logger.info(
                f"Successfully processed {len(new_items)} new items from {source_name}"
            )
            return new_items

        except requests.RequestException as e:
            logger.error(f"Network error fetching {source_name}: {e}")
            return []

        except Exception as e:
            logger.error(f"Unexpected error fetching {source_name}: {e}")
            return []

    def fetch_all_feeds(self):
        """
        Fetch all configured RSS feeds

        Returns:
            dict: Summary of results per feed
        """
        logger.info("Starting RSS feed fetch cycle")
        results = {}
        total_new_items = 0

        for source_name, feed_url in RSS_FEEDS.items():
            try:
                new_items = self.fetch_single_feed(source_name, feed_url)
                results[source_name] = {
                    "success": True,
                    "new_items": len(new_items),
                    "items": new_items,
                }
                total_new_items += len(new_items)

                # Small delay between feeds to be respectful
                time.sleep(1)

            except Exception as e:
                logger.error(f"Failed to fetch {source_name}: {e}")
                results[source_name] = {
                    "success": False,
                    "error": str(e),
                    "new_items": 0,
                }

        logger.info(f"RSS fetch cycle completed. Total new items: {total_new_items}")
        return results

    def start_scheduler(self):
        """Start the background scheduler for automatic RSS fetching"""
        if self.scheduler and self.scheduler.running:
            logger.warning("Scheduler already running")
            return

        self.scheduler = BackgroundScheduler()

        # Add job to fetch feeds at specified interval
        self.scheduler.add_job(
            func=self.fetch_all_feeds,
            trigger=IntervalTrigger(minutes=FETCH_INTERVAL_MINUTES),
            id="rss_fetch_job",
            name="Fetch RSS Feeds",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info(
            f"RSS scheduler started. Will fetch feeds every {FETCH_INTERVAL_MINUTES} minutes"
        )

        # Run initial fetch
        self.fetch_all_feeds()

    def stop_scheduler(self):
        """Stop the background scheduler"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("RSS scheduler stopped")


# Global RSS manager instance
rss_manager = RSSFeedManager()


def fetch_feeds_now():
    """Convenience function to fetch all feeds immediately"""
    return rss_manager.fetch_all_feeds()


def start_rss_scheduler():
    """Start the RSS feed scheduler"""
    rss_manager.start_scheduler()


def stop_rss_scheduler():
    """Stop the RSS feed scheduler"""
    rss_manager.stop_scheduler()


if __name__ == "__main__":
    # Test RSS fetching when run directly
    logger.info("Testing RSS feed fetching...")

    # Initialize database
    from models import init_database

    init_database()

    # Fetch all feeds once
    results = fetch_feeds_now()

    print("\nRSS Feed Fetch Results:")
    for source, result in results.items():
        if result["success"]:
            print(f"✓ {source}: {result['new_items']} new items")
        else:
            print(f"✗ {source}: {result['error']}")
