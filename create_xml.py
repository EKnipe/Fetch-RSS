### IMPORTS
import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import format_datetime
from html import escape as html_escape
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from playwright.sync_api import sync_playwright

### GLOBAL CONSTANTS

GLOBAL_MAX_ITEMS: int = 20

## Feed XML output
OUTPUT_DIR = Path("_site")
XML_EXT: str = ".xml"

GITHUB_USERNAME: str = "EKnipe"
GITHUB_REPO_NAME: str = "www.economics.ox.ac.uk-news-RSS"

GITHUB_PAGES_URL: str = "https://" + GITHUB_USERNAME + ".github.io/" + GITHUB_REPO_NAME
GITHUB_REPO_URL: str = "https://github.com/" + GITHUB_USERNAME + "/" + GITHUB_REPO_NAME


### CLASS DEFINITIONS

@dataclass
class CSS_selectors:
    item: str
    title: str
    url: str
    date: str | None
    image: str | None
    description: str | None
    page_content: str | None

@dataclass
class Feed:
    id: str
    base_url: str
    page_url_suffix: str
    title: str
    description: str
    max_items: int
    xml_filename: str
    timezone: ZoneInfo
    css_selectors: CSS_selectors

@dataclass
class Item:
    title: str
    url: str
    date_published: datetime
    description: str | None
    image_url: str | None


### FEEDS

FEEDS: list[Feed] = [
    Feed(
        id = "OxEcon",
        base_url = "https://www.economics.ox.ac.uk",
        page_url_suffix = "/news",
        title = "Oxford Economics Department" + " | " + "News",
        description = "News from the Department of Economics, University of Oxford",
        max_items = 20,
        xml_filename = "oxecon_feed",
        timezone = ZoneInfo("Europe/London"),
        css_selectors = CSS_selectors(
            item = "article[class*='listing-item']",
            title = "div[class*='listing-title'] h3",
            url = "a[class*='listing-item-link']",
            date = "div[class*='metadata-data']",
            image = "div[class*='image'] img",
            description = None,
            page_content = "div.content div.field-name-field-content div.field-item"
        )
    ),
    Feed(
        id = "OxHist",
        base_url = "https://www.history.ox.ac.uk",
        page_url_suffix = "/news",
        title = "Oxford Economics Department" + " | " + "News",
        description = "News from the Faculty of History, University of Oxford",
        max_items = 20,
        xml_filename = "oxhist_feed",
        timezone = ZoneInfo("Europe/London"),
        css_selectors = CSS_selectors(
            item = "",
            title = "",
            url = "",
            date = None,
            image = None,
            description = None,
            page_content = None
        )
    )
]


### FUNCTIONS

## HTTP

def fetch_page(page, feed: Feed):
    page.goto(
        feed.base_url + feed.page_url_suffix,
        wait_until = "domcontentloaded",
        timeout = 60_000
    )

    page.wait_for_selector(
        feed.css_selectors.title,
        state = "visible",
        timeout = 30_000,
    )

    page.wait_for_selector(
        feed.css_selectors.url,
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

def absolute_url(url, base_url: str):
    if not url:
        return ""

    return urljoin(base_url, url.strip())

def make_timezone_aware(dt, timezone: ZoneInfo):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone)

    return dt.astimezone(timezone)

def make_description(image_url: str | None, description_text: str | None = None) -> str:
    output: str = ""

    if image_url:
        output += (
            f'<p><img src="{xml_attribute(image_url)}" '
            f'alt="" /></p>'
        )

    if description_text:
        output += f"<p>{description_text}</p>"

    return output

def parse_date(element, timezone: ZoneInfo):
    if element is None:
        return None

    datetime_element = element.find(attrs={"datetime": True})

    if datetime_element:
        datetime_value = datetime_element.get("datetime")

        try:
            parsed = date_parser.parse(datetime_value)
            return make_timezone_aware(parsed, timezone)
        except (ValueError, OverflowError, TypeError):
            pass

    text = get_text(element)

    if not text:
        return None

    try:
        parsed = date_parser.parse(text, fuzzy=True)
        return make_timezone_aware(parsed, timezone)
    except (ValueError, OverflowError, TypeError):
        return None

def get_image_url(element, base_url: str):
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
            return absolute_url(value, base_url)

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
            return absolute_url(candidates[-1][1], base_url)

    return ""

def extract_description(element) -> str:
    if element is None:
        return ""

    return "TODO" ### TODO

## Scraper

