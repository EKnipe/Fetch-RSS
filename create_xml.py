### IMPORTS
import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import format_datetime
from html import escape as html_escape
from json import load as load_json
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from playwright.sync_api import sync_playwright
from requests import get as get_request

### GLOBAL CONSTANTS

GLOBAL_MAX_ITEMS: int = 20
GLOBAL_MAX_PAGES: int = 22
TIMEOUT_S: int = 10
PAUSE_MS: int = 1_000

FEEDS_ENABLED_DEFAULT: bool = True

DEFAULT_TIMEZONE: ZoneInfo = ZoneInfo("UTC")

GITHUB_USERNAME: str = "EKnipe"
GITHUB_REPO_NAME: str = "Fetch-RSS"

## JSON
FEEDS_JSON_PATH: Path = Path("feeds.json")

## Feed XML output
OUTPUT_DIR: Path = Path("_site")
XML_EXT: str = ".xml"

TIMEOUT_MS: int = TIMEOUT_S * 1000

GITHUB_PAGES_URL: str = "https://" + GITHUB_USERNAME + ".github.io/" + GITHUB_REPO_NAME
GITHUB_REPO_URL: str = "https://github.com/" + GITHUB_USERNAME + "/" + GITHUB_REPO_NAME

USER_AGENT: str = "Mozilla/5.0 (compatible; "+ GITHUB_REPO_NAME + "/1.0; +" + GITHUB_REPO_URL + "/)"


### CLASS DEFINITIONS

@dataclass
class CSS_Selectors:
    item: str
    title: str
    url: str
    date: str | None = None
    image: str | None = None
    description: str | None = None
    page_content: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "CSS_Selectors":
        return cls(**data)

@dataclass
class Feed:
    id: str
    base_url: str
    page_url_suffix: str
    title: str
    description: str
    xml_filename: str
    css_selectors: CSS_Selectors
    page_num_selector: str | None = None
    main_page_requires_js: bool = True ### conservative default
    articles_require_js: bool = False ### aggressive default to discover what breaks
    max_items: int = GLOBAL_MAX_ITEMS
    max_pages: int = GLOBAL_MAX_PAGES
    timezone: ZoneInfo = DEFAULT_TIMEZONE
    enabled: bool = FEEDS_ENABLED_DEFAULT

    @classmethod
    def from_dict(cls, data: dict) -> "Feed":
        data = data.copy()
        data["timezone"] = ZoneInfo(data["timezone"])
        data["css_selectors"] = CSS_Selectors.from_dict(data["css_selectors"])
        return cls(**data)

@dataclass
class Item:
    title: str
    url: str
    date_published: datetime
    description: str | None
    image_url: str | None

def parse_feeds() -> list[Feed]:
    with open(FEEDS_JSON_PATH, encoding="utf-8") as f:
        return [Feed.from_dict(x) for x in load_json(f)]


### FUNCTIONS

## HTTP

def fetch_page_playwright(page, css_selectors: CSS_Selectors, url: str):
    page.goto(
        url,
        wait_until = "domcontentloaded",
        timeout = TIMEOUT_MS
    )

    page.wait_for_selector(
        css_selectors.title,
        state = "visible",
        timeout = TIMEOUT_MS,
    )

    page.wait_for_selector(
        css_selectors.url,
        state = "attached",
        timeout = TIMEOUT_MS,
    )

    page.wait_for_timeout(PAUSE_MS)

    page_html = page.content()

    return page_html

def fetch_page_requests(url):
    response = get_request(
        url,
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml"
        },
        timeout = TIMEOUT_S
    )

    response.raise_for_status()

    return response.text

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

def make_timezone_aware(dt: datetime, timezone: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone)

    return dt.astimezone(timezone)

def make_description(image_url: str | None, description_text: str | None = None) -> str:
    output: str = ""

    if image_url:
        output += f'<p><img src="{xml_attribute(image_url)}" alt="" /></p>'

    if description_text:
        output += f"<p>{description_text}</p>"

    return output

def parse_date(element, timezone: ZoneInfo) -> datetime | None:
    if element is None:
        return None

    datetime_element = element.find(attrs={"datetime": True})

    if datetime_element:
        datetime_value = datetime_element.get("datetime")

        try:
            parsed: datetime = date_parser.parse(datetime_value)
            return make_timezone_aware(parsed, timezone)
        except (ValueError, OverflowError, TypeError):
            pass

    text: str = get_text(element)

    if not text:
        return None

    try:
        parsed: datetime = date_parser.parse(text, fuzzy=True)
        return make_timezone_aware(parsed, timezone)
    except (ValueError, OverflowError, TypeError):
        return None

