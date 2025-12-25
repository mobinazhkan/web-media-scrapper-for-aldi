#!/usr/bin/env python3
"""
ALDI Thanksgiving category scraper
Outputs:
 - CSV:   output/aldi_thanksgiving_products.csv
 - SQLite: output/aldi_thanksgiving.db  (and a SQL dump output/aldi_thanksgiving.sql)
 - Images downloaded to: output/images/<Subcategory>/

Notes:
 - Install requirements: pip install requests beautifulsoup4 lxml tqdm
 - If site needs JS rendering, see selenium fallback notes below.
"""

import os
import csv
import json
import sqlite3
import time
from urllib.parse import urljoin, urlparse
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# CONFIG
BASE_DOMAIN = "https://www.aldi.us"
# Main Thanksgiving landing (subcategory list)
SEED_PAGES = [
    "https://www.aldi.us/products/thanksgiving/thanksgiving-desserts/k/257",

]
OUTPUT_DIR = "output"
CSV_PATH = os.path.join(OUTPUT_DIR, "aldi_thanksgiving_products.csv")
SQLITE_PATH = os.path.join(OUTPUT_DIR, "aldi_thanksgiving.db")
SQL_DUMP_PATH = os.path.join(OUTPUT_DIR, "aldi_thanksgiving.sql")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AldiScraper/1.0; +https://example.com/bot)"
}
REQUEST_DELAY = 0.8  # seconds between requests to be polite

# Ensure output dirs
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

session = requests.Session()
session.headers.update(HEADERS)


def get_soup(url):
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def find_product_links_from_listing(soup):
    """
    Scans a category/listing page for product links.
    Adjust selectors if ALDI structure differs.
    """
    links = set()
    # Look for product link elements (ALDI uses <a> with product href)
    for a in soup.select("a.product-list__link, a.product-list__title, a"):
        href = a.get("href", "")
        if href and "/products/" in href:
            full = urljoin(BASE_DOMAIN, href)
            links.add(full.split("?")[0])
    # Fallback: find links that include '/product/' or '/products/'
    for a in soup.find_all("a", href=True):
        if "/products/" in a['href']:
            links.add(urljoin(BASE_DOMAIN, a['href']).split("?")[0])
    return list(links)