def scrape_articles(page_html, feed: Feed) -> list[Item]:
    articles = BeautifulSoup(page_html, "html.parser").select(feed.css_selectors.item)

    if not articles:
        raise RuntimeError("No articles found at " + feed.base_url + feed.page_url_suffix)
    
    items: list[Item] = []

    for article in articles:
        item_title = get_text(article.select_one(feed.css_selectors.title))
        if not item_title:
            continue ## Require title

        url_element = article.select_one(feed.css_selectors.url)
        if not url_element:
            continue ## Require URL
        
        item_url = absolute_url(url_element.get("href", ""), feed.base_url)
        if not item_url:
            continue ## Require href

        item_date = None
        if feed.css_selectors.date:
            item_date = parse_date(article.select_one(feed.css_selectors.date), feed.timezone)
        if item_date is None:
            item_date = datetime.now(feed.timezone) ## Fallback non-date

        image_url = None
        if feed.css_selectors.image:
            image_url = get_image_url(article.select_one(feed.css_selectors.image), feed.base_url)

        item_description = None
        if feed.css_selectors.description:
            item_description = extract_description(article.select_one(feed.css_selectors.description))

        items.append(Item(
                title = item_title,
                url = item_url,
                description = item_description,
                date_published = item_date,
                image_url = image_url
        ))
    
    if not items:
        raise RuntimeError("Failed to extract items")

    # Sort items by date (newest first)
    items.sort(
        key = lambda item: item.date_published,
        reverse = True
    )

    # Remove duplicate URLs
    unique_items: list[Item] = []
    seen_urls: set = set()

    for item in items:
        if item.url not in seen_urls:
            seen_urls.add(item.url)
            unique_items.append(item)

    return unique_items[:min(GLOBAL_MAX_ITEMS, feed.max_items)]

## Article body fetcher

def fetch_body(page, url, content_selector: str) -> str:
    page.goto(
        url,
        wait_until = "domcontentloaded",
        timeout = 60_000
    )

    locator = page.locator(content_selector).first

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
    value = str(value or "")
    value = value.replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{value}]]>"

## Generate RSS

def generate_RSS(items: list[Item], feed: Feed) -> str:
    RSS_items: list[str] = []

    for item in items:
        publication_date: str = format_datetime(item.date_published)

        guid = item.url
        
        RSS_item: str = f"""
    <item>
      <title>{cdata(item.title)}</title>
      <link>{xml_escape(item.url)}</link>
      <guid isPermaLink="true">{xml_escape(guid)}</guid>
      <pubDate>{xml_escape(publication_date)}</pubDate>
      <description>{cdata(item.description)}</description>
    </item>"""

        RSS_items.append(RSS_item)

    last_build_date: str = format_datetime(datetime.now(feed.timezone))

    rss: str = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>{cdata(feed.title)}</title>
    <link>{xml_escape(feed.base_url + feed.page_url_suffix)}</link>
    <description>{cdata(feed.description)}</description>
    <language>en-gb</language>
    <lastBuildDate>{xml_escape(last_build_date)}</lastBuildDate>
    <generator>{GITHUB_REPO_NAME}</generator>
    <ttl>60</ttl>
    <atom:link
      href="{xml_attribute(GITHUB_PAGES_URL + "/" + feed.xml_filename + XML_EXT)}"
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
                f"+{GITHUB_REPO_URL}/)"
            )
        )

        for feed in FEEDS:

            print(f"Processing feed: {feed.id}")
    
            print(f"Fetching {feed.base_url + feed.page_url_suffix}...")

            page_html = fetch_page(page, feed)

            print("Extracting news items...")

            items: list[Item] = scrape_articles(page_html, feed)

            for item in items:
                article_body = None
                if feed.css_selectors.page_content:
                    try:
                        article_body = fetch_body(page, item.url, feed.css_selectors.page_content)
                    except Exception as e:
                        print(f"Failed to fetch article contents from {item.url}: {e}")

                if article_body:
                    if item.description and (len(item.description) > len(article_body)):
                        print(f"WARNING: Overwrote item description with small content for item {item.url}")

                    item.description = make_description(item.image_url) + article_body
                else:
                    item.description = make_description(item.image_url, item.description)

            print(f"Found {len(items)} items. Generating RSS...")

            rss: str = generate_RSS(items, feed)

            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            output_file: Path = OUTPUT_DIR / (feed.xml_filename + XML_EXT)

            output_file.write_text(
                rss,
                encoding="utf-8",
            )

            print(f"Wrote {output_file}")


### EXECUTION

if __name__ == "__main__":
    main()