# RNM Scraper

Scrapes monthly average price data from [RNM FranceAgriMer](https://rnm.franceagrimer.fr/) and saves it as `.slk` spreadsheet files (compatible with Excel, LibreOffice, etc.).

## What it downloads

| Part | Source | Products | Output folder |
|------|--------|----------|---------------|
| 1 | 4 category pages (Fruits & Légumes, Pêche & Aquaculture, Beurre Oeuf Fromage, Viande) | ~300 | `output/RNM General/` |
| 2 | [Restauration collective page](https://rnm.franceagrimer.fr/rnm/panier_restau_co.shtml) — Rungis markets only | 15 | `output/RNM Frozen/` |

For each product, the script fetches the **12-month history** then downloads the **monthly averages** spreadsheet.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Default output to ./output/
python scrape_rnm.py

# Custom output directory
python scrape_rnm.py -o /path/to/data

# Adjust parallelism (default: 8 threads)
python scrape_rnm.py -w 4
```

Downloads run in parallel (8 threads by default), so the script completes in under a minute.

## Filenames

Output filenames are ASCII-only: accented characters are stripped (e.g. `Crème_fraîche` → `Creme_fraiche`). Double-encoded UTF-8 names (Rungis source) are handled automatically.

## Automation

This repository includes a GitHub Actions workflow that runs the scraper on the **15th of every month at 9:00 AM UTC** and commits the updated files automatically.

You can also trigger it manually from the Actions tab → `Monthly RNM Scrape` → `Run workflow`.

## Output format

Files are downloaded in `.slk` (SYLK) format, which can be opened directly in Excel or LibreOffice Calc.
