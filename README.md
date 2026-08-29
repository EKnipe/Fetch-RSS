# Fetch-RSS

RSS feed generator for selected sites which lack native feeds.

Supports:

- [www.economics.ox.ac.uk/news](https://www.economics.ox.ac.uk/news), the news page of the Department of Economics, University of Oxford
- [www.history.ox.ac.uk/news](https://www.history.ox.ac.uk/news), the news page of the Faculty of History, University of Oxford
- [www.classics.ox.ac.uk/news](https://www.classics.ox.ac.uk/news), the news page of the Faculty of Classics, University of Oxford\*
- [www.maths.ox.ac.uk/news](https://www.maths.ox.ac.uk/news), the news page of the Mathematical Institute, University of Oxford\*
- [www.biology.ox.ac.uk/news](https://www.biology.ox.ac.uk/news), the news page of the Department of Biology, University of Oxford\*
- [www.ox.ac.uk/news](https://www.ox.ac.uk/news), the news page of the University of Oxford\*

\*Partial functionality

## Usage

Add the corresponding XML link(s) to your RSS feed reader:

| Feed | Site | XML link |
| --- | --- | --- |
| Department of Economics, University of Oxford | [www.economics.ox.ac.uk/news](https://www.economics.ox.ac.uk/news) | [eknipe.github.io/Fetch-RSS/oxecon_feed.xml](https://eknipe.github.io/Fetch-RSS/oxecon_feed.xml) |
| Faculty of History, University of Oxford | [www.history.ox.ac.uk/news](https://www.history.ox.ac.uk/news) | [eknipe.github.io/Fetch-RSS/oxhist_feed.xml](https://eknipe.github.io/Fetch-RSS/oxhist_feed.xml) |
| Faculty of Classics, University of Oxford | [www.classics.ox.ac.uk/news](https://www.classics.ox.ac.uk/news) | [eknipe.github.io/Fetch-RSS/oxclassics_feed.xml](https://eknipe.github.io/Fetch-RSS/oxclassics_feed.xml) |
| Mathematical Institute, University of Oxford | [www.maths.ox.ac.uk/news](https://www.maths.ox.ac.uk/news) | [eknipe.github.io/Fetch-RSS/oxmaths_feed.xml](https://eknipe.github.io/Fetch-RSS/oxmaths_feed.xml) |
| Department of Biology, University of Oxford | [www.biology.ox.ac.uk/news](https://www.biology.ox.ac.uk/news) | [eknipe.github.io/Fetch-RSS/oxbio_feed.xml](https://eknipe.github.io/Fetch-RSS/oxbio_feed.xml) |
| University of Oxford | [www.ox.ac.uk/news](https://www.ox.ac.uk/news) | [eknipe.github.io/Fetch-RSS/oxuni_feed.xml](https://eknipe.github.io/Fetch-RSS/oxuni_feed.xml) |

Alternatively, clone this repository and run the script manually to create local XML files.

## Dependencies

(see [requirements.txt](requirements.txt) and [GitHub's dependency checker](https://github.com/EKnipe/Fetch-RSS/network/dependencies))

- [Playwright](https://github.com/microsoft/playwright)
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/)
- [dateutil](https://github.com/dateutil/dateutil)
- [requests](https://github.com/psf/requests)
