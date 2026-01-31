import json
import random
import re
from datetime import datetime, timezone

import feedparser


# =====================
# CONFIG
# =====================
MAX_ITEMS_PER_SECTION = 12
MAX_PER_SOURCE_PER_SECTION = 4


# =====================
# FEEDS
# =====================
BREAKING_FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
]

TOP_FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
]

BUSINESS_FEEDS = [
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("NPR Business", "https://feeds.npr.org/1006/rss.xml"),
]

MISC_FEEDS = [
    ("BBC Tech", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("NPR Tech", "https://feeds.npr.org/1019/rss.xml"),
]


LAYOUT = [
    [("Breaking", BREAKING_FEEDS), ("Top", TOP_FEEDS)],
    [("Business", BUSINESS_FEEDS)],
    [("World / Tech / Weird", MISC_FEEDS)],
]


# =====================
# TEXT
# =====================
SNARK = [
    "A confident plan has been announced. Reality is pending.",
    "Officials say it's under control. So that's something.",
    "A decision was made. Consequences scheduled for later.",
    "Experts disagree, loudly and on schedule.",
    "The plan is simple. The details are complicated.",
    "Numbers were cited. Interpretation may vary.",
    "This will surely be handled with nuance.",
    "A big announcement, with a small footnote doing cardio.",
    "A statement was issued. Substance not included.",
    "A compromise is proposed. Someone will hate it.",
    "The situation remains fluid. Like Jell-O.",
    "A timeline was provided. Nobody believes it.",
    "A bold prediction, fresh out of context.",
    "Everyone is calm. On paper.",
    "An investigation begins. Again.",
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
    "war", "explosion", "terror", "crash", "earthquake",
]


# =====================
# HELPERS
# =====================
def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def is_tragic(title):
    t = title.lower()
    return any(k in t for k in TRAGEDY_KEYWORDS)


def parse_feed(source, url):
    items = []
    feed = feedparser.parse(url)
    for e in feed.entries[:40]:
        title = clean(getattr(e, "title", ""))
        link = getattr(e, "link", "")
        if title and link:
            items.append({"title": title, "url": link, "source": source})
    return items


def unique_line(pool, used, fallback):
    random.shuffle(pool)
    for s in pool:
        if s not in used:
            used.add(s)
            return s
    while True:
        candidate = fallback + " "
        if candidate not in used:
            used.add(candidate)
            return candidate


def load_previous():
    try:
        with open("headlines.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# =====================
# MAIN
# =====================
def main():
    prev = load_previous()
    now = datetime.now(timezone.utc)
    three_hour = (now.hour % 3 == 0)

    used_urls = set()
    used_sublines = set()

    if prev and not three_hour:
        for col in prev.get("columns", []):
            for sec in col.get("sections", []):
                if sec.get("name") != "Breaking":
                    for it in sec.get("items", []):
                        used_urls.add(it["url"])
                        used_sublines.add(it.get("snark", ""))

    columns = []

    for col in LAYOUT:
        col_out = {"sections": []}

        for name, feeds in col:
            refresh = (name.startswith("Breaking") or three_hour)

            if not refresh and prev:
                for pcol in prev["columns"]:
                    for psec in pcol["sections"]:
                        if psec["name"] == name:
                            col_out["sections"].append(psec)
                            break
                continue

            raw = []
            for src, url in feeds:
                raw.extend(parse_feed(src, url))

            section_items = []
            per_source = {}

            for it in raw:
                if it["url"] in used_urls:
                    continue

                src = it["source"]
                per_source[src] = per_source.get(src, 0)
                if per_source[src] >= MAX_PER_SOURCE_PER_SECTION:
                    continue

                used_urls.add(it["url"])
                per_source[src] += 1

                tragic = is_tragic(it["title"])
                if tragic:
                    sub = unique_line([], used_sublines, random.choice(NEUTRAL))
                else:
                    sub = unique_line(SNARK, used_sublines, random.choice(NEUTRAL))

                section_items.append({
                    "title": it["title"],
                    "url": it["url"],
                    "source": it["source"],
                    "badge": "BREAK" if name.startswith("Breaking") and not section_items else "",
                    "feature": bool(name.startswith("Breaking") and not section_items),
                    "snark": sub,
                })

                if len(section_items) >= MAX_ITEMS_PER_SECTION:
                    break

            col_out["sections"].append({
                "name": name,
                "items": section_items,
            })

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