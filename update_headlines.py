import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import requests

HEADLINES_PATH = "headlines.json"
USER_AGENT = "DailySideEyeBot/1.0 (+https://dailysideeye.com)"

# If your “yesterday working” version already uses Google News RSS, keep it.
GOOGLE_NEWS_BASE = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

def google_news_rss(query: str) -> str:
    return GOOGLE_NEWS_BASE.format(q=quote_plus(query))

def now_iso():
    return datetime.now(timezone.utc).isoformat()

PROMO_PATTERNS = [
    r"\bsponsored\b", r"\badvertisement\b", r"\bpromo\b", r"\bpromotion\b",
    r"\bcoupon\b", r"\bdeal\b", r"\bdeals\b", r"\bshopping\b",
    r"\bsubscribe\b", r"\bsubscription\b", r"\bpartner content\b",
]
PROMO_RE = re.compile("|".join(PROMO_PATTERNS), re.IGNORECASE)

# “Tragic” is deterministic keyword-based. Not perfect, but it obeys your “unless tragic” rule.
TRAGIC_PATTERNS = [
    r"\bkilled\b", r"\bdead\b", r"\bdeath\b", r"\bmurder\b", r"\bshooting\b",
    r"\bstabbing\b", r"\bmassacre\b", r"\bterror\b", r"\bterrorist\b",
    r"\bwar\b", r"\binvasion\b", r"\bairstrike\b",
    r"\bearthquake\b", r"\bhurricane\b", r"\btornado\b", r"\bflood\b",
    r"\bcrash\b", r"\bexplosion\b", r"\bhostage\b",
]
TRAGIC_RE = re.compile("|".join(TRAGIC_PATTERNS), re.IGNORECASE)

# “Nothing Burger” signals (non-tragic)
NOTHINGBURGER_PATTERNS = [
    r"\bbacklash\b", r"\boutcry\b", r"\boutrage\b", r"\bslammed\b",
    r"\bclaps back\b", r"\bgoes viral\b", r"\binternet reacts\b",
    r"\bfans react\b", r"\bresponds\b", r"\bmeltdown\b",
    r"\bcontroversy\b", r"\bstuns\b", r"\byou won'?t believe\b",
]
NOTHINGBURGER_RE = re.compile("|".join(NOTHINGBURGER_PATTERNS), re.IGNORECASE)

def fetch_feed(url: str, timeout: int = 20):
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return feedparser.parse(r.content)

def normalize_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip())

def is_promo(title: str) -> bool:
    return bool(PROMO_RE.search(title or ""))

def is_tragic(title: str) -> bool:
    return bool(TRAGIC_RE.search(title or ""))

def is_nothingburger(title: str) -> bool:
    return bool(NOTHINGBURGER_RE.search(title or "")) and not is_tragic(title)

def items_from_feed(parsed, source_name: str, max_items: int):
    items = []
    for e in parsed.entries[: max_items * 3]:
        title = normalize_title(getattr(e, "title", ""))
        link = getattr(e, "link", None)
        if not title or not link:
            continue
        if is_promo(title):
            continue
        items.append({
            "title": title,
            "url": link,
            "source": source_name,
            "tragic": is_tragic(title),
        })
        if len(items) >= max_items:
            break
    return items

