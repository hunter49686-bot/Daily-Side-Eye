import json
import random
import re
import socket
import time
from datetime import datetime, timezone, timedelta

import feedparser

# =====================
# HARD NETWORK SAFETY (prevents Actions hangs)
# =====================
HTTP_TIMEOUT_SECONDS = 10
socket.setdefaulttimeout(HTTP_TIMEOUT_SECONDS)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

# =====================
# TUNING
# =====================
MAX_PER_SOURCE_PER_SECTION = 3

# Per-section caps (Breaking should feel like Breaking)
MAX_ITEMS_BY_SECTION = {
    "Breaking": 9,
    "Top": 16,
    "Business": 14,
    "World / Tech / Weird": 14,
}

# Freshness windows (days)
FRESHNESS_DAYS_BY_SECTION = {
    "Breaking": 3,
    "Top": 7,
    "Business": 14,
    "World / Tech / Weird": 21,
}

# Ensure balance: if available, include at least 1 from these sources per section
BALANCE_TARGETS = [
    "Fox News",
    "New York Post",
    "Washington Examiner",
    "National Review",
    "RealClearPolitics",
]

# =====================
# FEEDS
# =====================
BREAKING_FEEDS = [
    ("BBC Front Page", "https://feeds.bbci.co.uk/news/rss.xml"),
    ("CNN Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
    ("The Guardian World", "https://www.theguardian.com/world/rss"),
    ("Fox News", "https://feeds.foxnews.com/foxnews/latest"),
    ("New York Post", "https://nypost.com/feed/"),
    ("RealClearPolitics", "https://www.realclearpolitics.com/index.xml"),
]

TOP_FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("CNN Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
    ("The Guardian UK", "https://www.theguardian.com/uk/rss"),
    ("Fox News", "https://feeds.foxnews.com/foxnews/latest"),
    ("New York Post", "https://nypost.com/feed/"),
    ("RealClearPolitics", "https://www.realclearpolitics.com/index.xml"),
]

BUSINESS_FEEDS = [
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("CNN Business", "http://rss.cnn.com/rss/money_latest.rss"),
    ("NPR Business", "https://feeds.npr.org/1006/rss.xml"),
    ("The Guardian Business", "https://www.theguardian.com/business/rss"),
    ("Washington Examiner", "https://www.washingtonexaminer.com/rss.xml"),
    ("National Review", "https://www.nationalreview.com/feed/"),
]

WORLD_TECH_WEIRD_FEEDS = [
    ("BBC Tech", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("NPR Technology", "https://feeds.npr.org/1019/rss.xml"),
    ("The Guardian Tech", "https://www.theguardian.com/technology/rss"),
    ("National Review", "https://www.nationalreview.com/feed/"),
    ("RealClearPolitics", "https://www.realclearpolitics.com/index.xml"),
]

LAYOUT = [
    [("Breaking", BREAKING_FEEDS), ("Top", TOP_FEEDS)],
    [("Business", BUSINESS_FEEDS)],
    [("World / Tech / Weird", WORLD_TECH_WEIRD_FEEDS)],
]

# =====================
# COPY
# =====================
SNARK = [
    "The optics are doing most of the work here.",
    "This will surely be handled with nuance.",
    "A statement was issued. Substance not included.",
    "A confident plan has been announced. Reality is pending.",
    "A compromise is proposed. Someone will hate it.",
    "Numbers were cited. Interpretation may vary.",
    "Experts disagree, loudly and on schedule.",
    "A decision was made. Consequences scheduled for later.",
    "The fine print is doing most of the work.",
    "Everyone is calm. On paper.",
    "A bold claim meets inconvenient details.",
    "A timeline was provided. Nobody believes it.",
    "The explanation is technically words.",
    "An investigation begins. Again.",
    "A big announcement, with a small footnote doing cardio.",
    "The plan is simple. The details are complicated.",
    "A 'common sense' solution sparks uncommon disagreement.",
]

NEUTRAL = [
    "Developing story.",
    "Details are still emerging.",
    "Authorities are investigating.",
    "Situation remains unclear.",
    "More information expected soon.",
    "Reporting continues.",
    "Updates may follow.",
    "Context is still being gathered.",
]

TRAGEDY_KEYWORDS = [
    "dead", "dies", "killed", "death", "shooting", "attack",
    "war", "bomb", "explosion", "terror", "crash",
    "earthquake", "wildfire", "flood", "victim", "injured",
]

PROMO_PATTERNS = [
    r"\bbonus code\b",
    r"\bpromo code\b",
    r"\bbetmgm\b",
    r"\bdraftkings\b",
    r"\bfanduel\b",
    r"\bbetting\b",
    r"\bodds\b",
    r"\bsportsbook\b",
    r"\bfree bet\b",
    r"\bdeposit match\b",
    r"\bsubscribe\b",
    r"\bsponsored\b",
    r"\badvertis",
    r"\bcoupon\b",
    r"\bdeal\b",
]
PROMO_RE = re.compile("|".join(PROMO_PATTERNS), re.I)

# =====================
# HELPERS
# =====================
def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def norm_title_key(title: str) -> str:
    t = clean(title).lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:160]

def is_tragic(title: str) -> bool:
    t = (title or "").lower()
    return any(k in t for k in TRAGEDY_KEYWORDS)

def is_promo(title: str) -> bool:
    return bool(PROMO_RE.search(title or ""))

def load_previous():
    try:
        with open("headlines.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def unique_line(pool, used_set, fallback):
    if pool:
        random.shuffle(pool)
        for sline in pool:
            sline = clean(sline)
            if sline and sline not in used_set:
                used_set.add(sline)
                return sline

    base = clean(fallback) or "Updates may follow."
    pad = ""
    while base + pad in used_set:
        pad += " "
    used_set.add(base + pad)
    return base + pad

def entry_epoch_seconds(entry) -> int | None:
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not t:
        return None
    try:
        return int(time.mktime(t))
    except Exception:
        return None

def parse_feed(source: str, url: str):
    items = []
    try:
        feed = feedparser.parse(url, agent=USER_AGENT)
    except Exception:
        return items

    for e in getattr(feed, "entries", [])[:80]:
        title = clean(getattr(e, "title", ""))
        link = getattr(e, "link", "")

        if not title or not link:
            continue
        if is_promo(title):
            continue

        epoch = entry_epoch_seconds(e)
        published_utc = None
        if epoch:
            published_utc = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()

        items.append({
            "title": title[:180],
            "url": link,
            "source": source,
            "published_utc": published_utc,  # may be None
        })
    return items

def dedupe_local_by_url(items):
    seen = set()
    out = []
    for it in items:
        u = clean(it.get("url", ""))
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out

def dedupe_local_by_title(items):
    seen = set()
    out = []
    for it in items:
        key = norm_title_key(it.get("title", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

def filter_by_freshness(items, section_name: str, now_utc: datetime):
    days = FRESHNESS_DAYS_BY_SECTION.get(section_name, 14)
    cutoff = now_utc - timedelta(days=days)

    fresh = []
    unknown = []
    for it in items:
        pu = it.get("published_utc")
        if not pu:
            unknown.append(it)
            continue
        try:
            dt = datetime.fromisoformat(pu.replace("Z", "+00:00"))
        except Exception:
            unknown.append(it)
            continue
        if dt >= cutoff:
            fresh.append(it)

    # For Breaking/Top, do not allow unknown-dated items (prevents “2019/2023 evergreen” weirdness)
    if section_name in ("Breaking", "Top"):
        return fresh

    return fresh + unknown

def round_robin(items):
    buckets = {}
    for it in items:
        buckets.setdefault(it["source"], []).append(it)

    sources = list(buckets.keys())
    for src in sources:
        random.shuffle(buckets[src])
    random.shuffle(sources)

    out = []
    progressed = True
    while progressed:
        progressed = False
        for src in sources:
            if buckets[src]:
                out.append(buckets[src].pop())
                progressed = True
    return out

def pick_section_items(raw_items, used_urls, used_sublines, section_name, now_utc):
    max_items = MAX_ITEMS_BY_SECTION.get(section_name, 14)

    raw_items = dedupe_local_by_url(raw_items)
    raw_items = dedupe_local_by_title(raw_items)
    raw_items = filter_by_freshness(raw_items, section_name, now_utc)
    raw_items = round_robin(raw_items)

    section_items = []
    per_source = {}

    pool_by_source = {}
    for it in raw_items:
        pool_by_source.setdefault(it["source"], []).append(it)

    def add_item(it, is_first=False):
        tragic = is_tragic(it["title"])
        sub = unique_line([], used_sublines, random.choice(NEUTRAL)) if tragic else unique_line(SNARK, used_sublines, random.choice(NEUTRAL))
        sub = clean(sub)

        section_items.append({
            "title": it["title"],
            "url": it["url"],
            "source": it["source"],
            "badge": "BREAK" if section_name == "Breaking" and is_first else "",
            "feature": bool(section_name == "Breaking" and is_first),
            "snark": sub,
            "published_utc": it.get("published_utc"),
        })
        used_urls.add(it["url"])
        per_source[it["source"]] = per_source.get(it["source"], 0) + 1

    # Step 1: balance targets
    for target in BALANCE_TARGETS:
        if len(section_items) >= max_items:
            break
        if target not in pool_by_source:
            continue
        if per_source.get(target, 0) >= MAX_PER_SOURCE_PER_SECTION:
            continue

        picked = None
        for it in pool_by_source[target]:
            if it["url"] not in used_urls:
                picked = it
                break
        if not picked:
            continue

        add_item(picked, is_first=(len(section_items) == 0))

    # Step 2: fill normally
    for it in raw_items:
        if len(section_items) >= max_items:
            break
        if it["url"] in used_urls:
            continue
        if per_source.get(it["source"], 0) >= MAX_PER_SOURCE_PER_SECTION:
            continue

        add_item(it, is_first=(len(section_items) == 0))

    return section_items

# =====================
# MAIN
# =====================
def main():
    prev = load_previous()
    now = datetime.now(timezone.utc)

    # Only rebuild non-breaking sections every 3 hours
    three_hour_boundary = (now.hour % 3 == 0)

    used_urls = set()
    used_sublines = set()

    # Between 3-hour boundaries, keep non-breaking sections and prevent Breaking duplicates
    if prev and not three_hour_boundary:
        for col in prev.get("columns", []):
            for sec in col.get("sections", []):
                if sec.get("name") != "Breaking":
                    for it in sec.get("items", []):
                        u = clean(it.get("url", ""))
                        sub = clean(it.get("snark", ""))
                        if u:
                            used_urls.add(u)
                        if sub:
                            used_sublines.add(sub)

    columns = []

    for col in LAYOUT:
        col_out = {"sections": []}

        for section_name, feeds in col:
            refresh = (section_name == "Breaking") or three_hour_boundary

            # Reuse section if not refreshing
            if not refresh and prev:
                reused = None
                for pcol in prev.get("columns", []):
                    for psec in pcol.get("sections", []):
                        if psec.get("name") == section_name:
                            reused = psec
                            break
                    if reused:
                        break
                if reused:
                    col_out["sections"].append(reused)
                    continue

            raw = []
            for src, url in feeds:
                raw.extend(parse_feed(src, url))

            random.shuffle(raw)

            items = pick_section_items(raw, used_urls, used_sublines, section_name, now)
            col_out["sections"].append({"name": section_name, "items": items})

        columns.append(col_out)

    out = {
        "site": {
            "name": "THE DAILY SIDE-EYE",
            "tagline": "Headlines with a raised eyebrow.",
        },
        "generated_utc": now.isoformat(),
        "columns": columns,
    }

    with open("headlines.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
