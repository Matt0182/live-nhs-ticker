#!/usr/bin/env python3
"""
Find the latest NHS England financial directions on GOV.UK and maintain
budgets.json.

The ticker uses the calendar year as its reset period. For each calendar
year, the updater records the latest available NHS England total revenue
resource use limit for the corresponding/current financial year.

If the next financial year's directions are not published yet, the current
year is left unchanged until GOV.UK publishes them.
"""
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "budgets.json"
COLLECTION = "https://www.gov.uk/government/collections/financial-directions-to-nhs-england"

HEADERS = {
    "User-Agent": "NHS-Ticker-Budget-Updater/1.0 (GitHub Actions)"
}

def get(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text

def parse_money_millions(text):
    # Prefer the exact sentence used in Annex A1.
    patterns = [
        r"total revenue resource use.*?does not exceed\s+£\s*([\d,]+)\s*million",
        r"total revenue resource use limit.*?£\s*([\d,]+)\s*million",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I | re.S)
        if m:
            return int(m.group(1).replace(",", "")) * 1_000_000
    raise RuntimeError("Could not find the total revenue resource use limit.")

def parse_years(title):
    m = re.search(r"(20\d{2})\s+to\s+(20\d{2})", title, flags=re.I)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))

def candidates():
    soup = BeautifulSoup(get(COLLECTION), "html.parser")
    found = {}
    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        href = urljoin("https://www.gov.uk", a["href"])
        years = parse_years(title)
        if years and "financial directions to nhs england" in title.lower():
            found[href] = {"title": title, "url": href, "years": years}
    return list(found.values())

def publication_date(html):
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"property": "article:published_time"})
    if meta and meta.get("content"):
        return meta["content"][:10]
    text = soup.get_text(" ", strip=True)
    m = re.search(r"Published\s+(\d{1,2}\s+\w+\s+20\d{2})", text)
    if m:
        return datetime.strptime(m.group(1), "%d %B %Y").date().isoformat()
    return "1900-01-01"

def main():
    items = candidates()
    if not items:
        raise RuntimeError("No NHS England financial-direction pages found.")

    enriched = []
    for item in items:
        html = get(item["url"])
        item["published"] = publication_date(html)
        item["amount"] = parse_money_millions(
            BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        )
        enriched.append(item)

    # Latest direction for each financial year, then latest financial year.
    by_start = {}
    for item in enriched:
        start, end = item["years"]
        old = by_start.get(start)
        if old is None or item["published"] > old["published"]:
            by_start[start] = item

    today_year = date.today().year

    # A calendar year maps to the financial year beginning in the previous
    # April, but for the January reset we use the financial-year direction
    # covering that calendar year. Thus Jan-Dec 2026 uses 2026/27.
    usable = [x for x in by_start.values() if x["years"][0] <= today_year]
    if not usable:
        raise RuntimeError("No suitable published budget found.")

    latest = max(usable, key=lambda x: x["years"][0])
    start, end = latest["years"]

    # Record the budget against its financial-year start/calendar reset year.
    data = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {
        "source": "NHS England financial directions published by DHSC on GOV.UK",
        "lastUpdated": None,
        "budgets": {}
    }

    data.setdefault("budgets", {})
    data["budgets"][str(start)] = {
        "financialYear": f"{start}/{str(end)[-2:]}",
        "amount": latest["amount"],
        "sourceUrl": latest["url"],
        "published": latest["published"]
    }
    data["lastUpdated"] = str(date.today())

    DATA.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )

    print(f"Saved {start}/{str(end)[-2:]}: £{latest['amount']:,}")
    print(f"Source: {latest['url']}")

if __name__ == "__main__":
    main()
