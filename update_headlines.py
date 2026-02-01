import json
import random
import re
import socket
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import feedparser


# =====================
# TUNING
# =====================
MAX_ITEMS_PER_SECTION = 18
MAX_PER_SOURCE_PER_SECTION = 3
HTTP_TIMEOUT_SECONDS = 10

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

socket.setdefaulttimeout(HTTP_TIMEOUT_SECONDS)


# =====================
# RSS FEEDS (BALANCED)
# =====================
BREAKING_FEEDS = [
    # Center / Left
    ("BBC Front Page", "https://feeds.bbci.co.uk/news/rss.xml"),
    ("CNN Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
    ("The Guardian World", "https://www.theguardian.com/world/rss"),

    # Right-leaning
    ("Fox News", "https://feeds.foxnews.com/foxnews/latest"),
    ("New York Post", "https://nypost.com/feed/"),

    # Cross-spectrum aggregator
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

# 3 columns, Breaking at top of column 1
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


# =====================
# HELPERS
# =====================
def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_tragic(title: str) -> bool:
    t = (title or "").lower()
    return any(k in t for k in TRAGEDY_KEYWORDS)


def fetch_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8"})
    with urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
        return resp.read()


def parse_feed(source: str, url: str, debug_list: list):
    items = []
    try:
        data = fetch_bytes(url)
        feed = feedparser.parse(data)

        # If feedparser flags bozo, keep going but record it
        bozo = getattr(feed, "bozo", 0)
        bozo_exc = str(getattr(feed, "bozo_exception", "")) if bozo else ""

        entries = getattr(feed, "entries", [])[:80]
        for e in entries:
            title = clean(getattr(e, "title", ""))
            link = getattr(e, "link", "")
            if title and link:
                items.append({"title": title[:180], "url": link, "source": source})

        debug_list.append({
            "source": source,
            "url": url,
            "items": len(items),
            "bozo": bool(bozo),
            "bozo_exception": bozo_exc[:140] if bozo_exc else ""
        })
        return items

    except Exception as ex:
        debug_list.append({
            "source": source,
            "url": url,
            "items": 0,
            "error": str(ex)[:160]
        })
        return []


def load_previous():
    try:
        with open("headlines.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def unique_line(pool, used_set, fallback):
    random.shuffle(pool)
    for s in pool:
        if s not in used_set:
            used_set.add(s)
            return s

    # No visible "v2/v3": whitespace-only uniqueness
    base = fallback
    pad = " "
    while base + pad in used_set:
        pad += " "
    used_set.add(base + pad)
    return base + pad


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


def round_robin_by_source(items):
    """Return list of items interleaved by source so one outlet can't dominate."""
    buckets = {}
    for it in items:
        buckets.setdefault(it["source"], []).append(it)

    # Shuffle each bucket and shuffle the order of sources
    sources = list(buckets.keys())
    for s in sources:
        random.shuffle(buckets[s])
    random.shuffle(sources)

    out = []
    while True:
        progressed = False
        for s in sources:
            if buckets[s]:
                out.append(buckets[s].pop())
                progressed = True
        if not progressed:
            break
    return out


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
                        u = (it.get("url") or "").strip()
                        s = (it.get("snark") or "").strip()
                        if u:
                            used_urls.add(u)
                        if s:
                            used_sublines.add(s)

    columns = []
    debug = {"feeds": []}

    for col in LAYOUT:
        col_out = {"sections": []}

        for section_name, feeds in col:
            refresh = section_name.startswith("Breaking") or three_hour_boundary

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
            section_debug = []
            for src, url in feeds:
                raw.extend(parse_feed(src, url, section_debug))

            # Record feed health for this section (PROOF of what's loading)
            debug["feeds"].append({"section": section_name, "results": section_debug})

            # Local dedupe + round-robin for source diversity
            raw = dedupe_local_by_url(raw)
            raw = round_robin_by_source(raw)

            section_items = []
            per_source = {}

            for it in raw:
                if it["url"] in used_urls:
                    continue

                src = it["source"]
                per_source[src] = per_source.get(src, 0)
                if per_source[src] >= MAX_PER_SOURCE_PER_SECTION:
                    continue

                tragic = is_tragic(it["title"])
                if tragic:
                    sub = unique_line([], used_sublines, random.choice(NEUTRAL))
                else:
                    sub = unique_line(SNARK, used_sublines, random.choice(NEUTRAL))

                is_first = (len(section_items) == 0)
                section_items.append({
                    "title": it["title"],
                    "url": it["url"],
                    "source": it["source"],
                    "badge": "BREAK" if section_name.startswith("Breaking") and is_first else "",
                    "feature": bool(section_name.startswith("Breaking") and is_first),
                    "snark": sub,
                })

                used_urls.add(it["url"])
                per_source[src] += 1

                if len(section_items) >= MAX_ITEMS_PER_SECTION:
                    break

            col_out["sections"].append({"name": section_name, "items": section_items})

        columns.append(col_out)

    out = {
        "site": {
            "name": "THE DAILY SIDE-EYE",
            "tagline": "Headlines with a raised eyebrow.",
        },
        "generated_utc": now.isoformat(),
        "columns": columns,

        # DEBUG: remove later if you want, but keep now to diagnose feed health
        "debug": debug,
    }

    with open("headlines.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()