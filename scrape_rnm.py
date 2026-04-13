"""
RNM (FranceAgriMer) scraper.

Downloads monthly average price files (.slk) from the RNM website.

Part 1: Products from 4 main categories (~300 products)
Part 2: Rungis market products from the collective catering page (15 products)
"""

import argparse
import os
import re
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://rnm.franceagrimer.fr"
PRIX_URL = f"{BASE_URL}/prix"

CATEGORY_PATHS = [
    "/prix?FRUITS-ET-LEGUMES",
    "/prix?PECHE-ET-AQUACULTURE",
    "/prix?BEURRE-OEUF-FROMAGE",
    "/prix?VIANDE",
]

RUNGIS_PAGE_URL = f"{BASE_URL}/rnm/panier_restau_co.shtml"

REQUEST_DELAY = 0.5

CATEGORY_CODES = {
    "LEGUMES",
    "FRUITS",
    "SALADES",
    "CHAMPIGNONS",
    "AGRUMES",
    "LEGUMES-ET-HERBES-AROMATIQUES",
    "LEGUMES-FRUITS-ET-GRAINES",
    "LEGUMES-TUBERCULES,-RACINES",
    "LEGUMES-VERTS,-TIGES",
    "LEGUMES-EXOTIQUES",
    "FRUITS-A-COQUE-ET-FRUITS-SECS",
    "FRUITS-FRAIS",
    "BAIES,-PETITS-FRUITS",
    "FRUITS-A-NOYAU",
    "FRUITS-A-PEPINS",
    "FRUITS-EXOTIQUES-ET-AUTRES",
    "POISSONS",
    "POISSONS-DE-MER",
    "POISSONS-D-EAU-DOUCE---SALMONIDES",
    "COQUILLAGES",
    "CRUSTACES",
    "CEPHALOPODES",
    "DIVERS-PECHE-AQUACULTURE",
    "FROMAGES",
    "DESSERTS-LACTES",
    "AUTRES-PRODUITS-LACTES",
    "BEURRE-ET-MARGARINE",
    "LAITS",
    "OEUFS",
    "PRODUITS-VEGETAUX-TRANSFORMES",
    "BOVINS",
    "OVINS",
    "PORCINS",
    "CAPRINS",
    "VOLAILLES",
    "GIBIERS",
}

EXCLUDE_PATTERNS = [
    "FRUITS-ET-LEGUMES",
    "PECHE-ET-AQUACULTURE",
    "BEURRE-OEUF-FROMAGE",
    "VIANDE",
    "SAINOMMAR",
    "SAINOMPRODUIT",
    "FLEURS",
    "MARCHES",
    "ACCES",
    "SURGELE",
]


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; RNM-Scraper/1.0)"})
    return s


def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", "_", name)
    return name


def is_category(href: str) -> bool:
    code = href.split("?")[1] if "?" in href else ""
    return code in CATEGORY_CODES


def extract_form_params(html: str, form_id: str = "tab") -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", id=form_id)
    if not form:
        return None
    params = {}
    for inp in form.find_all("input", type="hidden"):
        name = inp.get("name")
        if name:
            params[name] = inp.get("value", "")
    return params


def download_file(
    session: requests.Session, params: dict, output_dir: str, label: str
) -> bool:
    try:
        resp = session.post(PRIX_URL, data=params)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"    ERROR downloading {label}: {e}")
        return False

    content_disp = resp.headers.get("content-disposition", "")
    if "attachment" not in content_disp:
        print(f"    SKIP {label} (no file in response)")
        return False

    match = re.search(r"filename=(.+?)(?:$|;)", content_disp)
    ext = os.path.splitext(match.group(1).strip())[1] if match else ".slk"
    ext = ext or ".slk"
    filename = f"{sanitize_filename(label)}{ext}"

    with open(os.path.join(output_dir, filename), "wb") as f:
        f.write(resp.content)
    return True


# ── Part 1: Products from category pages ──────────────────────


