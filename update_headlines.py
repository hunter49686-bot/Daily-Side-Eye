import argparse
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import requests

HEADLINES_PATH = "headlines.json"

GOOGLE_NEWS_BASE = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
USER_AGENT = "DailySideEyeBot/1.0 (+https://dailysideeye.com)"

# Conservative promo/ad filter (you can tune this list later)
PROMO_PATTERNS = [
    r"\bsponsored\b",
    r"\badvertisement\b",
    r"\bpromo\b",
    r"\bpromotion\b",
    r"\bcoupon\b",
    r"\bdeal\b",
    r"\bdeals\b",
    r"\bshopping\b",
    r"\bsubscribe\b",
    r"\bsubscription\b",
    r"\bpartner content\b",
]
PROMO_RE = re.compile("|".join(PROMO_PATTERNS), re.IGNORECASE)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def google_news_rss(query: str) -> str:
    return GOOGLE_NEWS_BASE.format(q=quote_plus(query))

def fetch_feed(url: str, timeout: int = 20):
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return feedparser.parse(r.content)

def normalize_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip())

def is_promo(title: str) -> bool:
    return bool(PROMO_RE.search(title or ""))

def items_from_feed(parsed, source_name: str, max_items: int):
    items = []
    for e in parsed.entries[: max_items * 3]:  # pull extra then filter/dedupe
        title = normalize_title(getattr(e, "title", ""))
        link = getattr(e, "link", None)

        if not title or not link:
            continue
        if is_promo(title):
            continue

        # Keep a stable minimal schema for the frontend
        items.append({
            "title": title,
            "url": link,
            "source": source_name,
        })

        if len(items) >= max_items:
            break

    return items

def dedupe(items):
    seen = set()
    out = []
    for it in items:
        key = (it.get("title", "").lower(), it.get("url", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

def load_existing():
    if not os.path.exists(HEADLINES_PATH):
        return {
            "meta": {"generated_at": None, "version": 2},
            "sections": {
                "breaking": [],
                "policy": [],
                "money": [],
                "tech": [],
                "weird": [],
            },
        }
    with open(HEADLINES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save(data):
    data["meta"]["generated_at"] = now_iso()
    if "version" not in data.get("meta", {}):
        data["meta"]["version"] = 2
    with open(HEADLINES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- FEED CONFIG (your locked choices) ---
# Note: You asked for Google News RSS. This uses site: queries.
# when: operator is commonly supported in Google News queries; it is not guaranteed to be strictly enforced,
# but it helps bias recency.
CONFIG = {
    "breaking": {
        "limit": 7,  # hard cap
        "feeds": [
            ("Reuters", google_news_rss("site:reuters.com when:1d -inurl:/video -inurl:/graphics")),
            ("AP",      google_news_rss("site:apnews.com when:1d")),
            ("Fox News",google_news_rss("site:foxnews.com when:1d")),
            ("NY Post", google_news_rss("site:nypost.com when:1d")),
        ],
    },
    "policy": {
        "limit": 20,
        "feeds": [
            ("Guardian",  google_news_rss("site:theguardian.com (policy OR politics OR government) when:2d")),
            ("Examiner",  google_news_rss("site:washingtonexaminer.com/section/policy when:7d")),
        ],
    },
    "money": {
        "limit": 20,
        "feeds": [
            ("WSJ",       google_news_rss("site:wsj.com (markets OR economy OR finance OR stocks) when:2d")),
            ("Bloomberg", google_news_rss("site:bloomberg.com (markets OR economy OR finance OR stocks) when:2d")),
        ],
    },
    "tech": {
        "limit": 20,
        "feeds": [
            ("Hacker News", "https://news.ycombinator.com/rss"),
            ("The Verge",   google_news_rss("site:theverge.com when:2d")),
        ],
    },
    "weird": {
        "limit": 20,
        "feeds": [
            ("Reuters OddlyEnough", google_news_rss("site:reuters.com ('oddly enough' OR oddly) when:14d -inurl:/video")),
            ("Atlas Obscura",       google_news_rss("site:atlasobscura.com when:30d")),
            ("Reuters Bizarre",     google_news_rss("site:reuters.com (bizarre OR strange OR unusual) when:14d -inurl:/video")),
        ],
    },
}

def update_section(data, section: str):
    cfg = CONFIG[section]
    combined = []

    for source_name, url in cfg["feeds"]:
        parsed = fetch_feed(url)
        combined.extend(items_from_feed(parsed, source_name, max_items=cfg["limit"]))

    combined = dedupe(combined)
    data["sections"][section] = combined[: cfg["limit"]]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", required=True, choices=list(CONFIG.keys()))
    args = ap.parse_args()

    data = load_existing()

    # Ensure Top is gone forever
    if "top" in data.get("sections", {}):
        del data["sections"]["top"]

    # Ensure required section keys exist
    data.setdefault("meta", {})
    data.setdefault("sections", {})
    for k in ["breaking", "policy", "money", "tech", "weird"]:
        data["sections"].setdefault(k, [])

    update_section(data, args.section)
    save(data)

if __name__ == "__main__":
    main()
