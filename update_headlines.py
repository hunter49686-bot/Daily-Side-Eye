import json
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import requests

HEADLINES_PATH = "headlines.json"
USER_AGENT = "DailySideEyeBot/1.0 (+https://dailysideeye.com)"
GOOGLE_NEWS_BASE = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

def google_news_rss(query: str) -> str:
    return GOOGLE_NEWS_BASE.format(q=quote_plus(query))

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

PROMO_RE = re.compile(
    r"\bsponsored\b|\badvertisement\b|\bpromo\b|\bpromotion\b|\bcoupon\b|\bdeal\b|\bdeals\b|"
    r"\bshopping\b|\bsubscribe\b|\bsubscription\b|\bpartner content\b",
    re.IGNORECASE
)

TRAGIC_RE = re.compile(
    r"\bkilled\b|\bdead\b|\bdeath\b|\bmurder\b|\bshooting\b|\bstabbing\b|\bmassacre\b|"
    r"\bterror\b|\bterrorist\b|\bwar\b|\binvasion\b|\bairstrike\b|\bearthquake\b|\bhurricane\b|"
    r"\btornado\b|\bflood\b|\bcrash\b|\bexplosion\b|\bhostage\b",
    re.IGNORECASE
)

NOTHINGBURGER_RE = re.compile(
    r"\bbacklash\b|\boutcry\b|\boutrage\b|\bslammed\b|\bclaps back\b|\bgoes viral\b|"
    r"\binternet reacts\b|\bfans react\b|\bresponds\b|\bmeltdown\b|\bcontroversy\b|\bstuns\b|"
    r"\byou won'?t believe\b",
    re.IGNORECASE
)

def is_promo(title: str) -> bool:
    return bool(PROMO_RE.search(title or ""))

def is_tragic(title: str) -> bool:
    return bool(TRAGIC_RE.search(title or ""))

def is_nothingburger(title: str) -> bool:
    return bool(NOTHINGBURGER_RE.search(title or "")) and not is_tragic(title)

def normalize_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip())

def fetch_feed(url: str, timeout: int = 20):
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return feedparser.parse(r.content)

def items_from_feed(parsed, source_name: str, max_items: int):
    out = []
    for e in parsed.entries[: max_items * 4]:
        title = normalize_title(getattr(e, "title", ""))
        link = getattr(e, "link", None)
        if not title or not link:
            continue
        if is_promo(title):
            continue
        out.append({
            "title": title,
            "url": link,
            "source": source_name,
            "tragic": is_tragic(title),
        })
        if len(out) >= max_items:
            break
    return out

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

def pull_sources(sources, take_each):
    combined = []
    for name, url in sources:
        parsed = fetch_feed(url)
        combined.extend(items_from_feed(parsed, name, max_items=take_each))
    return dedupe_list(combined)

def alternate(left_items, right_items, limit):
    out = []
    i = j = 0
    while len(out) < limit and (i < len(left_items) or j < len(right_items)):
        if i < len(left_items):
            out.append(left_items[i]); i += 1
            if len(out) >= limit:
                break
        if j < len(right_items):
            out.append(right_items[j]); j += 1
    return out[:limit]

def global_dedupe_in_priority(section_map, priority):
    seen = set()
    for sec in priority:
        filtered = []
        for it in section_map.get(sec, []):
            key = (it.get("title","").lower(), it.get("url",""))
            if key in seen:
                continue
            seen.add(key)
            filtered.append(it)
        section_map[sec] = filtered
    return section_map, seen

# ----------------------------
# Source pools (YOUR balance buckets)
# ----------------------------
# These are the same “sources you already chose earlier”, grouped for equal left/right counts.
LEFT_GENERAL = [
    ("Reuters", google_news_rss("site:reuters.com when:2d -inurl:/video -inurl:/graphics")),
    ("AP", google_news_rss("site:apnews.com when:2d")),
]
RIGHT_GENERAL = [
    ("Fox News", google_news_rss("site:foxnews.com when:2d")),
    ("NY Post", google_news_rss("site:nypost.com when:2d")),
]

LEFT_POLITICS = [
    ("Guardian", google_news_rss("site:theguardian.com (politics OR policy OR government) when:3d")),
    ("Reuters", google_news_rss("site:reuters.com (politics OR government OR election OR congress OR parliament) when:3d -inurl:/video")),
]
RIGHT_POLITICS = [
    ("Examiner", google_news_rss("site:washingtonexaminer.com (politics OR policy) when:7d")),
    ("Fox News", google_news_rss("site:foxnews.com (politics OR policy) when:3d")),
]

