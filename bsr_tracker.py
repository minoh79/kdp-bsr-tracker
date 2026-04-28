from playwright.sync_api import sync_playwright
from datetime import datetime
import pandas as pd
import re

ASINS = [
    "B0D9JQ33BX",
    "B0D1MYMVCC",
    "B0CSZDC243",
    "B0D3XXZRRC",
    "B0D3XXY1HV",
    "B0G43ZNNRX",
    "B0D97NFBG2",
    "B0D9B6HKC8",
    "B0D986WRQY",
    "B0D9D6QJKD",
    "B0D9DRYQSH",
    "B0FPDF7GQV",
    "B0DXP99LNN",
    "B0F61TRMXM",
    "B0DTKGRKC2",
    "B0DS5HPJ1M",
    "B0FJ8TFSZ1",
    "B0G4GQL5TG",
    "B0G5Z47WY7",
    "B0D2HQ2N8G",
    "B0CVNHV3CV",
    "B0D429W5H1",
    "B0D429WWSQ",
    "B0D22PKCGW",
    "B0CTPR6KZ4"
]


def extract_bsr(text):
    match = re.search(r"#([\d,]+)\s+in", text)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


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


def scrape():
    data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        for asin in ASINS:
            url = f"https://www.amazon.com/dp/{asin}"
            page.goto(url)

            # let page load
            page.wait_for_timeout(8000)

            # scroll to trigger full load
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(1000)
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(1000)

            # ensure title exists
            page.wait_for_selector("#productTitle", timeout=60000)
            title = page.locator("#productTitle").inner_text()

            # BSR (overall rank)
            bsr = extract_bsr(page.content())

            # CATEGORY RANKS
            categories = extract_category_ranks(page)

            # ✅ LONG FORMAT OUTPUT (IMPORTANT CHANGE)
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

            print("ASIN:", asin, "BSR:", bsr, "Categories:", len(categories))

        browser.close()

    return data


def save(data):
    df = pd.DataFrame(data)

    try:
        old = pd.read_csv("bsr_data.csv")
        df = pd.concat([old, df], ignore_index=True)
    except FileNotFoundError:
        pass

    df.to_csv("bsr_data.csv", index=False)
    print("Saved to CSV")


if __name__ == "__main__":
    data = scrape()
    save(data)