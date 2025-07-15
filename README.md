# MarketWatch

A Python package for scraping MarketWatch articles from the Wayback Machine. This tool allows you to extract historical financial news articles with their content, metadata, and associated data.

**Author:** Ariana Christodoulou (<ariana.chr@gmail.com>)  
**GitHub:** [https://github.com/ariana-ch/marketwatch-scrapper](https://github.com/ariana-ch/marketwatch-scrapper)

## Features

- Scrape MarketWatch articles from the Wayback Machine
- Extract article content, headlines, summaries, and metadata
- Filter articles by date range and topics (base URLs)
- Multi-threaded processing for efficient scraping
- Configurable capture limits (number of captures to keep per query date) and worker threads
- Built-in rate limiting and retry mechanisms

## Installation

### From PyPI (when published)
```bash
pip install marketwatch
```

### From source
```bash
git clone https://github.com/ariana-ch/marketwatch-scrapper.git
cd marketwatch-scrapper
pip install -e .
```

### Install via Git (recommended)
You can install the latest version directly from GitHub using pip:

```bash
pip install git+https://github.com/ariana-ch/marketwatch-scrapper.git
```

## Dependencies

- Python 3.8+
- requests
- beautifulsoup4
- pandas
- newspaper3k
- lxml[html_clean]

## Usage

### Basic Usage

```python
import datetime
from marketwatch_scrapper import MarketWatchScrapper

# Create a scrapper instance
scrapper = MarketWatchScrapper(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31),
    max_workers=3,
    no_of_captures=10
)

# Download articles
articles = scrapper.download()

# Print results
print(f"Downloaded {len(articles)} articles")
for article in articles[:3]:  # Show first 3 articles
    print(f"Headline: {article['headline']}")
    print(f"Date: {article['date']}")
    print(f"URL: {article['url']}")
    print("---")
```

### Advanced Usage

```python
import datetime
from marketwatch_scrapper import MarketWatchScrapper

# Custom topics
custom_topics = [
    '/investing/technology',
    '/investing/stocks',
    '/markets/us'
]

# Create scrapper with custom settings
scrapper = MarketWatchScrapper(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31),
    topics=custom_topics,
    max_workers=5,  # More workers for faster processing
    no_of_captures=20  # More captures per day
)

# Get CDX records first
records = scrapper.get_all_records()
print(f"Found {len(records)} CDX records")

# Get article links
article_links = scrapper.get_all_article_links(records)
print(f"Found {len(article_links)} article links")

# Download articles
articles = scrapper.download()
```

### Available Topics

The package includes predefined topics/base urls for MarketWatch sections:

- `/investing/technology`
- `/investing/autos`
- `/investing/banking`
- `/markets/us`
- `/investing/industries`
- `/investing/stocks`
- `/investing/internet-online-services`
- `/investing/retail`
- `/latest-news`
- `/markets/financial-markets`
- `/investing/software`
- `/markets`

## Configuration Options

### MarketWatchScrapper Parameters

- `start_date`: Start date for scraping (datetime.date)
- `end_date`: End date for scraping (datetime.date)
- `topics`: List of MarketWatch topics to scrape (default: predefined list)
- `max_workers`: Number of worker threads (default: 3)
- `no_of_captures`: Number of captures per day (-1 for all, default: -1)

### Article Data Structure

Each article contains the following fields:

- `headline`: Article headline
- `content`: Full article content
- `summary`: Article summary
- `keywords`: Article keywords
- `companies`: Mentioned companies
- `date`: Publication date (YYYY-MM-DD format)
- `url`: Original article URL
- `timestamp`: Wayback Machine timestamp
- `archive_url`: Wayback Machine archive URL

## Rate Limiting and Etiquette

The package includes built-in rate limiting to be respectful to the Wayback Machine servers:

- Random delays between requests (1-2 seconds)
- Automatic retry mechanism with exponential backoff
- Connection pooling for efficiency

## Error Handling

The package handles various error scenarios gracefully:

- Network timeouts and connection errors
- Missing or invalid article content
- Wayback Machine API failures
- Invalid date ranges

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for educational and research purposes. Please respect the terms of service of MarketWatch and the Wayback Machine. Use responsibly and in accordance with their robots.txt and usage policies. 