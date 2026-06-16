#!/usr/bin/env python3
"""
scrape_rate.py
Scrapes the MortgageNewsDaily.com 30-year and 15-year fixed rates and writes rates.json.
Run by GitHub Actions daily. Output is read by the Verified Home LLC mobile app.
"""
import json
import re
import sys
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

MND_30Y_URL = "https://www.mortgagenewsdaily.com/mortgage-rates/30-year-fixed"
MND_15Y_URL = "https://www.mortgagenewsdaily.com/mortgage-rates/15-year-fixed"
OUTPUT_FILE = "rates.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

def scrape_mnd_rate(url: str) -> float:
    """
    Fetch an MND rate page and extract the current rate.
    Returns the rate as a float (e.g., 6.875).
    Raises ValueError if parsing fails.
    """
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # --- Strategy 1: Look for the large bold rate display ---
    for selector in [
        "span.rate-value",
        "div.rate-value",
        "span.rateValue",
        "div.rateValue",
        ".current-rate",
        ".rate-number",
    ]:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(strip=True)
            rate = _parse_rate(text)
            if rate:
                return rate

    # --- Strategy 2: Search all text nodes for a rate-like pattern ---
    page_text = soup.get_text(" ")
    matches = re.findall(r"\b([3-9]\.\d{2,3})\s*%?", page_text)
    if matches:
        for m in matches:
            val = float(m)
            if 3.0 <= val <= 9.99:
                return round(val, 3)

    raise ValueError(f"Could not parse a valid rate from {url}")

def _parse_rate(text: str):
    """Extract a numeric rate from a string like '6.875%' or '6.875'."""
    m = re.search(r"([3-9]\.\d{2,3})", text)
    if m:
        val = float(m.group(1))
        if 3.0 <= val <= 9.99:
            return round(val, 3)
    return None

def main():
    # Scrape 30-year
    try:
        rate_30y = scrape_mnd_rate(MND_30Y_URL)
        print(f"SUCCESS: mnd_30y_fixed={rate_30y}")
    except Exception as e:
        print(f"ERROR: Failed to scrape 30Y rate: {e}", file=sys.stderr)
        sys.exit(1)

    # Scrape 15-year
    try:
        rate_15y = scrape_mnd_rate(MND_15Y_URL)
        print(f"SUCCESS: mnd_15y_fixed={rate_15y}")
    except Exception as e:
        print(f"ERROR: Failed to scrape 15Y rate: {e}", file=sys.stderr)
        sys.exit(1)

    payload = {
        "mnd_30y_fixed": rate_30y,
        "mnd_15y_fixed": rate_15y,
        "source": "mortgagenewsdaily.com",
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"SUCCESS: Wrote {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
