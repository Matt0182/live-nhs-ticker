import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "budgets.json"

HEADERS = {
    "User-Agent": "Live-NHS-Ticker/1.0"
}

# Official GOV.UK collection
COLLECTION_URL = (
    "https://www.gov.uk/government/collections/"
    "financial-directions-to-nhs-england"
)


def get_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()
    return response.text


def get_text(html):
    soup = BeautifulSoup(
        html,
        "html.parser"
    )
    return soup.get_text(" ", strip=True)


def find_budget_amount(text):
    text = re.sub(r"\s+", " ", text.replace("\xa0", " "))

    patterns = [
        re.compile(
            r"total\s+revenue\s+resource\s+use"
            r".*?"
            r"(?:does\s+not\s+exceed|"
            r"limit(?:\s+is|\s+of)?|"
            r"amount(?:\s+is|\s+of)?|"
            r"of)"
            r"\s*£\s*([\d,.]+)\s*(million|billion)",
            re.IGNORECASE | re.DOTALL
        ),
        re.compile(
            r"revenue\s+resource\s+use.{0,250}?"
            r"£\s*([\d,.]+)\s*(million|billion)",
            re.IGNORECASE | re.DOTALL
        ),
    ]

    for pattern in patterns:
        match = pattern.search(text)

        if match:
            value = Decimal(match.group(1).replace(",", ""))
            multiplier = (
                1_000_000
                if match.group(2).lower() == "million"
                else 1_000_000_000
            )
            return int(value * multiplier)

    return None


def find_published_date(text):
    match = re.search(
        r"Published\s+(\d{1,2}\s+\w+\s+20\d{2})",
        text,
        re.IGNORECASE
    )

    if match:
        return datetime.strptime(
            match.group(1),
            "%d %B %Y"
        ).date().isoformat()

    return str(date.today())


def find_year(title):
    match = re.search(
        r"(20\d{2})\s+to\s+(20\d{2})",
        title,
        re.IGNORECASE
    )

    if match:
        return (
            int(match.group(1)),
            int(match.group(2))
        )

    return None


def find_latest_budget():
    collection_html = get_page(
        COLLECTION_URL
    )

    soup = BeautifulSoup(
        collection_html,
        "html.parser"
    )

    candidates = []

    for link in soup.find_all(
        "a",
        href=True
    ):
        title = link.get_text(
            " ",
            strip=True
        )

        years = find_year(title)

        if not years:
            continue

        if (
            "financial directions to nhs england"
            not in title.lower()
        ):
            continue

        url = link["href"]

        if url.startswith("/"):
            url = (
                "https://www.gov.uk"
                + url
            )

        candidates.append(
            (
                years,
                title,
                url
            )
        )

    if not candidates:
        raise RuntimeError(
            "No NHS England financial direction pages "
            "were found on GOV.UK."
        )

    current_year = date.today().year

    # Prefer the most recent financial year that
    # has already started or is the current calendar year.
    usable = [
        item
        for item in candidates
        if item[0][0] <= current_year
    ]

    if not usable:
        raise RuntimeError(
            "No suitable NHS England budget page found."
        )

    # Most recent financial year first.
    usable.sort(
        key=lambda item: item[0][0],
        reverse=True
    )

    checked_urls = []

    for years, title, url in usable:
        html = get_page(url)
        text = get_text(html)
        amount = find_budget_amount(text)

        if amount is not None:
            published = find_published_date(text)

            return {
                "financialYear": (
                    f"{years[0]}/{str(years[1])[-2:]}"
                ),
                "amount": amount,
                "sourceUrl": url,
                "published": published,
                "snapshotDate": (
                    f"{current_year}-01-01"
                )
            }

        checked_urls.append(url)

    raise RuntimeError(
        "Budget amount not found on any suitable GOV.UK NHS England "
        "financial direction page. Checked: "
        + ", ".join(checked_urls)
    )


def main():
    today = date.today()
    current_year = today.year

    data = json.loads(
        DATA.read_text(
            encoding="utf-8"
        )
    )

    data.setdefault(
        "budgets",
        {}
    )

    year_key = str(current_year)

    # Do not overwrite an existing year's snapshot.
    # This keeps the rate fixed from 1 January.
    if year_key not in data["budgets"]:
        budget = find_latest_budget()

        data["budgets"][year_key] = budget

        print(
            "Created budget snapshot for "
            f"{current_year}: "
            f"{budget['financialYear']} "
            f"£{budget['amount']:,}"
        )
    else:
        print(
            f"Budget snapshot for {current_year} "
            "already exists; leaving it unchanged."
        )

    data["lastUpdated"] = str(today)

    DATA.write_text(
        json.dumps(
            data,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    print(
        "Budget data updated successfully."
    )


if __name__ == "__main__":
    main()
