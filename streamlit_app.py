"""
Streamlit frontend for RSS & Email Aggregator
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from sqlalchemy import desc, and_, or_
from sqlalchemy.orm import sessionmaker

import config
from models import Item, engine, init_database
from feeds import fetch_feeds_now, start_rss_scheduler, stop_rss_scheduler
from email_fetch import (
    authenticate_gmail,
    fetch_emails_now,
    start_email_scheduler,
    stop_email_scheduler,
)

# Configure Streamlit page
st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Initialize database
@st.cache_resource
def initialize_app():
    """Initialize database and return session factory"""
    init_database()
    return sessionmaker(bind=engine)


SessionLocal = initialize_app()


def get_db_session():
    """Get database session"""
    return SessionLocal()


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_available_sources():
    """Get list of all available sources from database"""
    session = get_db_session()
    try:
        sources = session.query(Item.source).distinct().all()
        return [source[0] for source in sources]
    finally:
        session.close()


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_sources_by_category():
    """Get sources organized by category"""
    all_sources = get_available_sources()
    categorized_sources = {}

    # First, separate email sources
    email_sources = [source for source in all_sources if source == "email"]
    non_email_sources = [source for source in all_sources if source != "email"]

    # Add email newsletters as a dedicated category
    if email_sources:
        categorized_sources["📧 Email Newsletters"] = email_sources

    # Categorize RSS feed sources
    for category, feeds in config.RSS_FEED_CATEGORIES.items():
        category_sources = [
            source for source in feeds.keys() if source in non_email_sources
        ]
        if category_sources:
            categorized_sources[category] = category_sources

    # Add uncategorized RSS sources
    categorized_sources_flat = []
    for category, sources in categorized_sources.items():
        if category != "📧 Email Newsletters":  # Don't include email in this check
            categorized_sources_flat.extend(sources)

    uncategorized = [
        source for source in non_email_sources if source not in categorized_sources_flat
    ]
    if uncategorized:
        categorized_sources["Other"] = uncategorized

    return categorized_sources


@st.cache_data(ttl=60)  # Cache for 1 minute
def get_items_count():
    """Get total count of items in database"""
    session = get_db_session()
    try:
        return session.query(Item).count()
    finally:
        session.close()


@st.cache_data(ttl=60)  # Cache for 1 minute
def get_items_count_by_category():
    """Get item counts by category"""
    session = get_db_session()
    try:
        categorized_sources = get_sources_by_category()
        category_counts = {}

        for category, sources in categorized_sources.items():
            if sources:
                count = session.query(Item).filter(Item.source.in_(sources)).count()
                category_counts[category] = count

        return category_counts
    finally:
        session.close()


def fetch_items(selected_sources=None, start_date=None, end_date=None, limit=100):
    """
    Fetch items from database with filtering

    Args:
        selected_sources (list): List of sources to filter by
        start_date (date): Start date for filtering
        end_date (date): End date for filtering
        limit (int): Maximum number of items to return

    Returns:
        list: List of Item objects
    """
    session = get_db_session()

    try:
        query = session.query(Item)

        # Filter by sources
        if selected_sources:
            query = query.filter(Item.source.in_(selected_sources))

        # Filter by date range
        if start_date:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            query = query.filter(Item.published >= start_datetime)

        if end_date:
            end_datetime = datetime.combine(end_date, datetime.max.time())
            query = query.filter(Item.published <= end_datetime)

        # Order by published date (newest first) and limit results
        items = query.order_by(desc(Item.published)).limit(limit).all()

        return items

    finally:
        session.close()


def display_item(item):
    """Display a single news/email item"""
    # Create columns for layout
    col1, col2 = st.columns([3, 1])

    with col1:
        # Add email indicator for newsletter items
        title_prefix = "📧 " if item.source == "email" else ""

        # For emails, don't make title clickable to Gmail - display as text
        if item.source == "email":
            st.markdown(f"### {title_prefix}{item.title}")
        else:
            # For RSS feeds, keep the clickable link
            st.markdown(f"### {title_prefix}[{item.title}]({item.link})")

        # Display content differently for emails vs RSS
        if item.source == "email" and item.summary and item.summary.strip():
            # For emails, create a meaningful preview
            content = item.summary.strip()

            # Create preview by taking first few meaningful lines
            preview_lines = []
            lines = content.split("\n")
            char_count = 0

            for line in lines:
                line = line.strip()
                if (
                    line
                    and not line.startswith("#")
                    and not line.startswith("View")
                    and char_count < 400
                ):
                    preview_lines.append(line)
                    char_count += len(line)
                    if len(preview_lines) >= 3:  # Max 3 lines in preview
                        break

            preview = "\n\n".join(preview_lines)
            if preview:
                st.write("**Preview:**")
                st.markdown(preview)

            # Add expandable full content with proper markdown rendering
            if len(content) > 600:  # Only show expander for longer emails
                with st.expander("📧 View Full Email Content", expanded=False):
                    st.markdown(content)
            else:
                # For shorter emails, show full content directly
                st.write("**Full Content:**")
                st.markdown(content)

        elif item.summary and item.summary.strip():
            # For RSS items, show summary as before
            summary = (
                item.summary[:300] + "..." if len(item.summary) > 300 else item.summary
            )
            st.write(summary)

    with col2:
        # Display metadata with special styling for emails
        source_display = (
            "📧 Email Newsletter" if item.source == "email" else item.source
        )
        st.write(f"**Source:** {source_display}")
        st.write(f"**Published:** {item.published.strftime('%Y-%m-%d %H:%M')}")

        # For RSS items, add a "Read More" button
        if (
            item.source != "email"
            and item.link
            and not item.link.startswith("local://")
        ):
            st.link_button("🔗 Read More", item.link, help="Open full article")

    st.divider()


def main():
    """Main Streamlit application"""

    # App header
    st.title("📰 " + config.APP_TITLE)
    st.markdown(config.APP_DESCRIPTION)

    # Create main tabs for different views
    tab1, tab2 = st.tabs(["📊 Browse by Category", "🔍 All Sources"])

    with tab1:
        st.subheader("Browse News by Category")

        # Get categorized sources
        categorized_sources = get_sources_by_category()
        category_counts = get_items_count_by_category()

        if not categorized_sources:
            st.info("👋 No categories available yet. Fetch some data first!")
            return

        # Create category selection
        selected_category = st.selectbox(
            "Select a Category",
            options=list(categorized_sources.keys()),
            help="Choose a news category to browse",
        )

        if selected_category:
            # Show category info
            category_sources = categorized_sources[selected_category]
            category_count = category_counts.get(selected_category, 0)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Sources in Category", len(category_sources))
            with col2:
                st.metric("Total Articles", category_count)
            with col3:
                if category_count > 0:
                    avg_per_source = round(category_count / len(category_sources), 1)
                    st.metric("Avg per Source", avg_per_source)

            # Source selection within category
            selected_sources_in_category = st.multiselect(
                f"Select Sources from {selected_category}",
                options=category_sources,
                default=category_sources,
                help="Choose specific sources within this category",
            )

            # Date range filter
            st.subheader("Date Range")
            col1, col2 = st.columns(2)

            with col1:
                start_date = st.date_input(
                    "Start Date",
                    value=date.today() - timedelta(days=7),
                    help="Show items published on or after this date",
                    key="category_start_date",
                )

            with col2:
                end_date = st.date_input(
                    "End Date",
                    value=date.today(),
                    help="Show items published on or before this date",
                    key="category_end_date",
                )

            # Validate date range
            if start_date > end_date:
                st.error("Start date must be before end date")
                return

            # Fetch and display items for selected category
            if selected_sources_in_category:
                with st.spinner("Loading articles..."):
                    items = fetch_items(
                        selected_sources=selected_sources_in_category,
                        start_date=start_date,
                        end_date=end_date,
                        limit=config.MAX_ITEMS_PER_PAGE,
                    )

                if items:
                    st.subheader(
                        f"📋 {len(items)} Articles Found in {selected_category}"
                    )

                    # Display source breakdown
                    source_counts = {}
                    for item in items:
                        source_counts[item.source] = (
                            source_counts.get(item.source, 0) + 1
                        )

                    with st.expander("View source breakdown"):
                        cols = st.columns(min(3, len(source_counts)))
                        for i, (source, count) in enumerate(source_counts.items()):
                            with cols[i % len(cols)]:
                                st.metric(source, count)

                    # Display items
                    for item in items:
                        display_item(item)
                else:
                    st.info(
                        f"No articles found in {selected_category} for the selected date range."
                    )

    with tab2:
        st.subheader("All Sources View")

        # Sidebar filters
        with st.sidebar:
            st.title("Filters & Controls")

            # Source filter
            available_sources = get_available_sources()
            if available_sources:
                # Always include email in defaults, plus first few RSS sources
                email_sources = [s for s in available_sources if s == "email"]
                rss_sources = [s for s in available_sources if s != "email"]
                default_sources = (
                    email_sources + rss_sources[:4]
                )  # Email + 4 RSS sources

                selected_sources = st.multiselect(
                    "Select Sources",
                    options=available_sources,
                    default=default_sources,
                    help="Choose which sources to display (📧 emails always included by default)",
                )
            else:
                selected_sources = []
                st.warning("No sources available. Fetch some data first!")

            # Date range filter
            st.subheader("Date Range")

            # Default to last 7 days
            default_start = date.today() - timedelta(days=7)
            default_end = date.today()

            start_date = st.date_input(
                "Start Date",
                value=default_start,
                help="Show items published on or after this date",
                key="all_sources_start_date",
            )

            end_date = st.date_input(
                "End Date",
                value=default_end,
                help="Show items published on or before this date",
                key="all_sources_end_date",
            )

            # Validate date range
            if start_date > end_date:
                st.error("Start date must be before end date")
                return

            # Manual fetch controls
            st.subheader("Manual Fetch")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Fetch RSS", help="Manually fetch all RSS feeds"):
                    with st.spinner("Fetching RSS feeds..."):
                        results = fetch_feeds_now()
                        total_new = sum(r.get("new_items", 0) for r in results.values())
                        st.success(f"Fetched {total_new} new RSS items")
                        st.cache_data.clear()  # Clear cache to refresh data

            with col2:
                if st.button("Fetch Email", help="Manually fetch emails"):
                    with st.spinner("Fetching emails..."):
                        try:
                            if authenticate_gmail():
                                emails = fetch_emails_now(1)  # Last 1 day
                                st.success(f"Fetched {len(emails)} new emails")
                                st.cache_data.clear()  # Clear cache to refresh data
                            else:
                                st.error("Gmail authentication failed")
                        except Exception as e:
                            st.error(f"Email fetch error: {e}")

            # App statistics
            st.subheader("Statistics")
            total_items = get_items_count()
            st.metric("Total Items", total_items)

            # Category breakdown
            if categorized_sources := get_sources_by_category():
                category_counts = get_items_count_by_category()
                with st.expander("Category Breakdown"):
                    for category, count in category_counts.items():
                        st.write(f"**{category}**: {count} items")

        # Main content area for All Sources view
        if not available_sources:
            st.info(
                "👋 Welcome! Use the manual fetch buttons in the sidebar to get started, or wait for automatic fetching to begin."
            )
            st.markdown("""
            ### Getting Started
            
            1. **RSS Feeds**: Click "Fetch RSS" to immediately fetch from all configured news sources
            2. **Email**: Click "Fetch Email" to get newsletter emails (requires Gmail setup)
            3. **Automatic Updates**: The app will automatically fetch new content every 10 minutes (RSS) and 30 minutes (email)
            
            ### Categories Available
            - **Finance & Business**: Market news, economic analysis, crypto updates
            - **World & Geopolitics**: International news, politics, current events  
            - **AI & Technology**: Tech industry news, innovations, startup coverage
            - **AI Specific**: Dedicated AI research, developments, and analysis
            
            ### Gmail Setup
            To enable email fetching, you'll need to:
            1. Create a Google Cloud Console project
            2. Enable the Gmail API
            3. Download `credentials.json` and place it in the app directory
            4. Run the authentication flow (happens automatically on first email fetch)
            """)
            return

        # Fetch and display items for All Sources view
        with st.spinner("Loading items..."):
            items = fetch_items(
                selected_sources=selected_sources,
                start_date=start_date,
                end_date=end_date,
                limit=config.MAX_ITEMS_PER_PAGE,
            )

        if not items:
            st.info(
                "No items found matching your filters. Try adjusting the date range or sources."
            )
            return

        # Display results summary
        st.subheader(f"📋 {len(items)} Items Found")

        if len(items) == config.MAX_ITEMS_PER_PAGE:
            st.warning(
                f"Showing first {config.MAX_ITEMS_PER_PAGE} items. Use filters to narrow results."
            )

        # Group by source for summary
        source_counts = {}
        for item in items:
            source_counts[item.source] = source_counts.get(item.source, 0) + 1

        # Display source breakdown
        with st.expander("View source breakdown"):
            cols = st.columns(min(4, len(source_counts)))
            for i, (source, count) in enumerate(source_counts.items()):
                with cols[i % len(cols)]:
                    st.metric(source, count)

        # Display items
        for item in items:
            display_item(item)

    # Footer
    st.markdown("---")
    st.markdown(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")


if __name__ == "__main__":
    main()