LEFT_MARKETS = [
    ("Bloomberg", google_news_rss("site:bloomberg.com (markets OR economy OR finance OR stocks) when:3d")),
    ("Reuters", google_news_rss("site:reuters.com (markets OR economy OR finance OR stocks) when:3d -inurl:/video")),
]
RIGHT_MARKETS = [
    ("WSJ", google_news_rss("site:wsj.com (markets OR economy OR finance OR stocks) when:3d")),
    ("Fox Business", google_news_rss("site:foxbusiness.com (markets OR economy OR finance OR stocks) when:3d")),
]

LEFT_TECH = [
    ("The Verge", google_news_rss("site:theverge.com when:3d")),
]
RIGHT_TECH = [
    ("Hacker News", "https://news.ycombinator.com/rss"),
]

LEFT_WEIRD = [
    ("Atlas Obscura", google_news_rss("site:atlasobscura.com when:30d")),
]
RIGHT_WEIRD = [
    ("Reuters OddlyEnough", google_news_rss("site:reuters.com ('oddly enough' OR oddly OR bizarre OR strange OR unusual) when:30d -inurl:/video")),
]

def main():
    sections = {}

    # Section configs
    cfg = {
        # Column 1
        "breaking":      {"limit": 7,  "take_each": 18, "left": LEFT_GENERAL,  "right": RIGHT_GENERAL,  "filter_fn": None},
        "developing":    {"limit": 14, "take_each": 18, "left": LEFT_GENERAL,  "right": RIGHT_GENERAL,  "filter_fn": None},
        "nothingburger": {"limit": 10, "take_each": 30, "left": LEFT_GENERAL,  "right": RIGHT_GENERAL,  "filter_fn": is_nothingburger},

        # Column 2
        "world":         {"limit": 14, "take_each": 18, "left": LEFT_GENERAL,  "right": RIGHT_GENERAL,  "filter_fn": None},
        "politics":      {"limit": 14, "take_each": 18, "left": LEFT_POLITICS, "right": RIGHT_POLITICS, "filter_fn": None},
        "markets":       {"limit": 14, "take_each": 18, "left": LEFT_MARKETS,  "right": RIGHT_MARKETS,  "filter_fn": None},

        # Column 3
        "tech":          {"limit": 14, "take_each": 24, "left": LEFT_TECH,     "right": RIGHT_TECH,     "filter_fn": None},
        "weird":         {"limit": 12, "take_each": 24, "left": LEFT_WEIRD,    "right": RIGHT_WEIRD,    "filter_fn": None},
    }

    # Build sections (balanced merge)
    for sec, c in cfg.items():
        left_pool = pull_sources(c["left"], take_each=c["take_each"])
        right_pool = pull_sources(c["right"], take_each=c["take_each"])

        fn = c["filter_fn"]
        if fn:
            left_pool = [x for x in left_pool if fn(x["title"])]
            right_pool = [x for x in right_pool if fn(x["title"])]

        sections[sec] = alternate(left_pool, right_pool, c["limit"])

    # Global dedupe in page priority order
    priority = ["breaking","developing","nothingburger","world","politics","markets","tech","weird"]
    sections, used = global_dedupe_in_priority(sections, priority)

    # Build "You Might Have Missed" from leftovers not already used, still balanced
    missed_left_sources = LEFT_GENERAL + LEFT_POLITICS + LEFT_MARKETS + LEFT_TECH + LEFT_WEIRD
    missed_right_sources = RIGHT_GENERAL + RIGHT_POLITICS + RIGHT_MARKETS + RIGHT_TECH + RIGHT_WEIRD

    missed_left = pull_sources(missed_left_sources, take_each=12)
    missed_right = pull_sources(missed_right_sources, take_each=12)

    missed_left = [it for it in missed_left if (it["title"].lower(), it["url"]) not in used]
    missed_right = [it for it in missed_right if (it["title"].lower(), it["url"]) not in used]

    sections["missed"] = dedupe_list(alternate(missed_left, missed_right, 12))

    # Final caps (Breaking hard cap 7)
    final = {
        "breaking": sections.get("breaking", [])[:7],
        "developing": sections.get("developing", []),
        "nothingburger": sections.get("nothingburger", []),
        "world": sections.get("world", []),
        "politics": sections.get("politics", []),
        "markets": sections.get("markets", []),
        "tech": sections.get("tech", []),
        "weird": sections.get("weird", []),
        "missed": sections.get("missed", []),
    }

    data = {
        "meta": {"generated_at": now_iso(), "version": 5},
        "sections": final
    }

    with open(HEADLINES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
