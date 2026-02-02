import json
import random
import re
import socket
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import feedparser

# =====================
# HARD NETWORK SAFETY
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
MAX_ITEMS_PER_SECTION = 18
MAX_PER_SOURCE_PER_SECTION = 3

# Breaking limit (you asked for max 7)
MAX_BREAKING_ITEMS = 7

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

# You can rename sections later; keeping your structure
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

# Ad / promo filters (fix “ads mixed in”)
AD_KEYWORDS = [
    "bonus code", "promo code", "bet", "betmgm", "draftkings", "fanduel",
    "odds", "sportsbook", "sign up", "deal", "discount", "coupon", "sale",
    "subscribe", "subscription", "sponsored", "advert", "advertisement",
    "shop", "buy now", "limited time", "get up to", "match up to"
]
AD_URL_HINTS = [
    "/betting/", "utm_", "aff", "affiliate", "promo", "coupon"
]

# =====================
# HELPERS
# =====================
def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def is_tragic(title: str) -> bool:
    t = (title or "").lower()
    return any(k in t for k in TRAGEDY_KEYWORDS)

def looks_like_ad(title: str, url: str) -> bool:
    t = (title or "").lower()
    u = (url or "").lower()
    if any(k in t for k in AD_KEYWORDS):
        return True
    if any(h in u for h in AD_URL_HINTS):
        return True
    return False

def load_previous():
    try:
        with open("headlines.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def unique_line(pool, used_set, fallback):
    random.shuffle(pool)
    for sline in pool:
        if sline not in used_set:
            used_set.add(sline)
            return sline

    base = fallback
    pad = " "
    while base + pad in used_set:
        pad += " "
    used_set.add(base + pad)
    return base + pad

def fetch_bytes(url: str) -> bytes:
    """
    Hard-timeout fetch for RSS bytes.
    This avoids feedparser.parse(url) stalling on some network cases.
    """
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
        return resp.read()

def parse_feed(source: str, url: str):
    items = []
    try:
        data = fetch_bytes(url)
        feed = feedparser.parse(data)
    except (HTTPError, URLError, TimeoutError, socket.timeout, Exception):
        return items

    for e in getattr(feed, "entries", [])[:80]:
        title = clean(getattr(e, "title", ""))
        link = getattr(e, "link", "")
        if not title or not link:
            continue

        # filter ads/promos
        if looks_like_ad(title, link):
            continue

        items.append({"title": title[:180], "url": link, "source": source})
    return items

def dedupe_local_by_url(items):
    seen = set()
    out = []
    for it in items:
        u = (it.get("url") or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out

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

def pick_section_items(raw_items, used_urls, used_sublines, section_name):
    raw_items = dedupe_local_by_url(raw_items)
    raw_items = round_robin(raw_items)

    section_items = []
    per_source = {}

    # Per-section cap (Breaking is 7)
    max_items = MAX_BREAKING_ITEMS if section_name == "Breaking" else MAX_ITEMS_PER_SECTION

    pool_by_source = {}
    for it in raw_items:
        pool_by_source.setdefault(it["source"], []).append(it)

    # Step 1: Force balance targets if available
    for target in BALANCE_TARGETS:
        if len(section_items) >= max_items:
            break
        if target not in pool_by_source:
            continue

        picked = None
        for it in pool_by_source[target]:
            if it["url"] not in used_urls:
                picked = it
                break
        if not picked:
            continue

        src = picked["source"]
        per_source[src] = per_source.get(src, 0)
        if per_source[src] >= MAX_PER_SOURCE_PER_SECTION:
            continue

        tragic = is_tragic(picked["title"])
        sub = unique_line([], used_sublines, random.choice(NEUTRAL)) if tragic else unique_line(SNARK, used_sublines, random.choice(NEUTRAL))

        is_first = (len(section_items) == 0)
        section_items.append({
            "title": picked["title"],
            "url": picked["url"],
            "source": picked["source"],
            "badge": "BREAK" if section_name == "Breaking" and is_first else "",
            "feature": bool(section_name == "Breaking" and is_first),
            "snark": sub,
        })
        used_urls.add(picked["url"])
        per_source[src] += 1

    # Step 2: Fill rest
    for it in raw_items:
        if len(section_items) >= max_items:
            break
        if it["url"] in used_urls:
            continue

        src = it["source"]
        per_source[src] = per_source.get(src, 0)
        if per_source[src] >= MAX_PER_SOURCE_PER_SECTION:
            continue

        tragic = is_tragic(it["title"])
        sub = unique_line([], used_sublines, random.choice(NEUTRAL)) if tragic else unique_line(SNARK, used_sublines, random.choice(NEUTRAL))

        is_first = (len(section_items) == 0)
        section_items.append({
            "title": it["title"],
            "url": it["url"],
            "source": it["source"],
            "badge": "BREAK" if section_name == "Breaking" and is_first else "",
            "feature": bool(section_name == "Breaking" and is_first),
            "snark": sub,
        })
        used_urls.add(it["url"])
        per_source[src] += 1

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

    if prev and not three_hour_boundary:
        for col in prev.get("columns", []):
            for sec in col.get("sections", []):
                if sec.get("name") != "Breaking":
                    for it in sec.get("items", []):
                        u = (it.get("url") or "").strip()
                        sl = (it.get("snark") or "").strip()
                        if u:
                            used_urls.add(u)
                        if sl:
                            used_sublines.add(sl)

    columns = []

    for col in LAYOUT:
        col_out = {"sections": []}

        for section_name, feeds in col:
            refresh = (section_name == "Breaking") or three_hour_boundary

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

            items = pick_section_items(raw, used_urls, used_sublines, section_name)
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
