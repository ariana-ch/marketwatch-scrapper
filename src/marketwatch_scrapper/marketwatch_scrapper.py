import datetime
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from logging import getLogger, StreamHandler, INFO
from typing import List, Optional, Dict

import pandas as pd
import requests
from bs4 import BeautifulSoup
from newspaper import Article
from requests.adapters import HTTPAdapter, Retry

TOPICS = [
    '/investing/technology',
    '/investing/autos',
    '/investing/banking',
    '/markets/us',
    '/investing/industries',
    '/investing/stocks',
    '/investing/internet-online-services',
    '/investing/retail',
    '/latest-news',
    '/markets/financial-markets',
    '/investing/software',
    '/markets'
]

EXCLUDE_PATTERNS = [
    'signin', 'login', 'subscri', 'member', 'footer', 'about', 'contact', 'privacy', 'terms', 'help',
    'video', 'podcast', 'audio', '-worship', 'architecture', 'lifestyle', 'fashion', 'on-the-clock',
    'recipes', 'travel', 'real-estate', 'science', 'health', 'sports', 'arts-culture', 'art-review',
    'obituar', 'wine', 'film-review', 'book-review', 'television-review', 'arts', 'art', '-review',
    'bookshelf', 'play.google', 'apple.com/us/app', 'policy/legal-policies', 'djreprints', 'register',
    'wsj.jobs', 'smartmoney', 'classifieds', 'cultural', 'masterpiece', 'puzzle', 'personal-finance',
    'style', 'customercenter', 'snapchat', 'cookie-notice', 'facebook', 'instagram', 'twitter',
    '/policy/copyright-policy', '/policy/data-policy', 'market-data/quotes/', 'buyside',
    'accessibility-statement', 'press-room', 'mansionglobal', 'images', 'mailto', 'youtube', '#',
    'get.investors'
]


