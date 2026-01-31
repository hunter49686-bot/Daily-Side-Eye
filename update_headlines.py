import json
import random
import re
from datetime import datetime, timezone, timedelta
import feedparser

MAX_ITEMS_PER_SECTION = 18
MAX_PER_SOURCE_PER_SECTION = 3

HISTORY_FILE = "history.json"
HISTORY_MAX_DAYS = 10

# ================= RSS FEEDS =================
BREAKING_FEEDS = [
    ("BBC Front Page", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/front_page/rss.xml"),
    ("CNN Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
]

TOP_FEEDS = [
    ("BBC World", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/world/rss.xml"),
    ("Guardian US", "https://www.theguardian.com/us/rss"),
    ("Reuters World", "https://feeds.reuters.com/Reuters/worldNews"),
]

BUSINESS_FEEDS = [
    ("BBC Business", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/business/rss.xml"),
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
]

TECH_FEEDS = [
    ("BBC Tech", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/technology/rss.xml"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
]

WEIRD_FEEDS = [
    ("Reuters Oddly Enough", "https://feeds.reuters.com/reuters/oddlyEnoughNews"),
    ("BBC Science", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/sci/tech/rss.xml"),
]

LAYOUT = [
    [("Breaking", BREAKING_FEEDS), ("Top", TOP_FEEDS)],
    [("Business", BUSINESS_FEEDS)],
    [("Tech", TECH_FEEDS), ("Weird", WEIRD_FEEDS)],
]

# ================= COPY =================
SNARK = [
    "A confident plan has been announced. Reality is pending.",
    "Officials say it is under control. So that is something.",
    "A decision was made. Consequences scheduled for later.",
    "Experts disagree, loudly and on schedule.",
    "The plan is simple. The details are complicated.",
    "Numbers were cited. Interpretation may vary.",
    "This will surely be handled with nuance.",
    "A statement was issued. Substance not included.",
    "A compromise is proposed. Someone will hate it.",
    "A timeline was provided. Nobody believes it.",
    "A win is declared. The scoreboard is unavailable.",
    "A review is underway.",
]

NEUTRAL_BASE = [
    "Developing story.",
    "Details are still emerging.",
    "Authorities are investigating.",
    "Situation remains unclear.",
    "More information is expected.",
    "Reporting continues.",
    "This remains under review.",
]

VARIANT_PREFIX = [
    "At present,",
    "Currently,",
    "For now,",
    "As things stand,",
    "At the moment,"
]

VARIANT_SUFFIX = [
    "more information is expected.",
    "details are still being verified.",
    "confirmation is pending.",
    "reporting continues.",
    "this remains under review.",
]

TRAGEDY_KEYWORDS = [
    "dead","death","dies","died","killed","kill","fatal","passed","loss","lost",
    "injured","hurt","pain","suffering","shooting","stabbed","attack","murder",
    "fire","explosion","crash","war","airstrike","bomb","tragic","victim",
    "missing","hospitalized","mourning","funeral"
]

SIDE_EYE_TRIGGERS = [
    "officials","sources","reportedly","claims","denies","investigation","review",
    "plan","strategy","announced","timeline","deal","talks","warning","court",
    "inflation","rates","central bank","fed","election","lawsuit"
]

AGES_POORLY_TRIGGERS = [
    "will","could","may","might","expected","plan","deal","talks","nominee",
    "rates","inflation","election","forecast"
]

# ================= HELPERS =================
def clean(t): return re.sub(r"\s+", " ", t or "").strip()

def is_tragic(title):
    t = title.lower()
    return any(k in t for k in TRAGEDY_KEYWORDS)

def side_eye_score(title):
    t = title.lower()
    hits = sum(1 for k in SIDE_EYE_TRIGGERS if k in t)
    return max(1, min(5, hits + 1))

def neutral_unique(used, i):
    base = NEUTRAL_BASE[i % len(NEUTRAL_BASE)]
    text = f"{random.choice(VARIANT_PREFIX)} {base.lower()} {random.choice(VARIANT_SUFFIX)}"
    if text not in used:
        used.add(text)
        return text
    used.add(base)
    return base

def parse_feed(src, url):
    out = []
    f = feedparser.parse(url)
    for e in f.entries[:60]:
        if getattr(e, "title", None) and getattr(e, "link", None):
            out.append({"title": clean(e.title), "url": e.link, "source": src})
    return out

# ================= MAIN =================
def main():
    prev = None
    try:
        with open("headlines.json", "r", encoding="utf-8") as f:
            prev = json.load(f)
    except:
        pass

    now = datetime.now(timezone.utc)
    three_hour = now.hour % 3 == 0

    used_urls, used_sublines = set(), set()
    snark_pool = SNARK[:]
    random.shuffle(snark_pool)

    columns = []
    ages_candidates = []

    for col in LAYOUT:
        col_out = {"sections": []}
        for sec_name, feeds in col:
            refresh = sec_name == "Breaking" or three_hour
            if not refresh and prev:
                for pcol in prev["columns"]:
                    for psec in pcol["sections"]:
                        if psec["name"] == sec_name:
                            col_out["sections"].append(psec)
                            continue

            raw = []
            for s,u in feeds:
                raw.extend(parse_feed(s,u))

            items, per_source = [], {}
            for i,it in enumerate(raw):
                if it["url"] in used_urls: continue
                per_source[it["source"]] = per_source.get(it["source"],0)
                if per_source[it["source"]] >= MAX_PER_SOURCE_PER_SECTION: continue

                tragic = is_tragic(it["title"])
                if tragic:
                    sub = neutral_unique(used_sublines, i)
                else:
                    sub = snark_pool.pop() if snark_pool else neutral_unique(used_sublines,i)
                    used_sublines.add(sub)

                meter = side_eye_score(it["title"])
                if sec_name in ["Tech","Weird"]:
                    meter = max(1, meter-1)

                item = {
                    "title": it["title"],
                    "url": it["url"],
                    "source": it["source"],
                    "badge": "BREAK" if sec_name=="Breaking" and not items else "",
                    "feature": sec_name=="Breaking" and not items,
                    "snark": sub,
                    "meter": meter,
                    "ages_poorly": False
                }

                if sec_name in ["Top","Business"] and not tragic:
                    if any(w in it["title"].lower() for w in AGES_POORLY_TRIGGERS):
                        ages_candidates.append(it["url"])

                items.append(item)
                used_urls.add(it["url"])
                per_source[it["source"]] += 1
                if len(items)>=MAX_ITEMS_PER_SECTION: break

            col_out["sections"].append({"name": sec_name, "items": items})
        columns.append(col_out)

    if ages_candidates:
        pick = ages_candidates[sum(ord(c) for c in now.strftime("%Y%m%d")) % len(ages_candidates)]
        for col in columns:
            for sec in col["sections"]:
                for it in sec["items"]:
                    if it["url"] == pick:
                        it["ages_poorly"] = True

    out = {
        "site":{"name":"THE DAILY SIDE-EYE","tagline":"Headlines with a raised eyebrow."},
        "generated_utc": now.isoformat(),
        "columns": columns,
        "week_in_hindsight": ["Tracking patterns. Full week view builds over time."]
    }

    with open("headlines.json","w",encoding="utf-8") as f:
        json.dump(out,f,indent=2)

if __name__=="__main__":
    main()