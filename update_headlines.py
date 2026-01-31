import json
import random
import re
from datetime import datetime, timezone
import feedparser

# --------------------------------------------
# CONFIG
# --------------------------------------------
MAX_ITEMS_PER_SECTION = 18
MAX_PER_SOURCE_PER_SECTION = 3

# Breaking refreshes every run.
# All other sections refresh only on UTC hours divisible by 3.
# (Your GitHub Actions runner uses UTC by default.)
def should_refresh(section_name: str, now_utc: datetime) -> bool:
    if section_name == "Breaking":
        return True
    return (now_utc.hour % 3 == 0)

# --------------------------------------------
# RSS FEEDS (expanded, less BBC-heavy)
# --------------------------------------------
BREAKING_FEEDS = [
    ("AP Top News", "https://apnews.com/apf-topnews?output=rss"),
    ("Reuters World", "https://feeds.reuters.com/Reuters/worldNews"),
    ("CNN Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
    ("BBC Front Page", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/front_page/rss.xml"),
]

TOP_FEEDS = [
    ("Reuters World", "https://feeds.reuters.com/Reuters/worldNews"),
    ("AP Top News", "https://apnews.com/apf-topnews?output=rss"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
    ("Guardian World", "https://www.theguardian.com/world/rss"),
    ("BBC World", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/world/rss.xml"),
]

BUSINESS_FEEDS = [
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("BBC Business", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/business/rss.xml"),
]

TECH_FEEDS = [
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Wired", "https://www.wired.com/feed/rss"),
    ("Reuters Technology", "https://feeds.reuters.com/reuters/technologyNews"),
    ("BBC Tech", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/technology/rss.xml"),
]

WEIRD_FEEDS = [
    ("Reuters Oddly Enough", "https://feeds.reuters.com/reuters/oddlyEnoughNews"),
    ("Smithsonian", "https://www.smithsonianmag.com/rss/latest_articles/"),
    ("BBC Science", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/sci/tech/rss.xml"),
]

# 3 columns: (1) Breaking + Top, (2) Business, (3) Tech + Weird
LAYOUT = [
    [("Breaking", BREAKING_FEEDS), ("Top", TOP_FEEDS)],
    [("Business", BUSINESS_FEEDS)],
    [("Tech", TECH_FEEDS), ("Weird", WEIRD_FEEDS)],
]

# --------------------------------------------
# COPY POOLS
# --------------------------------------------
SNARK_POOL = [
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
    "An update arrived. Clarity did not.",
    "Strong words were used. Outcomes remain TBD.",
    "Everyone is monitoring the situation.",
    "Talks were constructive. Feelings were shared.",
    "A framework is emerging. It will be revisited.",
]

# STRICT tragedy-safe sublines (no cadence, no jokes, no “as of now”)
TRAGEDY_SUBLINES = [
    "Authorities are investigating.",
    "Details are still emerging.",
    "Reporting continues.",
    "More information is expected.",
    "This is a developing situation.",
    "Updates will follow.",
]

# Expanded tragedy keywords (for safety)
TRAGEDY_KEYWORDS = [
    "dead", "death", "dies", "died", "killed", "kill", "fatal",
    "passed", "pass away", "loss", "lost", "mourning", "funeral",
    "injured", "hurt", "pain", "sorrow", "sad", "grief",
    "shooting", "shot", "stabbed", "attack", "assault", "murder",
    "fire", "burn", "explosion", "blast", "crash", "collision",
    "war", "airstrike", "bomb", "terror", "hostage", "massacre",
    "missing", "disaster", "tragedy", "victim", "hospitalized",
    "collapse", "collapsed",
]

# Ages-poorly triggers (non-tragic only, and ONLY Business + Tech)
AGES_POORLY_TRIGGERS = [
    "will", "could", "may", "might", "expected", "plan", "deal", "talks",
    "nominee", "rates", "inflation", "election", "forecast", "poll",
    "set to", "aims to",
]

LANGUAGE_WATCH_TERMS = [
    ("Developing", r"\bdevelop\w*\b"),
    ("Sources say", r"\bsources?\s+(say|said)\b"),
    ("Under review", r"\bunder\s+review\b"),
    ("Officials said", r"\bofficials?\s+(say|said)\b"),
    ("Expected to", r"\bexpected\s+to\b"),
]

MISSED_TRIGGERS = [
    "familiar with the matter",
    "sources say",
    "sources said",
    "according to",
    "officials said",
    "spokesperson",
    "statement",
    "under review",
]

NOTHING_BURGER_TRIGGERS = [
    "talks", "discuss", "discussion", "meet", "meeting", "negotiat",
    "consider", "review", "framework", "plan", "proposal", "weigh",
    "signal", "aims to", "expected", "set to",
]

# --------------------------------------------
# HELPERS
# --------------------------------------------
def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

def parse_feed(source_name: str, url: str):
    out = []
    f = feedparser.parse(url)
    for e in getattr(f, "entries", [])[:100]:
        title = clean(getattr(e, "title", ""))
        link = getattr(e, "link", "")
        if title and link:
            out.append({"title": title, "url": link, "source": source_name})
    return out

def is_tragic(title: str) -> bool:
    t = normalize(title)
    return any(k in t for k in TRAGEDY_KEYWORDS)

def build_language_watch(all_titles):
    joined = "\n".join(all_titles).lower()
    rows = []
    for label, pattern in LANGUAGE_WATCH_TERMS:
        try:
            n = len(re.findall(pattern, joined, flags=re.IGNORECASE))
        except Exception:
            n = 0
        rows.append({"label": label, "count": n})
    rows.sort(key=lambda x: (-x["count"], x["label"]))
    nonzero = [r for r in rows if r["count"] > 0]
    return nonzero[:5] if nonzero else rows[:3]

def pick_one_line_missed(candidates, day_seed):
    matches = []
    for it in candidates:
        t = normalize(it.get("title", ""))
        if any(trig in t for trig in MISSED_TRIGGERS):
            matches.append(it)

    pool = matches if matches else [it for it in candidates if not it.get("tragic")]
    if not pool:
        pool = candidates[:]

    if not pool:
        return None

    return pool[day_seed % len(pool)]

def pick_nothing_burger(candidates, day_seed):
    pool = []
    for it in candidates:
        if it.get("tragic"):
            continue
        sec = it.get("section")
        if sec not in ["Top", "Business", "Tech"]:
            continue
        t = normalize(it.get("title", ""))
        if any(trig in t for trig in NOTHING_BURGER_TRIGGERS):
            pool.append(it)

    if not pool:
        pool = [it for it in candidates if (not it.get("tragic")) and it.get("section") in ["Top", "Business", "Tech"]]

    if not pool:
        return None

    return pool[(day_seed * 3 + 7) % len(pool)]

# --------------------------------------------
# MAIN
# --------------------------------------------
def main():
    prev = None
    try:
        with open("headlines.json", "r", encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        prev = None

    now = datetime.now(timezone.utc)
    day_seed = int(now.strftime("%Y%m%d"))

    used_urls = set()
    used_sublines = set()

    snark_pool = SNARK_POOL[:]
    random.shuffle(snark_pool)

    columns = []
    ages_candidates = []     # list of urls eligible for "IF THIS AGES POORLY"
    today_candidates = []    # for missed/burger/language watch

    for col in LAYOUT:
        col_out = {"sections": []}

        for section_name, feeds in col:
            refresh = should_refresh(section_name, now)

            # Reuse previous section if not refreshing
            if not refresh and prev:
                reused = False
                reused_section = None
                for pcol in prev.get("columns", []):
                    for psec in pcol.get("sections", []):
                        if psec.get("name") == section_name:
                            reused_section = psec
                            col_out["sections"].append(psec)
                            reused = True
                            break
                    if reused:
                        break

                if reused and reused_section:
                    for it in reused_section.get("items", []):
                        today_candidates.append({
                            "title": it.get("title", ""),
                            "url": it.get("url", ""),
                            "source": it.get("source", ""),
                            "section": section_name,
                            "tragic": is_tragic(it.get("title", "")),
                        })
                    continue

            # Pull fresh
            raw = []
            for src_name, url in feeds:
                raw.extend(parse_feed(src_name, url))

            items = []
            per_source = {}

            for i, it in enumerate(raw):
                url = it["url"]
                src = it["source"]
                title = it["title"]

                if url in used_urls:
                    continue

                per_source[src] = per_source.get(src, 0)
                if per_source[src] >= MAX_PER_SOURCE_PER_SECTION:
                    continue

                tragic = is_tragic(title)

                # Subheadline assignment
                if tragic:
                    sub = random.choice(TRAGEDY_SUBLINES)
                else:
                    # Use snark, but ensure unique across page
                    if snark_pool:
                        sub = snark_pool.pop()
                    else:
                        # fallback: reuse snark pool in a shuffled cycle without duplicating if possible
                        sub = random.choice(SNARK_POOL)

                    tries = 0
                    while sub in used_sublines and tries < 20:
                        sub = random.choice(SNARK_POOL)
                        tries += 1

                used_sublines.add(sub)

                item = {
                    "title": title,
                    "url": url,
                    "source": src,
                    "badge": "BREAK" if (section_name == "Breaking" and len(items) == 0) else "",
                    "feature": True if (section_name == "Breaking" and len(items) == 0) else False,
                    "snark": sub,
                    "ages_poorly": False,
                }

                # Ages poorly candidates ONLY in Business + Tech, non-tragic
                if section_name in ["Business", "Tech"] and not tragic:
                    t = title.lower()
                    if any(w in t for w in AGES_POORLY_TRIGGERS):
                        ages_candidates.append(url)

                items.append(item)
                used_urls.add(url)
                per_source[src] += 1

                today_candidates.append({
                    "title": title,
                    "url": url,
                    "source": src,
                    "section": section_name,
                    "tragic": tragic,
                })

                if len(items) >= MAX_ITEMS_PER_SECTION:
                    break

            col_out["sections"].append({"name": section_name, "items": items})

        columns.append(col_out)

    # Mark exactly one item/day as "IF THIS AGES POORLY"
    if ages_candidates:
        pick = ages_candidates[day_seed % len(ages_candidates)]
        for col in columns:
            for sec in col.get("sections", []):
                for it in sec.get("items", []):
                    if it.get("url") == pick:
                        it["ages_poorly"] = True

    missed = pick_one_line_missed(today_candidates, day_seed)
    burger = pick_nothing_burger(today_candidates, day_seed)
    language_watch = build_language_watch([c.get("title", "") for c in today_candidates])

    out = {
        "site": {"name": "THE DAILY SIDE-EYE", "tagline": "Headlines with a raised eyebrow."},
        "generated_utc": now.isoformat(),
        "columns": columns,
        "one_line_everyone_missed": missed,
        "nothing_burger": burger,
        "language_watch": language_watch,
        "week_in_hindsight": [
            "Language repeats. So does the news.",
            "One 'If This Ages Poorly' is selected daily from Business/Tech only.",
        ],
    }

    with open("headlines.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

if __name__ == "__main__":
    main()