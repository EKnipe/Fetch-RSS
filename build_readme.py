from pathlib import Path

from create_xml import (
    GITHUB_PAGES_URL,
    GITHUB_PAGES_URL_NO_HTTPS,
    GITHUB_REPO_NAME,
    GITHUB_REPO_URL,
    XML_EXT,
    Feed,
    parse_feeds,
)

### PATHS

README_PATH: Path = Path("README.md")


### MAIN

def main():
    FEEDS: list[Feed] = parse_feeds()

    output: str = f'''# {GITHUB_REPO_NAME}

RSS feed generator for selected sites which lack native feeds.

Supports:
'''

    asterisk: bool = False
    for feed in FEEDS:
        if not feed.supported:
            continue

        output += f"\n- [{feed.base_url + feed.page_url_suffix}]({("https://" if feed.https else "http://") + feed.base_url + feed.page_url_suffix}), "

        if feed.readme_description:
            output += feed.readme_description
        else:
            output += feed.description

        if not feed.perfect:
            output += "\\*"
            asterisk = True

    if asterisk:
        output += "\n\n\\*Partial functionality"

    output += '''

## Usage

Add the corresponding XML link(s) to your RSS feed reader:

| Feed | Site | XML link |
| --- | --- | --- |'''

    for feed in FEEDS:
        if not feed.supported:
            continue

        output += "\n| "

        if feed.readme_title:
            output += feed.readme_title
        else:
            output += feed.title

        output += f" | [{feed.base_url + feed.page_url_suffix}]({("https://" if feed.https else "http://") + feed.base_url + feed.page_url_suffix}) | "

        output += f"[{GITHUB_PAGES_URL_NO_HTTPS + "/" + feed.xml_filename + XML_EXT}]({GITHUB_PAGES_URL + "/" + feed.xml_filename + XML_EXT}) |"

    output += f'''

Alternatively, clone this repository and run the script manually to create local XML files.

## Dependencies

(see [requirements.txt](requirements.txt) and [GitHub's dependency checker]({GITHUB_REPO_URL}/network/dependencies))

- [Playwright](https://github.com/microsoft/playwright)
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/)
- [dateutil](https://github.com/dateutil/dateutil)
- [requests](https://github.com/psf/requests)
'''

    print(output)

    README_PATH.write_text(
        output,
        encoding = "utf-8"
    )


### EXECUTION

if __name__ == "__main__":
    main()
