#!/usr/bin/env python3
"""
scrape_rate.py
Scrapes the MortgageNewsDaily.com 30-year and 15-year fixed rates and writes rates.json.
Run by GitHub Actions daily. Output is read by the Verified Home LLC mobile app + website.

Parsing is anchored to each product's own label ("30YR Fixed Rate", "15YR Fixed
Rate") rather than page position. MND renders a rate snapshot near the top of
every page where the 30yr rate appears first, so a position-based grab returned
the 30yr rate for both products. Anchoring on the label fixes that. Both rates
live in the same snapshot, so a single page fetch yields both.
"""
import json
import re
import sys
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

# Either product page contains the snapshot with BOTH rates; 30yr is primary,
# 15yr is a fallback source if the primary fetch ever fails.
PRIMARY_URL = "https://www.mortgagenewsdaily.com/mortgage-rates/30-year-fixed"
FALLBACK_URL = "https://www.mortgagenewsdaily.com/mortgage-rates/15-year-fixed"
OUTPUT_FILE = "rates.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _page_text(url: str) -> str:
    """Fetch a page and return its visible text with whitespace collapsed."""
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    text = BeautifulSoup(resp.text, "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", text)


def extract_rate(text: str, years: str) -> float:
    """
    Pull a fixed rate by its product label, e.g. '30YR Fixed Rate 6.54%'.
    Tolerant of 'YR' vs 'Yr.' and spacing. Returns a float or raises ValueError.
    """
    m = re.search(
        rf"{years}\s*YR\.?\s*Fixed\s*Rate\s*([3-9]\.\d{{2,3}})\s*%",
        text,
        re.IGNORECASE,
    )
    if not m:
        raise ValueError(f"Could not find a {years}YR Fixed rate label")
    val = round(float(m.group(1)), 3)
    if not 3.0 <= val <= 9.99:
        raise ValueError(f"{years}YR rate {val} outside sane range")
    return val


def main():
    try:
        text = _page_text(PRIMARY_URL)
        rate_30y = extract_rate(text, "30")
        rate_15y = extract_rate(text, "15")
    except Exception as e:
        print(f"WARN: primary parse failed ({e}); trying fallback page", file=sys.stderr)
        try:
            text = _page_text(FALLBACK_URL)
            rate_30y = extract_rate(text, "30")
            rate_15y = extract_rate(text, "15")
        except Exception as e2:
            print(f"ERROR: could not scrape rates: {e2}", file=sys.stderr)
            sys.exit(1)

    # Sanity guard: 15yr fixed should not exceed 30yr fixed, and the two should
    # not be identical (the exact symptom of the old position-based bug).
    if rate_15y >= rate_30y:
        print(
            f"ERROR: suspicious rates 30yr={rate_30y} 15yr={rate_15y} "
            f"(15yr should be below 30yr); refusing to write.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"SUCCESS: mnd_30y_fixed={rate_30y} mnd_15y_fixed={rate_15y}")

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