def _get_logger(name: str = __name__):
    # Configure logging
    logger = getLogger(name)
    logger.setLevel(INFO)
    handler = StreamHandler()
    handler.setLevel(INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = _get_logger('marketwatch')


def safe_get(url: str, session: requests.Session, timeout: int = 10) -> Optional[requests.Response]:
    """
    GET with retries configured on the session,
    plus a randomized sleep to throttle.
    Returns None if all retries fail.
    """
    # Throttle - this sleep is per-thread, so for parallel calls, it means each thread waits.
    time.sleep(random.uniform(1.0, 2.0))  # Increased sleep for better etiquette
    logger.debug(f"GET {url}")
    try:
        resp = session.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        logger.error(f"GET {url} failed with exception: {e}")
        return None


def create_session() -> requests.Session:
    """
    Create a safe session for GET requests.
    This session will be shared across threads to enable connection pooling.
    """
    session = requests.Session()
    # Increased total retries and backoff factor for more resilience
    retries = Retry(
        total=8,  # Reduced retries
        backoff_factor=2,  # 1s, 2s, 4s, 8s, 16s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def cdx_query(
    url: str,
    session: requests.Session,
    start_date: datetime.date,
    end_date: datetime.date
) -> List[List[str]]:
    """
    Query the Wayback Machine's CDX API for a specific URL and date range.

    This function constructs a URL for the CDX API, sends a GET request,
    and returns a list of records containing timestamps and original URLs.
    The records are filtered to include only HTML pages with a status code of 200.
    The results are collapsed by digest to avoid duplicates.
    The function raises a WaybackMachineNoLinks exception if no records are found
    or if the request fails.

    Args:
        url: The URL to query.
        session: A requests.Session object for making HTTP requests.
        start_date: The start date for the query (inclusive).
        end_date: The end date for the query (inclusive).

    Returns:
        A list of records, where each record is a list containing a timestamp and the original URL.
    Raises:
        WaybackMachineNoLinks: If no records are found or if the request fails.
    """
    cdx_url = (
        "https://web.archive.org/cdx/search/cdx"
        f"?url={url}"
        f"&fl=timestamp,original"
        f"&from={start_date:%Y%m%d}"
        f"&to={end_date:%Y%m%d}"
        "&output=json"
        "&filter=mimetype:text/html"
        "&filter=statuscode:200"
        "&collapse=digest"
    )
    resp = safe_get(cdx_url, session)
    if not resp:
        logger.error(f"Failed to fetch index for URL '{cdx_url}'")
        return []

    records = resp.json()[1:]  # skip header row
    if not records:
        logger.warning(f"No records found for URL '{url}'")
    return records


def is_article(url: str) -> bool:
    url = url.rsplit('https://', 1)[-1]
    if '-' not in url:
        return False
    tail = url.rsplit('-', 1)[-1]

    # Check if the URL ends with a valid article ID (at least 3 digits)
    return len(re.compile(r'\d').findall(tail)) > 3


def extract_article_links(soup: BeautifulSoup) -> List[str]:
    """
    Extract all article links from the BeautifulSoup object.
    Focuses on finding actual article URLs, not navigation or other links.
    """
    article_links = []

    # Find all links
    links = soup.find_all('a', href=True)

    for link in links:
        href = link['href']

        # Skip if href is empty or just a fragment
        if (
            not href
            or href.startswith('#')
            or any([pattern in href.lower() for pattern in EXCLUDE_PATTERNS])
            or not href.startswith('http')
        ):
            continue

        href = href.rsplit('?mod', 1)[0]  # Remove query parameters if any

        # Check if it's an article URL
        if is_article(href):
            article_links.append(href)

    return list(set(article_links))


def process_article_url(
    urls: List[str],
    session: requests.Session
) -> Optional[Dict]:
    """
    Process a single article to extract its content.
    Returns article data if successful, None otherwise.
    """
    for url in urls:
        try:
            response = safe_get(url, session)
            if not response or response.status_code != 200:
                continue

            article_data = {
                'headline': '',
                'content': '',
                'summary': '',
                'keywords': '',
                'companies': '',
                'date': '',
                'url': url,
                'timestamp': re.findall(r'\d{14}', url),
                'archive_url': url
            }

            # Use the unified extraction function
            article = Article('www.marketwatch.com', language='en')
            article.download(input_html=response.text)
            article.parse()
            article.nlp()


            keywords = (
                article.meta_keywords
                or article.keywords
                or article.meta_data['news_keywords']
                or article.meta_data['keywords']
            )
            keywords = keywords.split(',') if isinstance(keywords, str) else keywords
            excluded_keywords = re.compile([
                r'^\d+$',            # pure numbers
                r'^LINK\|',          # starts with LINK|
                r'WSJ',              # contains WSJ or WSJ-
                r'^SYND$',           # exactly SYND
                r'factiva',
                r'filter',
                r'gfx-',
                r'factset',
            ])
            keywords = [keyword.replace('wsj', '') for keyword in keywords if not excluded_keywords.search(keyword)]

            keywords = ','.join([
                x for x in keywords
                if not any([excluded in x.lower() for excluded in ['factiva', 'filter']])
            ])

            companies = ','.join([x for x in keywords.split(',') if 'US:' in x])

            title = (article.title or article.meta_data['parsely-title'] or '').strip()

            content = (
                article.meta_description + '\n' + article.text
                if article.meta_description else article.text
            )
            summary = article.summary or article.meta_data.get('parsely-summary', '')

            date = (
                article.publish_date
                or re.compile(r'\d{8}$').findall(article.meta_data['article.id'] or '')[0]
            )
            if isinstance(date, str) and len(date) == 8:
                try:
                    date = datetime.datetime.strptime(date, '%Y%m%d').date()
                except ValueError:
                    date = None
            else:
                date = None
            article_data['headline'] = title
            article_data['content'] = content.strip()
            article_data['summary'] = summary.strip()
            article_data['keywords'] = keywords.strip()
            article_data['companies'] = companies
            article_data['date'] = date.strftime('%Y-%m-%d') if date else ''
            return article_data
        except Exception as e:
            logger.error(f"Error processing article {url}: {e}")
            continue
    return


class MarketWatchScrapper:
    def __init__(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        topics: list = TOPICS,
        max_workers: int = 3,
        no_of_captures: int = -1
    ):
        self.url = 'www.marketwatch.com'
        self.start_date = start_date
        self.end_date = end_date
        self.topics = topics
        self.max_workers = max_workers
        self.no_of_captures = no_of_captures
        self.session = create_session()
        self.records = None
        self.article_links = None

    def get_all_records(self) -> List[List[str]]:
        def random_choice(df):
            """
            Randomly select a specified number of captures from each group.
            If no captures are available, return an empty DataFrame.
            """
            if len(df) == 0:
                return pd.DataFrame(columns=df.columns)
            return df.sample(
                n=min(self.no_of_captures, len(df)),
                replace=False,
                random_state=42
            )

        logger.info(
            f'Retrieving records from:\n'
            f'{"\n".join([f"{self.url}{topic}" for topic in self.topics])}'
        )
        records = cdx_query(
            url=self.url,
            session=self.session,
            start_date=self.start_date,
            end_date=self.end_date
        )
        if not records:
            logger.warning(
                f"No records found for URL '{self.url}' between {self.start_date} and {self.end_date}"
            )
            return []
        logger.info(
            f"Found {len(records)} records for {self.url} between {self.start_date} and {self.end_date}"
        )

        if self.no_of_captures > -1:
            df = pd.DataFrame(records, columns=['timestamp', 'original'])
            df['datetime'] = pd.to_datetime(df['timestamp'], format='%Y%m%d%H%M%S')
            df['date'] = df['datetime'].dt.date
            df = df.sort_values(by='datetime')
            df['clean_url'] = df.original.apply(
                lambda x: '/'.join([
                    i.strip()
                    for i in x.replace('http://', '').replace('https://', '').split('/')
                    if i.strip()
                ])
            )
            df = (
                df.groupby(['date', 'clean_url'], as_index=False)
                .apply(random_choice, include_groups=False)
                .reset_index(drop=True)
            )
            records = df[['timestamp', 'original']].values.tolist()
        records = [
            [x[0], x[1] + '/' + topic]
            for x in records for topic in self.topics
        ]
        return records

    def get_all_article_links(self, records: List[List[str]]) -> List[str]:
        """
        Fetch all article links from the Wayback Machine for the specified URL and date range.
        This method retrieves CDX records and processes each record to extract article links.
        """

        def _do_get_article_links(record) -> Optional[List[str]]:
            timestamp, website = record

            archive_url = f'https://web.archive.org/web/{timestamp}/{website}'
            response = safe_get(archive_url, self.session)
            if not response:
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            links = list(set(extract_article_links(soup)))
            return links

        logger.info(
            f"Fetching all article links between {self.start_date} and {self.end_date}"
        )

        all_links = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(_do_get_article_links, record)
                for record in records
            ]

            for future in futures:
                result = future.result()
                if result:
                    all_links.extend(result)

        df = pd.DataFrame(all_links, columns=['url'])
        df['date'] = pd.to_datetime(
            df['url'].str.extract(r'(\d{8})')[0], format='%Y%m%d'
        )
        df['article_url'] = df.url.apply(
            lambda x: x.rsplit('https://', 1)[-1]
        )
        df = df.groupby(['article_url']).url.apply(
            lambda x: x.tolist()
        ).reset_index()
        all_links = df['url'].tolist()
        logger.info(
            f"Found {len(all_links)} distinct article links from between {self.start_date} and {self.end_date}"
        )
        return all_links

    def download(self) -> List[Dict]:
        logger.info(
            f"Starting download for {self.url} from {self.start_date} to {self.end_date}"
        )
        records = self.get_all_records()

        self.records = records

        logger.info(f"Retrieved {len(records)} CDX records")
        article_links = self.get_all_article_links(records)
        self.article_links = article_links

        if not article_links:
            logger.error("Could not retrieve any article links")
            return []

        all_articles = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(process_article_url, link_list, self.session)
                for link_list in article_links
            ]

            for future in futures:
                result = future.result()
                if result:
                    all_articles.append(result)
        logger.info(f"Successfully extracted {len(all_articles)} articles")
        logger.info(
            f"Finished processing. Total articles extracted: {len(all_articles)}"
        )
        return all_articles


