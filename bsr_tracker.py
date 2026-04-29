from playwright.sync_api import sync_playwright
from datetime import datetime
import pandas as pd
import re

ASINS = [
    "B0D9JQ33BX","B0D1MYMVCC","B0CSZDC243","B0D3XXZRRC","B0D3XXY1HV",
    "B0G43ZNNRX","B0D97NFBG2","B0D9B6HKC8","B0D986WRQY","B0D9D6QJKD",
    "B0D9DRYQSH","B0FPDF7GQV","B0DXP99LNN","B0F61TRMXM","B0DTKGRKC2",
    "B0DS5HPJ1M","B0FJ8TFSZ1","B0G4GQL5TG","B0G5Z47WY7","B0D2HQ2N8G",
    "B0CVNHV3CV","B0D429W5H1","B0D429WWSQ","B0D22PKCGW","B0CTPR6KZ4"
]

# -----------------------------
# CLEAN TITLE
# -----------------------------
def clean_title(title):
    return re.split(r"[:：]", title)[0].strip()

# -----------------------------
# BSR EXTRACTION
# -----------------------------
def extract_bsr(text):
    match = re.search(r"#([\d,]+)\s+in", text)
    if match:
        return int(match.group(1).replace(",", ""))
    return None

# -----------------------------
# CATEGORY EXTRACTION
# -----------------------------
def extract_category_ranks(page):
    try:
        bsr_block = page.locator("#detailBulletsWrapper_feature_div").inner_text()
        lines = bsr_block.split("\n")

        categories = []

        for line in lines:
            if "#" in line and "in" in line:
                parts = line.split(" in ")
                if len(parts) == 2:
                    rank_part = parts[0]
                    category_part = parts[1]

                    rank = int(''.join(filter(str.isdigit, rank_part)))

                    categories.append({
                        "rank": rank,
                        "category": category_part.strip()
                    })

        return categories

    except:
        return []

# -----------------------------
# TITLE EXTRACTION (ROBUST)
# -----------------------------
def get_title(page, asin):
    title = None

    for attempt in range(3):
        try:
            page.wait_for_timeout(3000)

            # 1. productTitle
            el = page.query_selector("#productTitle")
            if el:
                title = el.inner_text().strip()

            # 2. og:title fallback
            if not title:
                og = page.query_selector('meta[property="og:title"]')
                if og:
                    title = og.get_attribute("content").strip()

            # 3. h1 fallback
            if not title:
                h1 = page.query_selector("h1")
                if h1:
                    title = h1.inner_text().strip()

            if title:
                return clean_title(title)

            raise Exception("No title found")

        except:
            print(f"Retry {attempt+1} for {asin} (title)")
            page.reload()
            page.wait_for_timeout(5000)

    return None

# -----------------------------
# SCRAPER
# -----------------------------
def scrape():
    data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )

        for asin in ASINS:
            print("START ASIN:", asin, flush=True)

            try:
                url = f"https://www.amazon.com/dp/{asin}"

                page.goto(url, timeout=60000)
                page.wait_for_timeout(8000)

                # light interaction
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(1000)
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(1000)

                # -----------------------------
                # TITLE (FIXED BLOCK)
                # -----------------------------
                title = get_title(page, asin)

                if not title:
                    print(f"FAILED to load {asin}", flush=True)
                    continue

                # -----------------------------
                # BSR + CATEGORY
                # -----------------------------
                bsr = extract_bsr(page.inner_text("body"))
                categories = extract_category_ranks(page)

                if categories:
                    for c in categories:
                        data.append({
                            "timestamp": datetime.now(),
                            "asin": asin,
                            "title": title,
                            "bsr": bsr,
                            "category": c["category"],
                            "category_rank": c["rank"]
                        })
                else:
                    data.append({
                        "timestamp": datetime.now(),
                        "asin": asin,
                        "title": title,
                        "bsr": bsr,
                        "category": None,
                        "category_rank": None
                    })

                print("DONE:", asin, "BSR:", bsr, "Categories:", len(categories), flush=True)

            except Exception as e:
                print(f"ERROR on {asin}: {e}", flush=True)
                continue

        browser.close()

    return data

# -----------------------------
# SAVE
# -----------------------------
def save(data):
    df = pd.DataFrame(data)

    try:
        old = pd.read_csv("bsr_data.csv")
        df = pd.concat([old, df], ignore_index=True)
    except FileNotFoundError:
        pass

    df = df.drop_duplicates(subset=["timestamp", "asin", "category", "category_rank", "bsr"])

    df.to_csv("bsr_data.csv", index=False)
    print("Saved to CSV")

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    data = scrape()
    save(data)
