"""
MarketWatch Scraper Package

A Python package for scraping MarketWatch articles from the Wayback Machine.

Author: Ariana Christodoulou <ariana.chr@gmail.com>
"""

from .marketwatch_scrapper import (
    MarketWatchAdapter,
    safe_get,
    create_session,
    cdx_query,
    is_article,
    extract_article_links,
    process_article_url,
    TOPICS,
    EXCLUDE_PATTERNS,
    logger
)

__version__ = "0.1.0"
__author__ = "Ariana Christodoulou"
__email__ = "ariana.chr@gmail.com"

__all__ = [
    "MarketWatchAdapter",
    "safe_get",
    "create_session", 
    "cdx_query",
    "is_article",
    "extract_article_links",
    "process_article_url",
    "TOPICS",
    "EXCLUDE_PATTERNS",
    "logger"
]