if __name__ == "__main__":
    # main()
    # Test with a smaller date range and fewer workers
    mw = MarketWatchScrapper(
        no_of_captures=15,
        start_date=datetime.date(2025, 1, 10),
        end_date=datetime.date(2025, 1, 10),  # Just one day
        max_workers=3  # Reduced workers
    )
    downloaded_articles = mw.download()

    # Print summary
    print(f"\n--- Download Summary ---")
    print(f"Total articles extracted: {len(downloaded_articles)}")

    # Print first few articles as examples
    for i, article in enumerate(downloaded_articles[:3]):
        print(f"\n--- Article {i + 1} ---")
        print(f"Headline: {article.get('headline', 'N/A')}")
        print(f"Author: {article.get('author', 'N/A')}")
        print(f"Date: {article.get('date', 'N/A')}")
        print(f"URL: {article.get('url', 'N/A')}")
        print(f"Summary: {article.get('summary', 'N/A')[:200]}...")
        print(f"Content length: {len(article.get('content', ''))} characters")

    # Save to JSON file
    if downloaded_articles:
        with open('extracted_articles_new.json', 'w', encoding='utf-8') as f:
            json.dump(downloaded_articles, f, indent=2, ensure_ascii=False)
        print(f"\nArticles saved to extracted_articles.json")
