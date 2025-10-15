import re
import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# --- CONFIG ---
URLS = [
    "https://dap-news.com/sport/2025/09/17/537427/",
    "https://dap-news.com/sport/2025/10/09/543389/",
    "https://dap-news.com/sport/2019/10/25/1887/",
]
WAIT_TIME = 15
CSV_FILE = "khmer_content.csv"

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

# --- REGEX for Khmer ---
khmer_pattern = re.compile(r"[\u1780-\u17FF]+")

with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["ID", "Khmer_Text"])  # CSV header

    unqiue_id = 1

    for URL in URLS:
        print(f"Opening {URL} ...")
        driver.get(URL)

        try:
            # Wait for main content
            WebDriverWait(driver, WAIT_TIME).until(
                EC.presence_of_element_located((By.ID, "content-main"))
            )
            time.sleep(2)

            # Parse HTML
            soup = BeautifulSoup(driver.page_source, "html.parser")

            # Extract paragraphs under #content-main
            content_div = soup.select_one("div#content-main")
            paragraphs = (
                [p.get_text(strip=True) for p in content_div.find_all("p")]
                if content_div
                else []
            )

            khmer_paragraphs = [p for p in paragraphs if khmer_pattern.search(p)]

            if khmer_paragraphs:
                for text in khmer_paragraphs:
                    writer.writerow([unqiue_id, text])
                    unqiue_id += 1

                print(f"✅ Article {unqiue_id} saved.")
            else:
                print(f"⚠️ No Khmer text found for {URL}")

        except Exception as e:
            print(f"❌ Error scraping {URL}: {e}")
            continue

driver.quit()
print(f"\n🎯 Done! Wrote all Khmer content to {CSV_FILE}")