def extract_product_data(product_url, parent_subcategory="Thanksgiving"):
    """
    Extract product fields from product page.
    """
    try:
        soup = get_soup(product_url)
    except Exception as e:
        print(f"[ERROR] failed to GET {product_url}: {e}")
        return None

    # Generic attempts to capture common fields. Adjust selectors when needed.
    def safe_text(sel):
        el = soup.select_one(sel)
        return el.get_text(strip=True) if el else ""

    title = safe_text("h1") or safe_text(".product-title") or safe_text(".page-title")
    price = safe_text(".product-price") or safe_text(".price") or ""
    unit_price = safe_text(".unit-price") or ""
    description = safe_text(".product-description") or safe_text(".short-description") or ""
    brand = safe_text(".brand") or ""
    sku = safe_text("[data-sku]") or ""
    # Try to find additional meta or json-ld structured data
    # JSON-LD
    jsonld = {}
    try:
        ld = soup.find("script", type="application/ld+json")
        if ld:
            jsonld = json.loads(ld.string or "{}")
    except Exception:
        jsonld = {}

    # collect images
    image_urls = set()
    for img in soup.select("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if src and src.strip():
            if src.startswith("//"):
                src = "https:" + src
            image_urls.add(urljoin(BASE_DOMAIN, src.split("?")[0]))

    # Some sites include gallery links in anchors
    for a in soup.select("a"):
        if any(ext in a.get("href", "").lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            image_urls.add(urljoin(BASE_DOMAIN, a['href'].split("?")[0]))

    # Use JSON-LD images if present
    if isinstance(jsonld, dict):
        imgs = jsonld.get("image") or jsonld.get("images")
        if isinstance(imgs, str):
            image_urls.add(urljoin(BASE_DOMAIN, imgs))
        elif isinstance(imgs, list):
            for ii in imgs:
                image_urls.add(urljoin(BASE_DOMAIN, str(ii)))

    data = {
        "title": title,
        "price": price,
        "unit_price": unit_price,
        "description": description,
        "brand": brand,
        "sku": sku,
        "category": "Thanksgiving",
        "subcategory": parent_subcategory,
        "product_url": product_url,
        "image_urls": list(image_urls),
        "crawl_timestamp": datetime.utcnow().isoformat() + "Z",
    }
    return data


def download_images_for_product(data):
    """
    Downloads images into IMAGES_DIR/<subcategory>/ with filenames <sku_or_slug>_<i>.<ext>
    """
    sub = data.get("subcategory") or "uncategorized"
    safe_sub = "".join(c if c.isalnum() or c in " _-" else "_" for c in sub)[:120]
    target_dir = os.path.join(IMAGES_DIR, safe_sub)
    os.makedirs(target_dir, exist_ok=True)
    saved_files = []
    sku_base = data.get("sku") or data.get("title") or "product"
    sku_base = "".join(c if c.isalnum() or c in "_-" else "_" for c in sku_base)[:60]

    for i, img_url in enumerate(data.get("image_urls", []), start=1):
        try:
            ext = os.path.splitext(urlparse(img_url).path)[1].split("?")[0] or ".jpg"
            filename = f"{sku_base}_{i}{ext}"
            path = os.path.join(target_dir, filename)
            if os.path.exists(path):
                saved_files.append(path)
                continue
            resp = session.get(img_url, stream=True, timeout=30)
            resp.raise_for_status()
            with open(path, "wb") as f:
                for chunk in resp.iter_content(1024 * 8):
                    if chunk:
                        f.write(chunk)
            saved_files.append(path)
            time.sleep(0.12)
        except Exception as e:
            print(f"[WARN] failed to download image {img_url}: {e}")
    return saved_files


def save_to_csv(rows, path):
    keys = ["id","title","price","unit_price","description","brand","sku","category","subcategory","product_url","image_urls","crawl_timestamp"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            row = {k: (json.dumps(r[k], ensure_ascii=False) if isinstance(r.get(k), (list,dict)) else r.get(k,"")) for k in keys}
            w.writerow(row)
    print(f"[OK] CSV saved to {path}")


def save_to_sqlite(rows, db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
          id TEXT PRIMARY KEY,
          title TEXT,
          price TEXT,
          unit_price TEXT,
          description TEXT,
          brand TEXT,
          sku TEXT,
          category TEXT,
          subcategory TEXT,
          product_url TEXT,
          image_urls TEXT,
          crawl_timestamp TEXT
        )
    """)
    for r in rows:
        c.execute("""
            INSERT OR REPLACE INTO products (id,title,price,unit_price,description,brand,sku,category,subcategory,product_url,image_urls,crawl_timestamp)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            r.get("id"),
            r.get("title"),
            r.get("price"),
            r.get("unit_price"),
            r.get("description"),
            r.get("brand"),
            r.get("sku"),
            r.get("category"),
            r.get("subcategory"),
            r.get("product_url"),
            json.dumps(r.get("image_urls", []), ensure_ascii=False),
            r.get("crawl_timestamp"),
        ))
    conn.commit()
    conn.close()
    # Dump SQL
    with sqlite3.connect(db_path) as conn:
        with open(SQL_DUMP_PATH, "w", encoding="utf-8") as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")
    print(f"[OK] SQLite DB saved to {db_path} and SQL dump to {SQL_DUMP_PATH}")


def main():
    discovered_products = {}
    # 1) Crawl seed pages and collect product links and subcategory context
    for seed in SEED_PAGES:
        try:
            soup = get_soup(seed)
        except Exception as e:
            print(f"[WARN] can't load seed {seed}: {e}")
            continue

        # attempt to determine a subcategory title from page
        subcat = ""
        h = soup.select_one("h1") or soup.select_one(".page-title")
        if h:
            subcat = h.get_text(strip=True)
        if not subcat:
            # fallback using last path segment
            subcat = seed.rstrip("/").split("/")[-1]

        links = find_product_links_from_listing(soup)
        print(f"[INFO] found {len(links)} product links on {seed} (subcategory='{subcat}')")
        for l in links:
            discovered_products[l] = subcat
        time.sleep(REQUEST_DELAY)

    # 2) Visit each product and extract details
    rows = []
    for idx, (purl, subcat) in enumerate(tqdm(list(discovered_products.items())), start=1):
        data = extract_product_data(purl, parent_subcategory=subcat or "Thanksgiving")
        if not data:
            continue
        data["id"] = f"aldi_thx_{idx}"
        # Ensure image_urls is list
        if not isinstance(data.get("image_urls"), list):
            data["image_urls"] = list(data.get("image_urls") or [])
        # download images
        imgs = download_images_for_product(data)
        data["downloaded_images"] = imgs
        rows.append(data)
        time.sleep(REQUEST_DELAY)

    # 3) Save CSV and SQLite
    save_to_csv(rows, CSV_PATH)
    save_to_sqlite(rows, SQLITE_PATH)

    print("[DONE] Scrape complete. Summary:")
    print(f" - Products: {len(rows)}")
    print(f" - CSV: {CSV_PATH}")
    print(f" - SQLite: {SQLITE_PATH}")
    print(f" - Images in: {IMAGES_DIR}")


if __name__ == "__main__":
    main()
