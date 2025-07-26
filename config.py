"""
Configuration settings for RSS & Email Aggregator
"""

import os
from pathlib import Path

# Database Configuration
DATABASE_URL = "sqlite:///db.sqlite3"

# RSS Feed Sources organized by categories
RSS_FEED_CATEGORIES = {
    "Finance & Business": {
        "Reuters Business News": "https://feeds.reuters.com/reuters/businessNews",
        "MarketWatch Top Stories": "https://feeds.marketwatch.com/marketwatch/topstories/",
        "BBC Business": "http://feeds.bbci.co.uk/news/business/rss.xml",
        "Yahoo Finance": "https://finance.yahoo.com/rss/topstories",  # Fixed URL
        "The Economist Finance": "https://www.economist.com/finance-and-economics/rss.xml",  # Fixed URL
        "Financial Times": "https://www.ft.com/rss/home/uk",
        "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "Wall Street Journal": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",  # Fixed WSJ URL
        "Bloomberg Markets": "https://feeds.bloomberg.com/markets/news.rss",
        "Seeking Alpha": "https://seekingalpha.com/rss.xml",  # Added working financial source
    },
    "World & Geopolitics": {
        "Reuters World News": "https://feeds.reuters.com/reuters/worldNews",
        "AP World News": "https://feeds.apnews.com/rss/apf-worldnews",
        "BBC World News": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "CNN International": "http://rss.cnn.com/rss/edition_world.rss",  # Fixed CNN URL
        "NPR News": "https://feeds.npr.org/1001/rss.xml",
        "Guardian World": "https://www.theguardian.com/world/rss",
        "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
        "Politico": "https://rss.politico.com/politics-news.xml",  # Added politics source
    },
    "AI & Technology": {
        "TechCrunch": "https://techcrunch.com/feed/",
        "MIT Technology Review": "https://www.technologyreview.com/feed/",
        "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
        "The Verge": "https://www.theverge.com/rss/index.xml",
        "Wired": "https://www.wired.com/feed/rss",
        "VentureBeat": "https://venturebeat.com/feed/",  # Added working tech source
        "Engadget": "https://www.engadget.com/rss.xml",  # Added Engadget
    },
    "AI Specific": {
        "MIT Tech Review AI": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
        "AI News": "https://artificialintelligence-news.com/feed/",
        "OpenAI Blog": "https://openai.com/blog/rss.xml",
        "DeepMind Blog": "https://www.deepmind.com/blog/rss.xml",  # Added DeepMind
    },
}

# Flatten all feeds for backward compatibility
RSS_FEEDS = {}
for category, feeds in RSS_FEED_CATEGORIES.items():
    RSS_FEEDS.update(feeds)

# Fetch Intervals (in minutes)
FETCH_INTERVAL_MINUTES = 10
EMAIL_FETCH_INTERVAL_MINUTES = 30

# Gmail API Configuration
GMAIL_CREDENTIALS_PATH = "credentials.json"  # Path to Google OAuth credentials file
GMAIL_TOKEN_PATH = "token.json"  # Path where access token will be stored
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Gmail Account Configuration
GMAIL_ACCOUNT = (
    "betterinfofeeds@gmail.com"  # The Gmail account to fetch newsletters from
)

# Gmail Newsletter Sources - Since this is a dedicated newsletter account,
# we'll fetch ALL emails (newsletters) and can filter by sender if needed
EMAIL_SOURCES = [
    # Common newsletter domains - add more as you subscribe to newsletters
    "noreply@",
    "newsletter@",
    "no-reply@",
    "hello@",
    "updates@",
    "news@",
    "info@",
    # Specific sources you mentioned before (keep these)
    "noreply@reuters.com",
    "noreply@apnews.com",
    "no-reply@bbc.co.uk",
    "newsletter@coindesk.com",
    "noreply@cryptopanic.com",
]

# Newsletter Email Configuration
EMAIL_FETCH_ALL_NEWSLETTERS = True  # Set to True to fetch ALL emails from the account
EMAIL_FETCH_DAYS_BACK = 7  # How many days back to look for emails on first run

# RSS Export Configuration
RSS_OUTPUT_FILE = "feed.xml"
RSS_EXPORT_ITEM_COUNT = 50  # Number of most recent items to include in aggregated feed

# Application Settings
APP_TITLE = "RSS & Email Aggregator"
APP_DESCRIPTION = "Local aggregator for RSS feeds and email newsletters"
APP_HOST = "localhost"
APP_PORT = 8501

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FILE = "aggregator.log"

# Time zone for displaying items (adjust as needed)
TIMEZONE = "UTC"

# Request timeout for RSS feeds (seconds)
REQUEST_TIMEOUT = 30

# Maximum number of items to display per page in Streamlit
MAX_ITEMS_PER_PAGE = 100
