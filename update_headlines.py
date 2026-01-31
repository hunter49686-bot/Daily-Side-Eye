import json
import re
from datetime import datetime, timezone

import feedparser

# -----------------------------
# RSS FEEDS (keep these simple)
# Use HTTPS wherever possible.
# -----------------------------
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
    "Everyone is ‘monitoring the situation.’",
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
    "terror"
]

NEUTRAL_FALLBACKS = [
    "Developing story.",
    "Details are still emerging.",
    "Authorities are investigating.",
    "Situation remains unclear.",
]

def clean_title(t: str) -> str:
    t = re.sub(r"\s+", " ", (t or "")).strip()
    return t[:160]

def pick_snark(i: int) -> str:
    return SNARK[i % len(SNARK)]

def is_tragic(title: str) -> bool:
    t = (title or "").lower()
    return any(word in t for word in TRAGEDY_KEYWORDS)

def neutral_line(i: int) -> str:
    return NEUTRAL_FALLBACKS[i % len(NEUTRAL_FALLBACKS)]

def parse_feed(source_name: str, feed_url: str):
    """
    Returns a list of dicts: {title, url, source}
    This function is defensive: it never raises, it just returns fewer items.
    """
    items = []
    try:
        d = feedparser.parse(feed_url)
        for e in getattr(d, "entries", [])[:25]:
            title = clean_title(getattr(e, "title", ""))
            link = getattr(e, "link", "")
            if title and link:
                items.append({"title": title, "url": link, "source": source_name})
    except Exception:
        # If a feed is down or malformed, just skip it.
        return []
    return items

def dedupe(items):
    seen = set()
    out = []
    for it in items:
        u = it.get("url", "")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out

def main():
    section_names = ["Top", "Business", "World / Tech / Weird"]
    columns = [{"sections": []}, {"sections": []}, {"sections": []}]

    for idx, sec in enumerate(section_names):
        combined = []
        for src, feed_url in FEEDS.get(sec, []):
            combined.extend(parse_feed(src, feed_url))

        combined = dedupe(combined)[:12]

        rendered_items = []
        for i, it in enumerate(combined):
            title = it["title"]
            rendered_items.append({
                "title": title,
                "url": it["url"],
                "source": it["source"],
                "badge": "TOP" if (sec == "Top" and i == 0) else "",
                "feature": True if (sec == "Top" and i == 0) else False,
                "snark": neutral_line(i) if is_tragic(title) else pick_snark(i),
            })

        columns[idx]["sections"].append({"name": sec, "items": rendered_items})

    data = {
        "site": {
            "name": "THE DAILY SIDE-EYE",
            "tagline": "Dry news links. Equal-opportunity skepticism."
        },
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "columns": columns
    }

    with open("headlines.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()