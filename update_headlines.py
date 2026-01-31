import json
import random
import re
from datetime import datetime, timezone

import feedparser

MAX_ITEMS_PER_SECTION = 18
MAX_PER_SOURCE_PER_SECTION = 3

SNARK = [
    "A confident plan has been announced. Reality is pending.",
    "Officials say it is under control. So that is something.",
    "A decision was made. Consequences scheduled for later.",
    "Experts disagree, loudly and on schedule.",
    "The plan is simple. The details are complicated.",
    "Numbers were cited. Interpretation may vary.",
    "This will surely be handled with nuance.",
    "A big announcement, with a small footnote doing cardio.",
    "A statement was issued. Substance not included.",
    "A compromise is proposed. Someone will hate it.",
    "The situation remains fluid.",
    "A timeline was provided. Nobody believes it.",
    "A bold prediction, fresh out of context.",
    "Everyone is calm. On paper.",
    "An investigation begins. Again.",
    "A quick fix becomes the long-term architecture.",
    "A review is underway.",
    "A win is declared. The scoreboard is unavailable.",
    "The fine print is doing most of the work here.",
    "Expectations were managed. Results were not.",
]

NEUTRAL = [
    "Developing story.",
    "Details are still emerging.",
    "Authorities are investigating.",
    "Situation remains unclear.",
    "More information expected.",
    "Updates may follow.",
]

TRAGEDY_KEYWORDS = [
    "dead", "death", "dies", "died", "killed", "kill",
    "injured", "hurt", "pain", "suffering",
    "shooting", "shot", "stabbing",
    "attack", "attacked", "assault",
    "fire", "explosion", "crash",
    "war", "airstrike", "missile",
    "tragic", "tragedy", "devastating",
    "victim", "victims",
    "missing", "disappeared",
    "passed", "loss", "lost", "mourning",
]

FEEDS = {
    "Breaking": [
        ("BBC Front Page", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/front_page/rss.xml"),
        ("CNN Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
    ],
    "Business": [
        ("BBC Business", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/business/rss.xml"),
        ("Guardian Business", "https://www.theguardian.com/business/rss"),
    ],
}

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()

def is_tragic(title):
    t = title.lower()
    return any(word in t for word in TRAGEDY_KEYWORDS)

def parse_feed(source, url):
    feed = feedparser.parse(url)
    items = []
    for e in feed.entries[:50]:
        title = clean(getattr(e, "title", ""))
        link = getattr(e, "link", "")
        if title and link:
            items.append({
                "title": title,
                "url": link,
                "source": source,
            })
    return items

def main():
    used_urls = set()
    used_snark = set()
    now = datetime.now(timezone.utc)

    columns = [{"sections": []}]

    for section_name, feeds in FEEDS.items():
        raw_items = []
        for src, url in feeds:
            raw_items.extend(parse_feed(src, url))

        section_items = []
        per_source = {}

        for item in raw_items:
            if item["url"] in used_urls:
                continue

            src = item["source"]
            per_source[src] = per_source.get(src, 0)
            if per_source[src] >= MAX_PER_SOURCE_PER_SECTION:
                continue

            tragic = is_tragic(item["title"])
            if tragic:
                snark = random.choice(NEUTRAL)
            else:
                choices = [s for s in SNARK if s not in used_snark]
                if not choices:
                    choices = NEUTRAL
                snark = random.choice(choices)
                used_snark.add(snark)

            used_urls.add(item["url"])
            per_source[src] += 1

            section_items.append({
                "title": item["title"],
                "url": item["url"],
                "source": item["source"],
                "badge": "BREAK" if section_name == "Breaking" and not section_items else "",
                "feature": section_name == "Breaking" and not section_items,
                "snark": snark,
            })

            if len(section_items) >= MAX_ITEMS_PER_SECTION:
                break

        columns[0]["sections"].append({
            "name": section_name,
            "items": section_items,
        })

    output = {
        "site": {
            "name": "THE DAILY SIDE-EYE",
            "tagline": "Headlines with a raised eyebrow.",
        },
        "generated_utc": now.isoformat(),
        "columns": columns,
    }

    with open("headlines.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

if __name__ == "__main__":
    main()