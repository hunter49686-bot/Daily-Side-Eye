import json
import re
from datetime import datetime, timezone

import feedparser

FEEDS = {
    "Top": [
        ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
    ],
    "Business": [
        ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
        ("NPR Business", "https://feeds.npr.org/1006/rss.xml"),
    ],
    "World / Tech / Weird": [
        ("BBC Tech", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
        ("NPR Technology", "https://feeds.npr.org/1019/rss.xml"),
    ],
}

SNARK = [
    "Strong statement. Details pending.",
    "Everyone is monitoring the situation.",
    "This will surely calm everyone down.",
    "A bold claim enters the chat.",
    "Nobody panicked. Publicly.",
]

TRAGEDY_KEYWORDS = [
    "killed", "dead", "death", "deaths",
    "shooting", "shooter", "murder", "homicide",
    "war", "bomb", "bombing", "explosion", "attack",
    "crash", "collision", "derail",
    "earthquake", "wildfire", "flood", "hurricane",
    "victim", "victims", "wounded", "injured",
    "terror",
]

NEUTRAL_FALLBACKS = [
    "Developing story.",
    "Details are still emerging.",
    "Authorities are investigating.",
    "Situation remains unclear.",
]

def clean_title(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:160]

def pick_snark(i):
    return SNARK[i % len(SNARK)]

def is_tragic(title):
    t = (title or "").lower()
    return any(word in t for word in TRAGEDY_KEYWORDS)

def neutral_line(i):
    return NEUTRAL_FALLBACKS[i % len(NEUTRAL_FALLBACKS)]

def parse_feed(source_name, feed_url):
    items = []
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:25]:
            title = clean_title(getattr(entry, "title", ""))
            link = getattr(entry, "link", "")
            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "source": source_name,
                })
    except Exception:
        return []
    return items

def dedupe(items):
    seen = set()
    result = []
    for item in items:
        url = item.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        result.append(item)
    return result

def main():
    section_names = ["Top", "Business", "World / Tech / Weird"]
    columns = [{"sections": []}, {"sections": []}, {"sections": []}]

    for idx, section in enumerate(section_names):
        combined = []
        for source, feed_url in FEEDS.get(section, []):
            combined.extend(parse_feed(source, feed_url))

        combined = dedupe(combined)[:12]

        rendered = []
        for i, item in enumerate(combined):
            title = item["title"]
            rendered.append({
                "title": title,
                "url": item["url"],
                "source": item["source"],
                "badge": "TOP" if section == "Top" and i == 0 else "",
                "feature": section == "Top" and i == 0,
                "snark": neutral_line(i) if is_tragic(title) else pick_snark(i),
            })

        columns[idx]["sections"].append({
            "name": section,
            "items": rendered,
        })

    data = {
        "site": {
            "name": "THE DAILY SIDE-EYE",
            "tagline": "Dry news links. Equal-opportunity skepticism.",
        },
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "columns": columns,
    }

    with open("headlines.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()