from playwright.sync_api import sync_playwright
from datetime import datetime
import pandas as pd
import re
import random
import time

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
        text = page.inner_text("body")

        categories = []
        matches = re.findall(r"#([\d,]+)\s+in\s+([^\n(]+)", text)

        for rank, cat in matches:
            categories.append({
                "rank": int(rank.replace(",", "")),
                "category": cat.strip()
            })

        return categories

    except:
        return []

# -----------------------------
# TITLE EXTRACTION (FLEXIBLE)
# -----------------------------
def get_title(page, asin):
    try:
        # try multiple sources WITHOUT strict waits
        selectors = ["#productTitle", "span#productTitle", "h1"]

        for sel in selectors:
            el = page.query_selector(sel)
            if el:
                txt = el.inner_text().strip()
                if txt:
                    return clean_title(txt)

        # og:title fallback
        og = page.query_selector('meta[property="og:title"]')
        if og:
            content = og.get_attribute("content")
            if content:
                return clean_title(content.strip())

    except:
        pass

    print(f"FAILED TITLE: {asin}", flush=True)
    return None

# -----------------------------
# SCRAPER
# -----------------------------
def scrape():
    data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )

        page = context.new_page()

        for asin in ASINS:
            print("START ASIN:", asin, flush=True)

            try:
                url = f"https://www.amazon.com/dp/{asin}"
                page.goto(url, timeout=60000)

                # RANDOM delay (huge for avoiding blocks)
                time.sleep(random.uniform(5, 9))

                # light human-like behavior
                page.mouse.wheel(0, random.randint(1500, 3000))
                time.sleep(random.uniform(1, 2))

                # -----------------------------
                # TITLE
                # -----------------------------
                title = get_title(page, asin)

                if not title:
                    continue

                # -----------------------------
                # BSR + CATEGORY
                # -----------------------------
                body_text = page.inner_text("body")

                # detect bot block page
                if "captcha" in body_text.lower():
                    print(f"BLOCKED by Amazon on {asin}", flush=True)
                    continue

                bsr = extract_bsr(body_text)
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

                # delay between ASINs (VERY important)
                time.sleep(random.uniform(4, 8))

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

    # fix .0 issue
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
