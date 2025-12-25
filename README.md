A Python web scraper for collecting product data from the **ALDI Thanksgiving** category.

This script crawls ALDI product pages, extracts detailed product information, downloads product images, and saves the results in multiple formats for further analysis or storage.

---

## Features

- Scrapes product data from ALDI Thanksgiving category pages
- Extracts:
  - Product title
  - Price & unit price
  - Description
  - Brand & SKU
  - Category & subcategory
  - Product URL
  - Image URLs
- Downloads all product images
- Outputs data in:
  - CSV file
  - SQLite database
  - SQL dump file
- Polite crawling with request delays
- Uses JSON-LD data when available
- output/
├── aldi_thanksgiving_products.csv
├── aldi_thanksgiving.db
├── aldi_thanksgiving.sql
└── images/
└── <Subcategory>/
├── product_1.jpg
├── product_2.jpg
└── ...

---

## Requirements

Install dependencies before running the script:

pip install requests beautifulsoup4 lxml tqdm

## Run the scraper with:
python scrapper.py

## The script will automatically:
Crawl the configured Thanksgiving category pages
Extract product data
Download images
Save everything inside the output/ directory
Configuration
You can modify these variables inside the script:
SEED_PAGES → ALDI category URLs to scrape
REQUEST_DELAY → Delay between requests (default: 0.8s)
OUTPUT_DIR → Output folder location
Notes
This scraper uses requests + BeautifulSoup.
If ALDI changes their website structure, selectors may need adjustments.
If the website requires JavaScript rendering in the future, a Selenium-based fallback can be added.

## Disclaimer

This project is for educational purposes only.
Please respect ALDI's terms of service and robots.txt when scraping.

## Author
Mobin Azhkan
---

