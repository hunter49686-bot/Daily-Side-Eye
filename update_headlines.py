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

SITE_NAME = "THE DAILY SIDE-EYE"
TAGLINE = "Headlines with a raised eyebrow."

# Breaking refreshes every run.
# All other sections refresh only on UTC hours divisible by 3.
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

# STRICT tragedy-safe sublines (no cadence, no jokes)
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

def shorten_title(t: str, max_len: int = 115) -> str:
    t = clean(t)
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"

# Stopwords for topic extraction (keep it simple and safe)
STOPWORDS = set("""
a an and are as at be by for from has have he her his i if in into is it its
just may more most much new not of on or our out over she so that the their
them then there these they this to too was we were what when where which who
will with you your vs via amid after before
""".split())

def extract_cap_phrases(title: str):
    # Pull sequences of 1-4 TitleCase words: "Federal Reserve", "Donald Trump"
    # Avoid very short junk.
    words = re.findall(r"[A-Za-z][A-Za-z'\-]+", title)
    phrases = []
    buf = []

    def flush():
        nonlocal buf
        if 1 <= len(buf) <= 4:
            phrase = " ".join(buf)
            if len(phrase) >= 4:
                phrases.append(phrase)
        buf = []

    for w in words:
        if w[0].isupper() and (w.lower() not in STOPWORDS):
            buf.append(w)
        else:
            flush()
    flush()
    # De-dupe while preserving order
    seen = set()
    out = []
    for p in phrases:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out

def extract_keywords(title: str):
    # Lowercase tokens >=4 chars, excluding stopwords.
    tokens = re.findall(r"[a-zA-Z][a-zA-Z'\-]+", title.lower())
    out = []
    for tok in tokens:
        tok = tok.strip("-'")
        if len(tok) < 4:
            continue
        if tok in STOPWORDS:
            continue
        out.append(tok)
    return out

def build_week_in_hindsight(candidates):
    """
    candidates: list of dicts with keys: title, source, section, tragic
    We will focus on Breaking + Top only.
    Rank topics by:
      1) number of distinct sources that mention the topic
      2) total mentions
    Then create 3 bullets with representative headlines (neutral wording).
    """
    pool = [c for c in candidates if c.get("section") in ["Breaking", "Top"]]
    if not pool:
        return []

    topic_to_sources = {}
    topic_to_titles = {}

    for c in pool:
        title = c.get("title", "")
        src = c.get("source", "")

        # Candidate topics: capitalized phrases first, plus a few keywords
        topics = extract_cap_phrases(title)
        kws = extract_keywords(title)[:3]  # keep small to avoid noisy topics

        # Normalize and add
        for t in topics:
            key = t.lower()
            topic_to_sources.setdefault(key, set()).add(src)
            topic_to_titles.setdefault(key, []).append(title)

        # For keywords, only use if we have no cap phrases (helps with "Epstein", etc.)
        if not topics:
            for kw in kws:
                key = kw.lower()
                topic_to_sources.setdefault(key, set()).add(src)
                topic_to_titles.setdefault(key, []).append(title)

    # Filter out extremely generic topics
    def is_generic(key: str) -> bool:
        k = key.lower()
        if k in STOPWORDS:
            return True
        if k in ["today", "week", "says", "said", "live", "update", "updates", "news"]:
            return True
        return False

    scored = []
    for key, srcs in topic_to_sources.items():
        if is_generic(key):
            continue
        titles = topic_to_titles.get(key, [])
        if not titles:
            continue
        scored.append((len(srcs), len(titles), key))

    if not scored:
        return []

    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))

    # Pick top 3 distinct topics (avoid near-duplicates by substring)
    picked = []
    picked_keys = []
    for src_count, mention_count, key in scored:
        if len(picked) >= 3:
            break
        if any(key in pk or pk in key for pk in picked_keys):
            continue
        picked_keys.append(key)
        picked.append(key)

    bullets = []
    for key in picked:
        titles = topic_to_titles.get(key, [])
        # representative headline: shortest title that contains the topic
        rep = sorted(titles, key=lambda s: len(s))[0] if titles else key
        rep = shorten_title(rep, 120)

        # Friendly display name
        display = " ".join([w.capitalize() for w in key.split()]) if " " in key else key.capitalize()

        # Build neutral bullet
        bullets.append(f"• {display}: {rep}")

    return bullets

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
    random.seed(day_seed + now.hour)  # small drift, stable within hour

    used_urls = set()
    used_sublines = set()

    snark_pool = SNARK_POOL[:]
    random.shuffle(snark_pool)

    columns = []
    ages_candidates = []      # list of urls eligible for "IF THIS AGES POORLY"
    today_candidates = []     # for week_in_hindsight and other meta features

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

            for it in raw:
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
                    # Use snark, ensure unique across page best-effort
                    if snark_pool:
                        sub = snark_pool.pop()
                    else:
                        sub = random.choice(SNARK_POOL)

                    tries = 0
                    while sub in used_sublines and tries < 25:
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

    # Auto-generate Week in Hindsight based on most repeated Breaking/Top topics
    week_in_hindsight = build_week_in_hindsight(today_candidates)
    if not week_in_hindsight:
        week_in_hindsight = [
            "• Top stories rotated quickly today. Check back after the next refresh.",
            "• Breaking updates more often than the other sections by design.",
            "• If this ages poorly appears once per day (Business/Tech only).",
        ]

    out = {
        "site": {"name": SITE_NAME, "tagline": TAGLINE},
        "generated_utc": now.isoformat(),
        "columns": columns,
        "week_in_hindsight": week_in_hindsight,
    }

    with open("headlines.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

if __name__ == "__main__":
    main()