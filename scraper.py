### IMPORTS
import re
from datetime import datetime
from email.utils import format_datetime
from html import escape as html_escape
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from playwright.sync_api import sync_playwright

### CONSTANTS

BASE_URL: str = "https://www.economics.ox.ac.uk"
PAGE_URL: str = BASE_URL + "/news"

MAX_ITEMS: int = 5 ## Low maximum for fetch testing

FEED_TITLE: str = "Oxford Economics Department" + " | " + "News"
FEED_DESCRIPTION: str = "News from the Department of Economics, University of Oxford"

LOCAL_TIMEZONE = ZoneInfo("Europe/London") ## Oxford timezone

## CSS Selectors (Determined using FiveFilters Feed Creator)
ITEM_SELECTOR: str = "article[class*='listing-item']"
TITLE_SELECTOR: str = "div[class*='listing-title'] h3"
URL_SELECTOR: str = "a[class*='listing-item-link']"
DATE_SELECTOR: str = "div[class*='metadata-data']"
IMAGE_SELECTOR: str = "div[class*='image'] img"

## Selector for page content
CONTENT_SELECTOR: str = "div.content div.field-name-field-content div.field-item"

## Feed XML output
OUTPUT_DIR = Path("_site")
OUTPUT_FILE = OUTPUT_DIR / "feed.xml"

FEED_URL: str = "https://EKnipe.github.io/www.economics.ox.ac.uk-news-RSS/feed.xml"


### FUNCTIONS

## HTTP

def fetch_page(page):
    page.goto(
        PAGE_URL,
        wait_until = "domcontentloaded",
        timeout = 60_000
    )

    page.wait_for_selector(
        TITLE_SELECTOR,
        state = "visible",
        timeout = 30_000,
    )

    page.wait_for_selector(
        URL_SELECTOR,
        state = "attached",
        timeout = 30_000,
    )

    page.wait_for_timeout(1_000)

    page_html = page.content()

    return page_html

## Helper Functions for Scraper

def get_text(element) -> str:
    if element is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        element.get_text(" ", strip=True),
    )

def absolute_url(url):
    if not url:
        return ""

    return urljoin(BASE_URL, url.strip())

def make_timezone_aware(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=LOCAL_TIMEZONE)

    return dt.astimezone(LOCAL_TIMEZONE)

def make_description(image_url: str) -> str:
    if image_url:
        return (
            f'<p><img src="{xml_attribute(image_url)}" '
            f'alt="" /></p>'
        )
    else:
        return ""

def parse_date(element):
    if element is None:
        return None

    datetime_element = element.find(attrs={"datetime": True})

    if datetime_element:
        datetime_value = datetime_element.get("datetime")

        try:
            parsed = date_parser.parse(datetime_value)
            return make_timezone_aware(parsed)
        except (ValueError, OverflowError, TypeError):
            pass

    text = get_text(element)

    if not text:
        return None

    try:
        parsed = date_parser.parse(text, fuzzy=True)
        return make_timezone_aware(parsed)
    except (ValueError, OverflowError, TypeError):
        return None

def get_image_url(element):
    if element is None:
        return ""

    for attribute in ( ### prefer srcset?
        "src",
        "data-src",
        "data-lazy-src",
        "data-original"
    ):
        value = element.get(attribute)
        if value:
            return absolute_url(value)

    srcset = element.get("srcset") or element.get("data-srcset")

    if srcset:
        candidates: list = []

        for candidate in srcset.split(","):
            candidate = candidate.strip()
            if not candidate:
                continue

            parts = candidate.split()
            url = parts[0]

            descriptor = 0
            if len(parts) > 1:
                match = re.match(r"(\d+)(w|x)", parts[1])
                if match:
                    descriptor = int(match.group(1))

            candidates.append((descriptor, url))

        if candidates:
            candidates.sort(key=lambda x: x[0])
            return absolute_url(candidates[-1][1])

    return ""

## Scraper

