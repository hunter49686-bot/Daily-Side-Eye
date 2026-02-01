import json
import random
import re
from datetime import datetime, timezone

import feedparser


# =====================
# TUNING
# =====================
MAX_ITEMS_PER_SECTION = 18
MAX_PER_SOURCE_PER_SECTION = 3


# =====================
# RSS FEEDS (EXPANDED + BALANCED)
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
def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def is_tragic(title):
    t = (title or "").lower()
    return any(k in t for k in TRAGEDY_KEYWORDS)


def parse_feed(source, url):
    items = []
    feed = feedparser.parse(url)
    for e in feed.entries[:80]:
        title = clean(getattr(e, "title", ""))
        link = getattr(e, "link", "")
        if title and link:
            items.append({"title": title[:180], "url": link, "source": source})
    return items


def load_previous():
    try:
        with open("headlines.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def unique_line(pool, used, fallback):
    random.shuffle(pool)
    for s in pool:
        if s not in used:
            used.add(s)
            return s
    # No visible v2/v3: use a whitespace-only uniqueness trick
    while True:
        candidate = fallback + " "
        if candidate not in used:
            used.add(candidate)
            return candidate


def dedupe_local_by_url(items):
    seen = set()
    out = []
    for it in items:
        u = it.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out


# =====================
# MAIN
# =====================
def main():
    prev = load_previous()
    now = datetime.now(timezone.utc)
    three_hour_boundary = (now.hour % 3 == 0)

    used_urls = set()
    used_sublines = set()

    # Between 3-hour boundaries, reuse non-breaking sections and prevent Breaking from duplicating them
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

    for col in LAYOUT:
        col_out = {"sections": []}

        for name, feeds in col:
            refresh = name.startswith("Breaking") or three_hour_boundary

            # reuse section if not refreshing
            if not refresh and prev:
                reused = None
                for pcol in prev.get("columns", []):
                    for psec in pcol.get("sections", []):
                        if psec.get("name") == name:
                            reused = psec
                            break
                    if reused:
                        break
                if reused:
                    col_out["sections"].append(reused)
                    continue

            # Build fresh section
            raw = []
            for src, url in feeds:
                raw.extend(parse_feed(src, url))

            # KEY FIX: shuffle so later sources (Fox/NYPost/RCP/etc.) get a fair shot
            random.shuffle(raw)

            # local URL dedupe inside this section
            raw = dedupe_local_by_url(raw)

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
                    "badge": "BREAK" if name.startswith("Breaking") and is_first else "",
                    "feature": bool(name.startswith("Breaking") and is_first),
                    "snark": sub,
                })

                used_urls.add(it["url"])
                per_source[src] += 1

                if len(section_items) >= MAX_ITEMS_PER_SECTION:
                    break

            col_out["sections"].append({"name": name, "items": section_items})

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