def get_product_links(session: requests.Session, category_path: str) -> list[dict]:
    url = f"{BASE_URL}{category_path}"
    print(f"  Fetching products from {category_path}...")
    resp = session.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    products = []
    seen = set()
    for link in soup.select('a[href^="/prix?"]'):
        href = link.get("href", "")
        if "&" in href:
            continue
        if any(p in href.upper() for p in EXCLUDE_PATTERNS):
            continue
        if href in seen:
            continue
        seen.add(href)
        products.append({"name": link.get_text(strip=True), "href": href})
    return products


def download_product(session: requests.Session, product: dict, output_dir: str) -> bool:
    name = product["name"]
    href = product["href"]

    try:
        resp = session.get(f"{BASE_URL}{href}&12MOIS")
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"    ERROR fetching {name}: {e}")
        return False

    params = extract_form_params(resp.text)
    if not params or ("ESPECE" not in params and "MARCHE" not in params):
        print(f"    SKIP {name} (no download form)")
        return False

    return download_file(session, params, output_dir, name)


def scrape_products(session: requests.Session, output_dir: str) -> tuple[int, int]:
    all_products = []
    seen_hrefs = set()

    for path in CATEGORY_PATHS:
        for p in get_product_links(session, path):
            if p["href"] not in seen_hrefs and not is_category(p["href"]):
                seen_hrefs.add(p["href"])
                all_products.append(p)

    total = len(all_products)
    print(f"\n  Total products to process: {total}\n")

    success = 0
    for i, product in enumerate(all_products, 1):
        print(f"  [{i}/{total}] {product['name']}...", end=" ", flush=True)
        if download_product(session, product, output_dir):
            success += 1
            print("OK")
        time.sleep(REQUEST_DELAY)

    return success, total


# ── Part 2: Rungis products ───────────────────────────────────


def get_rungis_products(session: requests.Session) -> list[dict]:
    print("  Fetching Rungis products...")
    resp = session.get(RUNGIS_PAGE_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    products = []
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        onclick = link.get("onclick", "")
        if "Rungis" not in text and "rungis" not in text:
            continue
        match = re.search(r"marche_hebdo\((\d+),", onclick)
        if match:
            products.append({"name": text, "code": int(match.group(1))})
    return products


def download_rungis_product(
    session: requests.Session, name: str, code: int, output_dir: str
) -> bool:
    try:
        resp = session.post(PRIX_URL, data={"MENSUEL": "1", "MARCHE": str(code)})
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"    ERROR fetching {name}: {e}")
        return False

    params = extract_form_params(resp.text)
    if not params:
        print(f"    SKIP {name} (no download form)")
        return False

    return download_file(session, params, output_dir, name)


def scrape_rungis(session: requests.Session, output_dir: str) -> tuple[int, int]:
    products = get_rungis_products(session)
    total = len(products)
    print(f"\n  Total Rungis products: {total}\n")

    success = 0
    for i, product in enumerate(products, 1):
        print(f"  [{i}/{total}] {product['name']}...", end=" ", flush=True)
        if download_rungis_product(
            session, product["name"], product["code"], output_dir
        ):
            success += 1
            print("OK")
        time.sleep(REQUEST_DELAY)

    return success, total


# ── Main ──────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Download RNM monthly price data (.slk files)"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output",
        help="Root output directory (default: output)",
    )
    args = parser.parse_args()

    products_dir = os.path.join(args.output, "produits")
    rungis_dir = os.path.join(args.output, "rungis")
    os.makedirs(products_dir, exist_ok=True)
    os.makedirs(rungis_dir, exist_ok=True)

    session = build_session()

    print("=" * 60)
    print("PART 1: Downloading products (4 categories)")
    print("=" * 60)
    prod_ok, prod_total = scrape_products(session, products_dir)
    print(f"\n  Result: {prod_ok}/{prod_total} downloaded")

    print()
    print("=" * 60)
    print("PART 2: Downloading Rungis products")
    print("=" * 60)
    rungis_ok, rungis_total = scrape_rungis(session, rungis_dir)
    print(f"\n  Result: {rungis_ok}/{rungis_total} downloaded")

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Products : {prod_ok}/{prod_total} -> {products_dir}/")
    print(f"  Rungis   : {rungis_ok}/{rungis_total} -> {rungis_dir}/")
    print(f"  Total    : {prod_ok + rungis_ok} files downloaded")


if __name__ == "__main__":
    main()
