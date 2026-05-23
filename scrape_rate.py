#!/usr/bin/env python3
"""
scrape_rate.py
Scrapes the MortgageNewsDaily.com 30-year fixed rate and writes rates.json.
Run by GitHub Actions daily. Output is read by the Verified Home LLC mobile app.
"""

import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

MND_URL = "https://www.mortgagenewsdaily.com/mortgage-rates/30-year-fixed"
OUTPUT_FILE = "rates.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_mnd_rate() -> float:
    """
    Fetch MND's 30-year fixed rate page and extract the current rate.
    Returns the rate as a float (e.g., 6.875).
    Raises ValueError if parsing fails.
    """
    resp = requests.get(MND_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # --- Strategy 1: Look for the large bold rate display (most reliable) ---
    # MND renders the current rate in a prominent element — try common patterns
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

    # --- Strategy 2: Search all text nodes for a rate-like pattern near "30" ---
    # MND page typically shows "30 Year Fixed  6.875%" in a structured section
    page_text = soup.get_text(" ")
    # Look for pattern like "30 Year Fixed ... 6.875" or "6.875%"
    matches = re.findall(r"\b([5-9]\.\d{2,3})\s*%?", page_text)
    if matches:
        # Return the first plausible rate value (between 5.0 and 9.99)
        for m in matches:
            val = float(m)
            if 5.0 <= val <= 9.99:
                return round(val, 3)

    raise ValueError("Could not parse a valid 30-year fixed rate from MND page.")


def _parse_rate(text: str):
    """Extract a numeric rate from a string like '6.875%' or '6.875'."""
    m = re.search(r"([5-9]\.\d{2,3})", text)
    if m:
        val = float(m.group(1))
        if 5.0 <= val <= 9.99:
            return round(val, 3)
    return None


def main():
    try:
        rate = scrape_mnd_rate()
    except Exception as e:
        print(f"ERROR: Failed to scrape MND rate: {e}", file=sys.stderr)
        sys.exit(1)

    payload = {
        "mnd_30y_fixed": rate,
        "source": "mortgagenewsdaily.com",
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"SUCCESS: Wrote {OUTPUT_FILE} → mnd_30y_fixed={rate}")


if __name__ == "__main__":
    main()
