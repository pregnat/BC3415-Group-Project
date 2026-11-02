"""Fetch moomoo SG help-centre articles into rag/corpus/. OWNER: B.
Records every URL + fetch date in rag/corpus_manifest.csv.  Run: python -m rag.scrape"""
from __future__ import annotations

import csv
import re
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
CORPUS = ROOT / "corpus"
MANIFEST = ROOT / "corpus_manifest.csv"
BASE_URL = "https://www.moomoo.com/sg/support/topic5_{}"
HEADERS = {"User-Agent": "Mozilla/5.0 (student project; BC3415 margin assistant)"}
MANIFEST_FIELDS = ["chunk_source_file", "title", "url", "fetched_on", "product", "breadcrumb"]

# Product is set by hand and checked against the printed breadcrumbs. The other products have
# their own margin and close-out rules, so they are indexed to be filtered out, not to be cited
# in securities-margin answers.
TOPICS = {
    "securities_margin": [
        483, 484, 485, 486, 487, 488, 489, 490, 1165,  # Margin Trading > Introduction
        492, 493, 494, 495, 1446,  # Margin Trading > About Margin Calls
        124,  # asset field definitions (remaining liquidity etc.)
    ],
    "ipo_financing": [274],  # its "interest charges" are IPO financing, not margin interest
    "general": [1264],  # firm risk controls on orders, not margin rules
    "forex_cfd": [603, 604, 607, 897],
    "futures": [149, 150, 152],
    "options": [315],
}


def extract_body(body) -> str:
    """Article HTML -> plain text: one block per line, table rows as 'a | b'."""
    for table in body.find_all("table"):
        rows = [
            " | ".join(cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"]))
            for row in table.find_all("tr")
        ]
        table.replace_with("\n" + "\n".join(rows) + "\n")
    for br in body.find_all("br"):
        br.replace_with("\n")
    for block in body.find_all(["p", "li", "div", "h1", "h2", "h3", "h4", "h5", "h6"]):
        block.append("\n")
    # get_text("") keeps inline spans on one line; the help centre wraps product names in spans.
    lines = (re.sub(r"[ \t\xa0]+", " ", line).strip() for line in body.get_text("").splitlines())
    return "\n".join(line for line in lines if line)


def fetch_topic(topic_id: int) -> tuple[str, list[str], str]:
    """Returns (title, breadcrumb, body text). Raises if the page has no article body."""
    response = requests.get(BASE_URL.format(topic_id), headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    body = soup.select_one(".futu-richTextContent")
    if body is None:
        raise ValueError(f"topic5_{topic_id}: no article body")
    crumbs = [c.get_text(strip=True) for c in soup.select(".breadcrumb-text")]
    return soup.find("h1").get_text(strip=True), crumbs, extract_body(body)


def main():
    CORPUS.mkdir(exist_ok=True)
    rows = []
    for product, topic_ids in TOPICS.items():
        for topic_id in topic_ids:
            title, crumbs, text = fetch_topic(topic_id)
            filename = f"topic5_{topic_id}.txt"
            (CORPUS / filename).write_text(text + "\n", encoding="utf-8")
            rows.append({
                "chunk_source_file": filename,
                "title": title,
                "url": BASE_URL.format(topic_id),
                "fetched_on": date.today().isoformat(),
                "product": product,
                "breadcrumb": " > ".join(crumbs[1:-1]),
            })
            print(f"{product:18} {filename:18} {len(text):6} chars  {' > '.join(crumbs[1:-1])}")
            time.sleep(1)  # be polite to the site
    with MANIFEST.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} articles -> {MANIFEST}")


if __name__ == "__main__":
    main()
