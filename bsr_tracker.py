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
# TITLE EXTRACTION
# -----------------------------
def get_title(page, asin):
    for attempt in range(3):
        try:
            page.wait_for_selector(
                "#productTitle, span#productTitle, h1",
                timeout=20000
            )

            title = None

            for sel in ["#productTitle", "span#productTitle", "h1"]:
                el = page.query_selector(sel)
                if el:
                    text = el.inner_text().strip()
                    if text:
                        title = text
                        break

            if not title:
                og = page.query_selector('meta[property="og:title"]')
                if og:
                    content = og.get_attribute("content")
                    if content:
                        title = content.strip()

            if title:
                return clean_title(title)

            raise Exception("No title found")

        except:
            print(f"Retry {attempt+1} for {asin} (title)", flush=True)
            page.reload()
            page.wait_for_timeout(6000)

    return None

# -----------------------------
# BSR EXTRACTION (ROBUST)
# -----------------------------
def get_bsr_and_categories(page, asin):
    for attempt in range(2):
        try:
            # wait specifically for BSR container
            page.wait_for_selector("#detailBulletsWrapper_feature_div", timeout=15000)

            body_text = page.inner_text("body")
            bsr = extract_bsr(body_text)
            categories = extract_category_ranks(page)

            if bsr or categories:
                return bsr, categories

            raise Exception("BSR not found")

        except:
            print(f"Retry {attempt+1} for {asin} (BSR)", flush=True)
            page.reload()
            page.wait_for_timeout(8000)

    return None, []

# -----------------------------
# SCRAPER
# -----------------------------
def scrape():
    data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        for asin in ASINS:
            print("START ASIN:", asin, flush=True)

            try:
                url = f"https://www.amazon.com/dp/{asin}"
                page.goto(url, timeout=60000)

                page.wait_for_timeout(12000)

                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(1000)
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(1000)

                # TITLE
                title = get_title(page, asin)
                if not title:
                    print(f"FAILED TITLE: {asin}", flush=True)
                    continue

                # BSR + CATEGORY (NEW ROBUST LOGIC)
                bsr, categories = get_bsr_and_categories(page, asin)

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

    # fix numeric formatting
    if "bsr" in df.columns:
        df["bsr"] = pd.to_numeric(df["bsr"], errors="coerce").astype("Int64")

    if "category_rank" in df.columns:
        df["category_rank"] = pd.to_numeric(df["category_rank"], errors="coerce").astype("Int64")

    df.to_csv("bsr_data.csv", index=False)
    print("Saved to CSV")

# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    data = scrape()
    save(data)
