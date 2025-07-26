"""
RSS Export functionality for generating aggregated RSS feed
"""

import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import desc
from loguru import logger

from config import RSS_OUTPUT_FILE, RSS_EXPORT_ITEM_COUNT, APP_TITLE, APP_DESCRIPTION
from models import Item, get_db_session

logger.add("rss_export.log", rotation="1 day", retention="7 days", level="INFO")


class RSSExporter:
    """Handles generation of aggregated RSS feed"""

    def __init__(self):
        # Set up Jinja2 environment
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def generate_feed_xml(self, output_path=None, item_count=None):
        """
        Generate RSS XML feed from database items

        Args:
            output_path (str): Path to save the RSS file (default: RSS_OUTPUT_FILE)
            item_count (int): Number of items to include (default: RSS_EXPORT_ITEM_COUNT)

        Returns:
            str: Generated RSS XML content
        """
        if output_path is None:
            output_path = RSS_OUTPUT_FILE

        if item_count is None:
            item_count = RSS_EXPORT_ITEM_COUNT

        logger.info(f"Generating RSS feed with {item_count} items")

        # Fetch recent items from database
        session = get_db_session()

        try:
            items = (
                session.query(Item)
                .order_by(desc(Item.published))
                .limit(item_count)
                .all()
            )

            if not items:
                logger.warning("No items found in database for RSS export")
                items = []

            # Prepare template context
            now = datetime.utcnow()

            context = {
                "channel_title": APP_TITLE,
                "channel_link": "http://localhost:8501",  # Default Streamlit URL
                "channel_description": APP_DESCRIPTION
                + f" - {len(items)} recent items",
                "last_build_date": now.strftime("%a, %d %b %Y %H:%M:%S +0000"),
                "pub_date": now.strftime("%a, %d %b %Y %H:%M:%S +0000"),
                "items": items,
            }

            # Load and render template
            template = self.env.get_template("feed.xml.j2")
            rss_content = template.render(**context)

            # Write to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(rss_content)

            logger.info(f"RSS feed generated successfully: {output_path}")
            return rss_content

        except Exception as e:
            logger.error(f"Error generating RSS feed: {e}")
            raise

        finally:
            session.close()

    def get_feed_info(self):
        """
        Get information about the current feed

        Returns:
            dict: Feed statistics and metadata
        """
        session = get_db_session()

        try:
            total_items = session.query(Item).count()

            if total_items == 0:
                return {"total_items": 0, "latest_item": None, "sources": []}

            latest_item = session.query(Item).order_by(desc(Item.published)).first()

            sources = session.query(Item.source).distinct().all()
            source_list = [source[0] for source in sources]

            return {
                "total_items": total_items,
                "latest_item": latest_item,
                "sources": source_list,
                "export_count": min(RSS_EXPORT_ITEM_COUNT, total_items),
            }

        finally:
            session.close()


# Global RSS exporter instance
rss_exporter = RSSExporter()


def generate_rss_feed(output_path=None, item_count=None):
    """
    Convenience function to generate RSS feed

    Args:
        output_path (str): Path to save the RSS file
        item_count (int): Number of items to include

    Returns:
        str: Generated RSS XML content
    """
    return rss_exporter.generate_feed_xml(output_path, item_count)


def get_rss_feed_info():
    """Get RSS feed information"""
    return rss_exporter.get_feed_info()


if __name__ == "__main__":
    # Test RSS generation when run directly
    logger.info("Testing RSS feed generation...")

    # Initialize database
    from models import init_database

    init_database()

    # Get feed info
    info = get_rss_feed_info()
    print(f"\nFeed Information:")
    print(f"Total items in database: {info['total_items']}")
    print(f"Available sources: {', '.join(info['sources'])}")
    print(f"Items to export: {info['export_count']}")

    if info["latest_item"]:
        print(f"Latest item: {info['latest_item'].title[:50]}...")
        print(f"Published: {info['latest_item'].published}")

    # Generate RSS feed
    if info["total_items"] > 0:
        try:
            rss_content = generate_rss_feed()
            print(f"\n✓ RSS feed generated: {RSS_OUTPUT_FILE}")
            print(f"Feed size: {len(rss_content)} characters")
        except Exception as e:
            print(f"✗ Error generating RSS feed: {e}")
    else:
        print("\nNo items available for RSS export. Fetch some data first.")
