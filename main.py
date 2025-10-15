import time
import json
import logging
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/scraper.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

class DapNewsScraper:
    def __init__(self, base_url="https://dap-news.com/"):
        self.base_url = base_url.rstrip("/") + "/"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; DapNewsScraper/1.0)"
        })

    def fetch_page(self, path="/"):
        url = urljoin(self.base_url, path.lstrip("/"))
        logger.info(f"Fetching page: {url}")
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            logger.info(f"Fetched {url} (status {resp.status_code})")
            return resp.text
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def parse_home_via_initial_html(self, html):
        """Fallback parse from initial HTML (if content is partly server-rendered)."""
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for a in soup.select(".td-module-thumb a, .entry-title a"):
            title = a.get("title") or a.get_text(strip=True)
            href = a.get("href")
            if href:
                results.append({"title": title, "url": href})
        return results

    def fetch_via_ajax(self, ajax_url, payload, method="POST"):
        """Generic AJAX fetcher."""
        logger.info(f"Fetching AJAX content from {ajax_url} with payload {payload}")
        try:
            if method == "POST":
                resp = self.session.post(ajax_url, data=payload, timeout=10)
            else:
                resp = self.session.get(ajax_url, params=payload, timeout=10)
            resp.raise_for_status()
            logger.info(f"AJAX fetch success (status {resp.status_code})")
            return resp.text
        except requests.RequestException as e:
            logger.error(f"Error AJAX fetch: {e}")
            return None

    def parse_home_via_ajax(self):
        """
        Inspect the network calls on DAP News homepage to see which AJAX endpoint
        delivers the article listings. Then call that endpoint (often a JSON or HTML fragment),
        parse it, and return the article links.
        """
        # ** You must inspect devtools to find the correct endpoint & payload **
        ajax_endpoint = urljoin(self.base_url, "wp-admin/admin-ajax.php")
        # Example payload, you must change these fields based on actual site
        payload = {
            "action": "td_ajax_block",
            "td_atts": json.dumps({
                "category_id": "",  # maybe empty = all categories
                "limit": "10",
                "block_template_id": "0",
                "ajax_pagination": "next_prev",
            }),
            "td_block_id": "td_uid_1",  # or whatever block ID is used
            "td_column_number": "3",
        }
        text = self.fetch_via_ajax(ajax_endpoint, payload, method="POST")
        if not text:
            return []

        # The response might be HTML or JSON containing HTML. Try parsing.
        # If JSON:
        try:
            j = json.loads(text)
            html_fragment = j.get("html", "")
        except json.JSONDecodeError:
            html_fragment = text

        soup = BeautifulSoup(html_fragment, "html.parser")
        results = []
        for a in soup.select(".td-module-thumb a, .entry-title a"):
            title = a.get("title") or a.get_text(strip=True)
            href = a.get("href")
            if href:
                results.append({"title": title, "url": href})
        return results

    def scrape_home(self):
        """Try AJAX first, fallback to static."""
        results = self.parse_home_via_ajax()
        if results:
            logger.info(f"Got {len(results)} articles via AJAX")
            return results
        logger.info("AJAX failed or returned no results, falling back to static HTML parse")
        html = self.fetch_page("/")
        if not html:
            return []
        return self.parse_home_via_initial_html(html)

    def parse_article_from_html(self, html):
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.select_one("h1.entry-title, h1")
        title = title_tag.get_text(strip=True) if title_tag else None
        paragraphs = soup.select(".td-post-content p, article p, .post-content p")
        body = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        return {"title": title, "body": body}

    def scrape_article_via_ajax(self, article_url):
        """
        Some sites load the article body via AJAX too. If so, inspect devtools
        to find the endpoint & payload.
        """
        # Placeholder — you need to inspect the site's network tab:
        ajax_endpoint = urljoin(self.base_url, "wp-admin/admin-ajax.php")
        payload = {
            "action": "td_ajax_get_post",
            "post_id": self.extract_post_id(article_url),
        }
        resp = self.fetch_via_ajax(ajax_endpoint, payload, method="POST")
        if resp:
            # it might return JSON or HTML fragment
            try:
                j = json.loads(resp)
                html_fragment = j.get("content", "")
            except json.JSONDecodeError:
                html_fragment = resp
            return self.parse_article_from_html(html_fragment)
        return None

    def extract_post_id(self, url):
        """
        Example: if URL is https://dap-news.com/sport/2025/09/17/537427/
        the post_id might be 537427 — you need to adapt this logic.
        """
        parts = url.rstrip("/").split("/")
        last = parts[-1]
        if last.isdigit():
            return int(last)
        # fallback: maybe parse id from query param or other pattern
        return None

    def scrape_article(self, article_url):
        # First try AJAX route
        art = self.scrape_article_via_ajax(article_url)
        if art and art.get("body"):
            art["url"] = article_url
            return art

        # fallback: fetch full page + parse
        html = self.fetch_page(article_url)
        if not html:
            return None
        art = self.parse_article_from_html(html)
        art["url"] = article_url
        return art

    def run(self, max_articles=None):
        articles = self.scrape_home()
        logger.info(f"Found {len(articles)} articles on home")
        scraped = []
        for i, art in enumerate(articles):
            if max_articles and i >= max_articles:
                break
            url = art.get("url")
            if not url:
                continue
            time.sleep(1)
            logger.info(f"Scraping article: {url}")
            art_data = self.scrape_article(url)
            if art_data:
                scraped.append(art_data)
        return scraped


class DapNewsScraperSelenium:
    """
    Fallback heavy version: use Selenium to let JS run and scrape final HTML.
    """
    def __init__(self, base_url="https://dap-news.com/"):
        self.base_url = base_url.rstrip("/") + "/"
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        self.driver = webdriver.Chrome(options=options)

    def fetch_rendered_html(self, url):
        logger.info(f"Selenium fetching: {url}")
        self.driver.get(url)
        # give JS time to load content
        time.sleep(3)
        return self.driver.page_source

    def scrape_article(self, article_url):
        html = self.fetch_rendered_html(article_url)
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.select_one("h1.entry-title, h1")
        title = title_tag.get_text(strip=True) if title_tag else None
        paragraphs = soup.select(".td-post-content p, article p, .post-content p")
        body = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        return {"title": title, "body": body, "url": article_url}

    def scrape_home(self):
        html = self.fetch_rendered_html(self.base_url)
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for a in soup.select(".td-module-thumb a, .entry-title a"):
            title = a.get("title") or a.get_text(strip=True)
            href = a.get("href")
            if href:
                results.append({"title": title, "url": href})
        return results

    def run(self, max_articles=None):
        arts = self.scrape_home()
        scraped = []
        for i, art in enumerate(arts):
            if max_articles and i >= max_articles:
                break
            url = art.get("url")
            if not url:
                continue
            time.sleep(1)
            adata = self.scrape_article(url)
            if adata:
                scraped.append(adata)
        return scraped

    def quit(self):
        self.driver.quit()


if __name__ == "__main__":
    # Pick one
    scraper = DapNewsScraper("https://dap-news.com/")
    data = scraper.run(max_articles=5)
    if not data:
        logger.warning("No data from AJAX scraper, falling back to Selenium")
        selenium_scraper = DapNewsScraperSelenium("https://dap-news.com/")
        data = selenium_scraper.run(max_articles=5)
        selenium_scraper.quit()

    for art in data:
        print("TITLE:", art["title"])
        print("BODY:", art["body"][:200], "…")
        print("URL:", art["url"])
        print("========================================\n")
