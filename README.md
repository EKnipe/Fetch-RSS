# [www.economics.ox.ac.uk/news](https://www.economics.ox.ac.uk/news) RSS

RSS feed generator for selected sites which lack native feeds.

Supports:

- [www.economics.ox.ac.uk/news](https://www.economics.ox.ac.uk/news), the news page of the Department of Economics, University of Oxford
- [www.history.ox.ac.uk/news](https://www.history.ox.ac.uk/news), the news page of the Faculty of History, University of Oxford

## Usage

Add the corresponding XML link(s) to your RSS feed reader:

| Feed | Site | XML link |
| --- | --- | --- |
| Department of Economics, University of Oxford | [www.economics.ox.ac.uk/news](https://www.economics.ox.ac.uk/news) | [eknipe.github.io/www.economics.ox.ac.uk-news-RSS/oxecon_feed.xml](https://eknipe.github.io/www.economics.ox.ac.uk-news-RSS/oxecon_feed.xml) |
| Faculty of History, University of Oxford | [www.history.ox.ac.uk/news](https://www.history.ox.ac.uk/news) | [eknipe.github.io/www.economics.ox.ac.uk-news-RSS/oxhist_feed.xml](https://eknipe.github.io/www.economics.ox.ac.uk-news-RSS/oxhist_feed.xml) |

Alternatively, clone this repository and run the script manually to create local XML files.

## Dependencies

(see [requirements.txt](requirements.txt) and [GitHub's dependency checker](https://github.com/EKnipe/www.economics.ox.ac.uk-news-RSS/network/dependencies))

- [Playwright](https://github.com/microsoft/playwright)
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/)
- [dateutil](https://github.com/dateutil/dateutil)
