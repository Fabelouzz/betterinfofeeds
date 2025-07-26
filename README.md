# RSS & Email Aggregator

A self-hosted Python application that aggregates RSS feeds and email newsletters into a unified Streamlit dashboard with automatic scheduling and RSS export capabilities.

## Features

- **RSS Feed Aggregation**: Automatically fetches from multiple news sources
- **Email Newsletter Integration**: Pulls newsletters from Gmail using the Gmail API
- **Interactive Dashboard**: Streamlit-based web interface with filtering capabilities
- **Automatic Scheduling**: Background processing with configurable intervals
- **RSS Export**: Generates aggregated RSS feed for external consumption
- **Deduplication**: Prevents duplicate items using unique links
- **Comprehensive Logging**: Detailed logging for monitoring and debugging

## Included News Sources

- Reuters World News
- AP Top News  
- BBC World News
- CoinDesk
- CryptoPanic

## Project Structure

```
rss_aggregator/
├── config.py           # Configuration settings
├── requirements.txt    # Python dependencies
├── models.py          # SQLAlchemy database models
├── feeds.py           # RSS feed fetching logic
├── email_fetch.py     # Gmail API integration
├── streamlit_app.py   # Streamlit web interface
├── rss_export.py      # RSS feed generation
├── main.py            # Main application entry point
├── templates/         # Jinja2 templates
│   └── feed.xml.j2    # RSS feed template
├── README.md          # This file
├── feed.xml           # Generated RSS feed (created at runtime)
└── db.sqlite3         # SQLite database (created at runtime)
```

## Installation

1. **Clone/Download** the project files to your desired directory

2. **Install Python Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Gmail API Setup** (Optional - for email features):

   a. Go to the [Google Cloud Console](https://console.cloud.google.com/)

   b. Create a new project or select an existing one

   c. Enable the Gmail API:
      - Navigate to "APIs & Services" > "Library"
      - Search for "Gmail API" and enable it

   d. Create credentials:
      - Go to "APIs & Services" > "Credentials"
      - Click "Create Credentials" > "OAuth 2.0 Client IDs"
      - Choose "Desktop application"
      - Download the JSON file and save it as `credentials.json` in the project directory

   e. Add your Gmail account to test users (if app is in development mode)

## Configuration

Edit `config.py` to customize:

- **RSS_FEEDS**: Add/remove RSS feed sources
- **EMAIL_SOURCES**: Configure email addresses to monitor
- **FETCH_INTERVAL_MINUTES**: RSS fetching interval (default: 10 minutes)
- **EMAIL_FETCH_INTERVAL_MINUTES**: Email fetching interval (default: 30 minutes)
- **RSS_EXPORT_ITEM_COUNT**: Number of items in generated RSS feed (default: 50)

## Usage

### Option 1: Streamlit Web Interface (Recommended)

Start the web interface:

```bash
streamlit run streamlit_app.py
```

The interface will be available at `http://localhost:8501`

Features:

- Filter by news sources
- Filter by date range
- Manual fetch buttons for RSS and email
- Real-time statistics
- Clickable article links

### Option 2: Command Line Interface

**Initialize and run one-time fetch**:

```bash
python main.py --mode once
```

**Run in daemon mode** (background with automatic scheduling):

```bash
python main.py --mode daemon
```

**Show application information**:

```bash
python main.py --info
```

**RSS-only mode** (skip email fetching):

```bash
python main.py --mode once --no-email
```

### Option 3: Individual Module Testing

**Test RSS fetching**:

```bash
python feeds.py
```

**Test email fetching**:

```bash
python email_fetch.py
```

**Test RSS export**:

```bash
python rss_export.py
```

## Gmail Authentication Flow

1. On first email fetch, a browser window will open
2. Sign in to your Gmail account
3. Grant permission to read emails
4. The authentication token will be saved as `token.json`
5. Subsequent runs will use the saved token

## Generated Files

- **db.sqlite3**: SQLite database with all aggregated items
- **feed.xml**: Generated RSS feed with recent items
- **token.json**: Gmail API authentication token
- ***.log**: Log files for different components

## Scheduling

The application supports automatic background scheduling:

- **RSS Feeds**: Fetched every 10 minutes (configurable)
- **Email**: Fetched every 30 minutes (configurable)
- **RSS Export**: Generated after each fetch cycle

## Filtering and Search

The Streamlit interface provides:

- **Source Filter**: Multi-select dropdown for news sources
- **Date Range**: Start and end date pickers
- **Real-time Updates**: Manual fetch buttons
- **Statistics**: Item counts per source

## RSS Export

The application generates a standard RSS 2.0 feed (`feed.xml`) that can be:

- Subscribed to in RSS readers
- Integrated with other systems
- Customized via the Jinja2 template

## Troubleshooting

### Common Issues

1. **Gmail Authentication Fails**:
   - Ensure `credentials.json` is in the project directory
   - Check that Gmail API is enabled in Google Cloud Console
   - Verify your account is added to test users

2. **RSS Feeds Not Loading**:
   - Check internet connectivity
   - Verify RSS feed URLs in `config.py`
   - Review logs in `feeds.log`

3. **Database Errors**:
   - Delete `db.sqlite3` to reset the database
   - Check file permissions
   - Review logs in `main.log`

4. **Streamlit Issues**:
   - Try refreshing the browser
   - Restart the Streamlit server
   - Check for port conflicts

### Logs

Check these log files for debugging:

- `main.log`: Main application events
- `feeds.log`: RSS feed fetching
- `email_fetch.log`: Gmail integration
- `rss_export.log`: RSS generation

## Customization

### Adding New RSS Sources

Edit `config.py`:

```python
RSS_FEEDS = {
    "Your Source Name": "https://example.com/rss",
    # ... existing sources
}
```

### Changing Email Sources

Edit `config.py`:

```python
EMAIL_SOURCES = [
    "newsletter@example.com",
    # ... existing sources
]
```

### Modifying the RSS Template

Edit `templates/feed.xml.j2` to customize the RSS output format.

### Adjusting Fetch Intervals

Edit `config.py`:

```python
FETCH_INTERVAL_MINUTES = 15        # RSS every 15 minutes
EMAIL_FETCH_INTERVAL_MINUTES = 60  # Email every hour
```

## Dependencies

- **streamlit**: Web interface framework
- **feedparser**: RSS feed parsing
- **google-api-python-client**: Gmail API access
- **sqlalchemy**: Database ORM
- **apscheduler**: Background job scheduling
- **jinja2**: Template engine for RSS generation
- **loguru**: Enhanced logging
- **requests**: HTTP client for RSS feeds

## Security Notes

- Keep `credentials.json` and `token.json` secure
- The application only requests read-only Gmail access
- All data is stored locally in SQLite
- No external services receive your data

## License

This project is open source. Use and modify as needed for your requirements.

## Support

For issues or questions:

1. Check the troubleshooting section
2. Review log files for error details
3. Verify configuration settings
4. Ensure all dependencies are installed correctly
