import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# --- CONFIG ---
START_URL = "https://dap-news.com/category/sport/"
WAIT_TIME = 10
CSV_FILE = "dap_news_links.csv"

# --- SETUP SELENIUM ---
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--window-size=1920,1080")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
)

driver = webdriver.Chrome(options=options)
driver.get(START_URL)

all_links = []
page_count = 0

try:
    while True:
        page_count += 1
        print(f"\n🌐 Scraping page {page_count} ...")
        
        # Wait for posts to load
        WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.infinite-post"))
        )
        time.sleep(2)
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")
        posts = soup.select("li.infinite-post a")

        # Extract unique hrefs
        new_links = []
        for a in posts:
            href = a.get("href")
            if href and href not in all_links:
                all_links.append(href)
                new_links.append(href)

        print(f"✅ Found {len(new_links)} new links (Total so far: {len(all_links)})")

        # Try to find and click the "Next" link
        try:
            next_button = driver.find_element(By.XPATH, "//a[contains(text(), 'Next')]")
            next_href = next_button.get_attribute("href")
            if not next_href:
                print("⚠️ No next link found. Stopping.")
                break

            # Go to next page
            driver.get(next_href)
            time.sleep(2)

        except Exception:
            print("🚫 No more 'Next' button found. Reached last page.")
            break

except Exception as e:
    print(f"❌ Error during scraping: {e}")

finally:
    driver.quit()

# --- SAVE TO CSV ---
with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["ID", "URL"])
    for i, link in enumerate(all_links, start=1):
        writer.writerow([i, link])

print(f"\n🎯 Done! Collected {len(all_links)} unique links across {page_count} pages and saved to {CSV_FILE}")