def get_image_url(element, base_url: str) -> str:
    if element is None:
        return ""

    for attribute in ( ### TODO: Prefer srcset for some feeds?
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
        candidates: list[tuple] = []

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

def unique_items(items: list[Item]) -> list[Item]:
    unique: list[Item] = []
    seen_urls: set[str] = set()
    for item in items:
        if item.url not in seen_urls:
            seen_urls.add(item.url)
            unique.append(item)
    
    return unique

## Scraper

def scrape_articles(page_html, feed: Feed) -> list[Item]:
    articles = BeautifulSoup(page_html, "html.parser").select(feed.css_selectors.item)

    if not articles:
        raise RuntimeError("No articles found at " + feed.base_url + feed.page_url_suffix)
    
    items: list[Item] = []

    for article in articles:
        item_title: str = get_text(article.select_one(feed.css_selectors.title))
        if not item_title:
            continue ## Require title

        url_element = article.select_one(feed.css_selectors.url)
        if not url_element:
            continue ## Require URL
        
        item_url: str = absolute_url(url_element.get("href", ""), feed.base_url)
        if not item_url:
            continue ## Require href

        item_date: datetime | None = None
        if feed.css_selectors.date:
            item_date = parse_date(article.select_one(feed.css_selectors.date), feed.timezone)
        if item_date is None:
            item_date = datetime.now(feed.timezone) ## Fallback non-date

        image_url: str | None = None
        if feed.css_selectors.image:
            image_url = get_image_url(article.select_one(feed.css_selectors.image), feed.base_url)

        item_description: str | None = None
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

    return items

## Article body fetcher

def fetch_body_playwright(page, url, content_selector: str) -> str:
    page.goto(
        url,
        wait_until = "domcontentloaded",
        timeout = TIMEOUT_MS
    )

    locator = page.locator(content_selector).first

    locator.wait_for(
        state = "visible",
        timeout = TIMEOUT_MS
    )

    article_html: str = locator.inner_html()

    soup: BeautifulSoup = BeautifulSoup(article_html, "html.parser")

    for unwanted in soup.select("script, style, noscript"):
        unwanted.decompose()

    for paragraph in soup.find_all("p"):
        if not paragraph.get_text(" ", strip=True):
            paragraph.decompose()

    return str(soup).strip()

def fetch_body_requests(page, url, content_selector: str) -> str:
    return fetch_body_playwright(page, url, content_selector) ### TEMP / TODO

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

        guid: str = item.url
        
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

    return f"""<?xml version="1.0" encoding="UTF-8"?>
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
    <atom:link
      href="{xml_attribute(GITHUB_PAGES_URL + "/" + feed.xml_filename + XML_EXT)}"
      rel="self"
      type="application/rss+xml" />
{''.join(RSS_items)}
  </channel>
</rss>
"""


### MAIN

def main():
    print("loading feed configurations...")

    feeds: list[Feed] = parse_feeds()

    print("Launching Playwright...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            user_agent = USER_AGENT
        )

        feed_count: int = 0
        for feed in feeds:
            try:
                if not feed.enabled:
                    print(f"Skipping feed: {feed.id}")
                    continue

                print(f"Processing feed: {feed.id}")

                feed_visit_count: int = 0

                feed_page_url: str = feed.base_url + feed.page_url_suffix

                items: list[Item] = []
                page_number: int = 1
                while len(items) < feed.max_items and feed_visit_count < min(feed.max_pages, GLOBAL_MAX_PAGES):
                    if page_number == 1:
                        working_url: str = feed_page_url
                    else:
                        if not feed.page_num_selector:
                            break
                        working_url: str = feed_page_url + feed.page_num_selector + str(page_number)
        
                    print(f"Fetching {working_url}...")

                    if feed.main_page_requires_js:
                        page_html = fetch_page_playwright(page, feed.css_selectors, working_url)
                    else:
                        page_html = fetch_page_requests(working_url)

                    print("Extracting news items...")

                    initial_item_count: int = len(items)

                    items += scrape_articles(page_html, feed)
                    feed_visit_count += 1
                
                    items = unique_items(items)

                    if len(items) <= initial_item_count:
                        break

                    page_number += 1

                # Sort items by date (newest first)
                items.sort(
                    key = lambda item: item.date_published,
                    reverse = True
                )
                
                items = items[:min(GLOBAL_MAX_ITEMS, feed.max_items)]

                for item in items:
                    article_body: str | None = None

                    if feed.css_selectors.page_content and feed_visit_count < min(feed.max_pages, GLOBAL_MAX_PAGES):
                        feed_visit_count += 1

                        try:
                            if feed.articles_require_js:
                                article_body = fetch_body_playwright(page, item.url, feed.css_selectors.page_content)
                            else:
                                article_body = fetch_body_requests(page, item.url, feed.css_selectors.page_content) ### pass page for temp passthrough function
                        except Exception as e_item:
                            print(f"Failed to fetch article contents from {item.url}: {e_item}")

                    if article_body:
                        if item.description and (len(item.description) > len(article_body)):
                            print(f"WARNING: Overwrote item description with small content for item {item.url}")

                        item.description = make_description(item.image_url) + article_body
                    else:
                        item.description = make_description(item.image_url, item.description)

                print(f"Found {len(items)} items. Generating RSS...")

                rss: str = generate_RSS(items, feed)

                print("Writing XML...")

                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

                output_file: Path = OUTPUT_DIR / (feed.xml_filename + XML_EXT)

                output_file.write_text(
                    rss,
                    encoding="utf-8",
                )

                print(f"Wrote {output_file}")
                feed_count += 1
            except Exception as e_feed:
                print(f"Exception processing feed: {e_feed}")

    print(f"{feed_count} {"feed" if feed_count == 1 else "feeds"} fetched")


### EXECUTION

if __name__ == "__main__":
    main()