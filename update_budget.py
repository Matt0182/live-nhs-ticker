import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "budgets.json"

COLLECTION = (
    "https://www.gov.uk/government/collections/"
    "financial-directions-to-nhs-england"
)

HEADERS = {
    "User-Agent": "NHS-Ticker-Budget-Updater/1.0"
}


def get(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def parse_years(title):
    match = re.search(
        r"(20\d{2})\s+to\s+(20\d{2})",
        title,
        re.IGNORECASE
    )

    if not match:
        return None

    return int(match.group(1)), int(match.group(2))


def parse_amount(text):
    patterns = [
        r"total revenue resource use limit.*?"
        r"which is\s+£\s*([\d,]+)\s*million",

        r"total revenue resource use.*?"
        r"does not exceed\s+£\s*([\d,]+)\s*million",

        r"total revenue resource use limit.*?"
        r"£\s*([\d,]+)\s*million",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL
        )

        if match:
            return (
                int(match.group(1).replace(",", ""))
                * 1_000_000
            )

    raise RuntimeError(
        "Could not find the total revenue resource use limit "
        "on this GOV.UK page."
    )


def publication_date(html):
    soup = BeautifulSoup(html, "html.parser")

    meta = soup.find(
        "meta",
        attrs={"property": "article:published_time"}
    )

    if meta and meta.get("content"):
        return meta["content"][:10]

    text = soup.get_text(" ", strip=True)

    match = re.search(
        r"Published\s+(\d{1,2}\s+\w+\s+20\d{2})",
        text
    )

    if match:
        return datetime.strptime(
            match.group(1),
            "%d %B %Y"
        ).date().isoformat()

    return "1900-01-01"


def find_pages():
    soup = BeautifulSoup(get(COLLECTION), "html.parser")

    pages = {}

    for link in soup.find_all("a", href=True):
        title = link.get_text(" ", strip=True)
        years = parse_years(title)

        if (
            years
            and "financial directions to nhs england"
            in title.lower()
        ):
            url = urljoin(
                "https://www.gov.uk",
                link["href"]
            )

            pages[url] = {
                "title": title,
                "url": url,
                "years": years
            }

    return list(pages.values())


def main():
    candidates = find_pages()

    if not candidates:
        raise RuntimeError(
            "No NHS England financial-direction pages found."
        )

    by_start = {}

    for item in candidates:
        html = get(item["url"])

        item["published"] = publication_date(html)

        text = BeautifulSoup(
            html,
            "html.parser"
        ).get_text(" ", strip=True)

        item["amount"] = parse_amount(text)

        start, end = item["years"]

        existing = by_start.get(start)

        if (
            existing is None
            or item["published"] > existing["published"]
        ):
            by_start[start] = item

    today = date.today()
    current_year = today.year

    data = json.loads(
        DATA.read_text(encoding="utf-8")
    )

    data.setdefault("budgets", {})

    # Each calendar year gets a stable 1 January snapshot.
    if str(current_year) not in data["budgets"]:

        usable = [
            item
            for item in by_start.values()
            if item["years"][0] <= current_year
        ]

        if not usable:
            raise RuntimeError(
                "No suitable published NHS budget found."
            )

        latest = max(
            usable,
            key=lambda item: (
                item["years"][0],
                item["published"]
            )
        )

        start, end = latest["years"]

        data["budgets"][str(current_year)] = {
            "financialYear": (
                f"{start}/{str(end)[-2:]}"
            ),
            "amount": latest["amount"],
            "sourceUrl": latest["url"],
            "published": latest["published"],
            "snapshotDate": (
                f"{current_year}-01-01"
            )
        }

    # Prepare the next year's snapshot if its
    # financial directions have already been published.
    next_year = current_year + 1

    future = [
        item
        for item in by_start.values()
        if item["years"][0] == next_year
    ]

    if (
        str(next_year) not in data["budgets"]
        and future
    ):
        latest = max(
            future,
            key=lambda item: item["published"]
        )

        start, end = latest["years"]

        data["budgets"][str(next_year)] = {
            "financialYear": (
                f"{start}/{str(end)[-2:]}"
            ),
            "amount": latest["amount"],
            "sourceUrl": latest["url"],
            "published": latest["published"],
            "snapshotDate": (
                f"{next_year}-01-01"
            )
        }

    data["lastUpdated"] = str(today)

    DATA.write_text(
        json.dumps(
            data,
            indent=2,
            sort_keys=True
        ) + "\n",
        encoding="utf-8"
    )

    print("Budget data updated successfully.")


if __name__ == "__main__":
    main()
