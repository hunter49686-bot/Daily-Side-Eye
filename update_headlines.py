import json, re
from datetime import datetime, timezone
import feedparser

TRAGEDY_KEYWORDS = [
    "killed", "dead", "death", "deaths",
    "shooting", "shooter", "murder", "homicide",
    "war", "bomb", "bombing", "explosion", "attack",
    "crash", "crashes", "collision", "derail",
    "earthquake", "wildfire", "flood", "hurricane",
    "victim", "victims", "wounded", "injured",
    "terror"
]

NEUTRAL_FALLBACKS = [
    "Developing story.",
    "Details are still emerging.",
    "Authorities are investigating.",
    "Situation remains unclear."
]

def is_tragic(title: str) -> bool:
    t = title.lower()
    return any(word in t for word in TRAGEDY_KEYWORDS)

def neutral_line(i: int) -> str:
    return NEUTRAL_FALLBACKS[i % len(NEUTRAL_FALLBACKS)]


# --- EDIT THESE FEEDS ---
FEEDS = {
    "Top": [
        ("Reuters (Top)", "https://feeds.reuters.com/reuters/topNews"),
        ("AP News (Top)", "https://apnews.com/apf-topnews?output=rss"),
        ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ],
    "Business": [
        ("Reuters (Business)", "https://feeds.reuters.com/reuters/businessNews"),
        ("BBC Business", "http://feeds.bbci.co.uk/news/business/rss.xml"),
    ],
    "World / Tech / Weird": [
        ("BBC Tech", "http://feeds.bbci.co.uk/news/technology/rss.xml"),
        ("NPR", "https://feeds.npr.org/1001/rss.xml"),
    ],
}

SNARK = [
    "Strong statement. Details pending.",
    "Everyone is ‘monitoring the situation.’",
    "This will surely calm everyone down.",
    "A bold claim enters the chat.",
    "Nobody panicked. Publicly.",
]

def pick_snark(i: int) -> str:
    return SNARK[i % len(SNARK)]

def clean_title(t: str) -> str:
    t = re.sub(r"\s+", " ", t or "").strip()
    return t[:140]

def parse_feed(name, url):
    d = feedparser.parse(url)
    items = []

    for e in d.entries[:20]:
        title = clean_title(getattr(e, "title", ""))
        link = getattr(e, "link", "")

        # Try to find an RSS-provided image
        image = ""
        if hasattr(e, "media_thumbnail"):
            image = e.media_thumbnail[0].get("url", "")
        elif hasattr(e, "media_content"):
            image = e.media_content[0].get("url", "")
        elif hasattr(e, "enclosures") and e.enclosures:
            image = e.enclosures[0].get("href", "")

        if title and link:
            items.append({
                "title": title,
                "url": link,
                "source": name,
                "image": image
            })

    return items


def dedupe(items):
    seen = set()
    out = []
    for it in items:
        u = it["url"]
        if u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out

def main():
    columns = [{"sections": []}, {"sections": []}, {"sections": []}]
    section_names = ["Top", "Business", "World / Tech / Weird"]

    for idx, sec in enumerate(section_names):
        combined = []
        for src, feed_url in FEEDS.get(sec, []):
            combined.extend(parse_feed(src, feed_url))
        combined = dedupe(combined)[:12]

        items = []
       items.append({
    "title": it["title"],
    "url": it["url"],
    "source": it["source"],
    "image": it.get("image", ""),
    "badge": "TOP" if (sec == "Top" and i == 0) else "",
    "feature": True if (sec == "Top" and i == 0) else False,
    "snark": neutral_line(i) if is_tragic(it["title"]) else pick_snark(i)
})

        columns[idx]["sections"].append({"name": sec, "items": items})

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