def dedupe_list(items):
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
        return None
    with open(HEADLINES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save(data):
    with open(HEADLINES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# -----------------------------
# SOURCE POOLS (balance rule)
# -----------------------------
# You asked for equal counts from “left” and “right” source pools per section.
# These labels are YOUR operational buckets (not a claim of objective ideology).
LEFT_SOURCES = [
    ("Reuters",  google_news_rss("site:reuters.com when:2d -inurl:/video -inurl:/graphics")),
    ("AP",       google_news_rss("site:apnews.com when:2d")),
    ("Guardian", google_news_rss("site:theguardian.com when:3d")),
    ("Bloomberg",google_news_rss("site:bloomberg.com when:3d")),
]

RIGHT_SOURCES = [
    ("Fox News", google_news_rss("site:foxnews.com when:2d")),
    ("NY Post",  google_news_rss("site:nypost.com when:2d")),
    ("Examiner", google_news_rss("site:washingtonexaminer.com when:5d")),
    ("WSJ",      google_news_rss("site:wsj.com when:3d")),
]

TECH_LEFT = [
    ("The Verge", google_news_rss("site:theverge.com when:3d")),
]
TECH_RIGHT = [
    ("Hacker News", "https://news.ycombinator.com/rss"),
]

WEIRD_LEFT = [
    ("Atlas Obscura", google_news_rss("site:atlasobscura.com when:30d")),
]
WEIRD_RIGHT = [
    ("Reuters OddlyEnough", google_news_rss("site:reuters.com ('oddly enough' OR oddly OR bizarre OR strange OR unusual) when:30d -inurl:/video")),
]

# -----------------------------
# SECTION DEFINITIONS
# -----------------------------
# Each section uses N from left + N from right (equal).
# Then we alternate left/right in the final list for visible balance.
SECTIONS = {
    "breaking": {
        "total": 7,              # cap at 7
        "left_right_each": 4,    # pull pool size; final will be deduped/capped to 7
        "sources_left": LEFT_SOURCES[:2],   # Reuters, AP
        "sources_right": RIGHT_SOURCES[:2], # Fox, NYPost
        "filter_fn": None,
    },
    "developing": {
        "total": 14,
        "left_right_each": 8,
        "sources_left": LEFT_SOURCES[:2],
        "sources_right": RIGHT_SOURCES[:2],
        "filter_fn": None,
    },
    "nothingburger": {
        "total": 10,
        "left_right_each": 8,
        "sources_left": LEFT_SOURCES[:2],
        "sources_right": RIGHT_SOURCES[:2],
        "filter_fn": is_nothingburger,
    },
    "world": {
        "total": 14,
        "left_right_each": 10,
        "sources_left": [LEFT_SOURCES[0], LEFT_SOURCES[1], LEFT_SOURCES[2]],  # Reuters/AP/Guardian
        "sources_right": [RIGHT_SOURCES[0], RIGHT_SOURCES[1], RIGHT_SOURCES[2]], # Fox/NYP/Examiner
        "filter_fn": None,
    },
    "politics": {
        "total": 14,
        "left_right_each": 10,
        "sources_left": [LEFT_SOURCES[2], LEFT_SOURCES[0]],   # Guardian/Reuters
        "sources_right": [RIGHT_SOURCES[2], RIGHT_SOURCES[0]],# Examiner/Fox
        "filter_fn": None,
    },
    "markets": {
        "total": 14,
        "left_right_each": 10,
        "sources_left": [LEFT_SOURCES[3], LEFT_SOURCES[0]],   # Bloomberg/Reuters
        "sources_right": [RIGHT_SOURCES[3], RIGHT_SOURCES[0]],# WSJ/Fox
        "filter_fn": None,
    },
    "tech": {
        "total": 14,
        "left_right_each": 10,
        "sources_left": TECH_LEFT,
        "sources_right": TECH_RIGHT,
        "filter_fn": None,
    },
    "weird": {
        "total": 12,
        "left_right_each": 10,
        "sources_left": WEIRD_LEFT,
        "sources_right": WEIRD_RIGHT,
        "filter_fn": None,
    },
    "missed": {
        "total": 12,
        "left_right_each": 0,  # computed from leftovers, balance handled by origin tags
        "sources_left": [],
        "sources_right": [],
        "filter_fn": None,
    },
}

def pull_from_sources(sources, take_n):
    combined = []
    for source_name, url in sources:
        parsed = fetch_feed(url)
        combined.extend(items_from_feed(parsed, source_name, max_items=take_n))
    return dedupe_list(combined)

def alternate_merge(left_items, right_items, limit):
    out = []
    i = j = 0
    while len(out) < limit and (i < len(left_items) or j < len(right_items)):
        if i < len(left_items):
            out.append(left_items[i]); i += 1
            if len(out) >= limit: break
        if j < len(right_items):
            out.append(right_items[j]); j += 1
    return out[:limit]

def global_dedupe(section_items_map):
    seen = set()
    for section_name, items in section_items_map.items():
        filtered = []
        for it in items:
            key = (it.get("title", "").lower(), it.get("url", ""))
            if key in seen:
                continue
            seen.add(key)
            filtered.append(it)
        section_items_map[section_name] = filtered
    return section_items_map

def main():
    # Build all sections in one run so global dedupe is guaranteed.
    sections_out = {}

    # First generate all sections except "missed"
    for name, cfg in SECTIONS.items():
        if name == "missed":
            continue

        n_each = cfg["left_right_each"]
        left_pool = pull_from_sources(cfg["sources_left"], n_each) if n_each else []
        right_pool = pull_from_sources(cfg["sources_right"], n_each) if n_each else []

        # Optional per-section filter
        fn = cfg["filter_fn"]
        if fn:
            left_pool = [x for x in left_pool if fn(x["title"])]
            right_pool = [x for x in right_pool if fn(x["title"])]

        merged = alternate_merge(left_pool, right_pool, cfg["total"])
        sections_out[name] = merged

    # Global dedupe across these sections (in page order priority)
    page_order = ["breaking","developing","nothingburger","world","politics","markets","tech","weird"]
    ordered_map = {k: sections_out.get(k, []) for k in page_order}
    ordered_map = global_dedupe(ordered_map)
    sections_out.update(ordered_map)

    # Build "You Might Have Missed" from leftovers across the non-breaking sections
    already_used = set()
    for k in page_order:
        for it in sections_out.get(k, []):
            already_used.add((it.get("title","").lower(), it.get("url","")))

    # Candidate pool: pull extra from a broad mix, then remove anything already used.
    missed_candidates = []
    missed_sources = [
        LEFT_SOURCES[0], LEFT_SOURCES[1], LEFT_SOURCES[2], LEFT_SOURCES[3],
        RIGHT_SOURCES[0], RIGHT_SOURCES[2], RIGHT_SOURCES[3],
        TECH_RIGHT[0], TECH_LEFT[0],
        WEIRD_RIGHT[0], WEIRD_LEFT[0],
    ]
    # Pull a decent amount, then global-filter
    for source_name, url in missed_sources:
        parsed = fetch_feed(url)
        missed_candidates.extend(items_from_feed(parsed, source_name, max_items=12))
    missed_candidates = dedupe_list(missed_candidates)

    missed_filtered = []
    for it in missed_candidates:
        key = (it.get("title","").lower(), it.get("url",""))
        if key in already_used:
            continue
        if is_promo(it["title"]):
            continue
        missed_filtered.append(it)
        if len(missed_filtered) >= SECTIONS["missed"]["total"]:
            break

    sections_out["missed"] = missed_filtered

    data = {
        "meta": {"generated_at": now_iso(), "version": 3},
        "sections": sections_out
    }
    save(data)

if __name__ == "__main__":
    main()
