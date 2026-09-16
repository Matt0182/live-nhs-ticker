# Live NHS Ticker

A mobile-friendly NHS England budget ticker.

## How it works

- The ticker resets to £0 at midnight on 1 January each year.
- It calculates a per-second rate from the annual NHS England total revenue resource use limit.
- `update_budget.py` checks the official GOV.UK collection for the latest NHS England financial directions.
- GitHub Actions runs the updater weekly and can also be run manually.
- `budgets.json` contains the official figure and source URL used by the webpage.

## Important interpretation

This is a calculated allocation rate, not a measurement of actual NHS spending in real time.

The official NHS England budget is set on a financial-year basis (April–March), while this visualisation resets on 1 January. The page therefore explicitly identifies the financial-year budget used.

## GitHub Pages

Enable GitHub Pages for the repository and select the `main` branch and `/ (root)` as the source.

The site will then be available at your GitHub Pages URL.

## Files

- `index.html` — ticker
- `budgets.json` — current researched budget data
- `update_budget.py` — GOV.UK researcher/updater
- `.github/workflows/update-budget.yml` — weekly automation