def scrape_articles(page_html) -> list[dict]:
    articles = BeautifulSoup(page_html, "html.parser").select(ITEM_SELECTOR)

    if not articles:
        raise RuntimeError("No articles found at " + PAGE_URL)
    
    items: list[dict] = []

    for article in articles:
        item_title = get_text(article.select_one(TITLE_SELECTOR))
        if not item_title:
            continue ## Require title

        url_element = article.select_one(URL_SELECTOR)
        if not url_element:
            continue ## Require URL
        
        item_url = absolute_url(url_element.get("href", ""))
        if not item_url:
            continue ## Require href

        item_date = parse_date(article.select_one(DATE_SELECTOR))
        if item_date is None:
            item_date = datetime.now(LOCAL_TIMEZONE) ## Fallback non-date

        image_url = get_image_url(article.select_one(IMAGE_SELECTOR))

        item_description = make_description(image_url)

        items.append({
                "title": item_title,
                "url": item_url,
                "description": item_description,
                "published": item_date
        })
    
    if not items:
        raise RuntimeError("Failed to extract items")

    # Sort items by date (newest first)
    items.sort(
        key = lambda item: item["published"],
        reverse = True
    )

    # Remove duplicate URLs
    unique_items: list[dict] = []
    seen_urls: set = set()

    for item in items:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            unique_items.append(item)

    return unique_items[:MAX_ITEMS]

## Article body fetcher

def fetch_body(page, url) -> str:
    page.goto(
        url,
        wait_until = "domcontentloaded",
        timeout = 60_000
    )

    locator = page.locator(CONTENT_SELECTOR).first

    locator.wait_for(
        state = "visible",
        timeout = 30_000
    )

    article_html: str = locator.inner_html()

    soup = BeautifulSoup(article_html, "html.parser")

    for unwanted in soup.select("script, style, noscript"):
        unwanted.decompose()

    for paragraph in soup.find_all("p"):
        if not paragraph.get_text(" ", strip=True):
            paragraph.decompose()

    return str(soup).strip()

## Helper Functions for RSS

def xml_attribute(value):
    return html_escape(str(value), quote=True)

def xml_escape(value):
    return html_escape(str(value), quote=False)

def cdata(value) -> str:
    value: str = str(value or "")
    value = value.replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{value}]]>"

## Generate RSS

def generate_RSS(items: list[dict]) -> str:
    RSS_items: list[str] = []

    for item in items:
        publication_date: str = format_datetime(item["published"])

        guid = item["url"]
        
        RSS_item: str = f"""
    <item>
      <title>{cdata(item["title"])}</title>
      <link>{xml_escape(item["url"])}</link>
      <guid isPermaLink="true">{xml_escape(guid)}</guid>
      <pubDate>{xml_escape(publication_date)}</pubDate>
      <description>{cdata(item["description"])}</description>
    </item>"""

        RSS_items.append(RSS_item)

    last_build_date: str = format_datetime(datetime.now(LOCAL_TIMEZONE))

    rss: str = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>{cdata(FEED_TITLE)}</title>
    <link>{xml_escape(PAGE_URL)}</link>
    <description>{cdata(FEED_DESCRIPTION)}</description>
    <language>en-gb</language>
    <lastBuildDate>{xml_escape(last_build_date)}</lastBuildDate>
    <generator>Oxford Economics RSS scraper</generator>
    <ttl>60</ttl>
    <atom:link
      href="{xml_attribute(FEED_URL)}"
      rel="self"
      type="application/rss+xml" />
{''.join(RSS_items)}
  </channel>
</rss>
"""

    return rss


### MAIN

def main():
    print("Launching Playwright...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            user_agent = (
                "Mozilla/5.0 (compatible; www.economics.ox.ac.uk-news-RSS/1.0; "
                "+https://github.com/EKnipe/www.economics.ox.ac.uk-news-RSS/)"
            )
        )
    
        print(f"Fetching {PAGE_URL}...")

        page_html = fetch_page(page)

        print("Extracting news items...")

        items: list[dict] = scrape_articles(page_html)

        for item in items:
            try:
                article_body = fetch_body(page, url = item["url"])
                item["description"] += article_body
            except Exception as e:
                print(f"Failed to fetch article contents from {item["url"]}: {e}")

    print(f"Found {len(items)} items. Generating RSS...")

    rss: str = generate_RSS(items)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    OUTPUT_FILE.write_text(
        rss,
        encoding="utf-8",
    )

    print(f"Wrote {OUTPUT_FILE}")


### EXECUTION

if __name__ == "__main__":
    main()