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
# RSS FEEDS (balanced, not all BBC)
# NOTE: Keep these aligned with what your site already shows.
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
    # If you’re using NYT in your repo already, keep it here:
    ("NYT HomePage", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"),
]

BUSINESS_FEEDS = [
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("BBC Business", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/business/rss.xml"),
    # Guardian business is often helpful for variety:
    ("Guardian Business", "https://www.theguardian.com/business/rss"),
]

TECH_FEEDS = [
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Wired", "https://www.wired.com/feed/rss"),
    ("Reuters Technology", "https://feeds.reuters.com/reuters/technologyNews"),
    ("BBC Tech", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/technology/rss.xml"),
    ("Guardian Tech", "https://www.theguardian.com/technology/rss"),
]

WEIRD_FEEDS = [
    ("Reuters Oddly Enough", "https://feeds.reuters.com/reuters/oddlyEnoughNews"),
    ("Smithsonian", "https://www.smithsonianmag.com/rss/latest_articles/"),
    ("BBC Science", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/sci/tech/rss.xml"),
    ("Guardian US", "https://www.theguardian.com/us-news/rss"),
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
    "Confidence is high. Evidence is pending.",
    "The optics are doing most of the work here.",
    "This is either a turning point or a rehearsal.",
    "A quick fix becomes the long-term architecture.",
    "The fine print is doing most of the work here.",
    "Everyone is calm. On paper.",
    "A big announcement, with a small footnote doing cardio.",
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

# Phrases from older versions you want to purge on reuse
OLD_NEUTRAL_PREFIXES = [
    "as of now:", "so far:", "at this point:", "for now:", "currently:",
]
OLD_NEUTRAL_FRAGMENTS = [
    "awaiting confirmation", "updates expected", "more as it develops",
    "early reports are still being verified", "key details remain unconfirmed",
    "context is still being gathered", "situation remains unclear",
]

# Expanded tragedy keywords (for safety)
TRAGEDY_KEYWORDS = [
    "dead", "death", "dies", "died", "killed", "kill", "fatal",
    "passed", "pass away", "loss", "lost", "mourning", "funeral",
    "injured", "hurt", "pain", "sorrow", "sad", "grief",
    "shooting", "shot", "stabbed", "attack", "assault", "murder",
    "fire", "burn", "explosion", "blast", "crash", "collision",
    "war", "airstrike", "air strike", "bomb", "terror", "hostage", "massacre",
    "missing", "disaster", "tragedy", "victim", "hospitalized",
    "collapse", "collapsed",
]

# Ages-poorly triggers (non-tragic only, and ONLY Business + Tech)
AGES_POORLY_TRIGGERS = [
    "will", "could", "may", "might", "expected", "plan", "deal", "talks",
    "nominee", "rates", "inflation", "election", "forecast", "poll",
    "set to", "aims to",
]

# Language Watch terms (counts shown in footer)
LANGUAGE_WATCH_TERMS = [
    ("Developing", r"\bdevelop\w*\b"),
    ("Sources say", r"\bsources?\s+(say|said)\b"),
    ("Under review", r"\bunder\s+review\b"),
    ("Officials said", r"\bofficials?\s+(say|said)\b"),
    ("Expected to", r"\bexpected\s+to\b"),
]

# “One Line Everyone Missed” triggers
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

# Nothing Burger triggers
NOTHING_BURGER_TRIGGERS = [
    "talks", "discuss", "discussion", "meet", "meeting", "negotiat",
    "consider", "review", "framework", "plan", "proposal", "weigh",
    "signal", "aims to", "expected", "set to",
]

# Stopwords for topic extraction
STOPWORDS = set("""
a an and are as at be by for from has have he her his i if in into is it its
just may more most much new not of on or our out over she so that the their
them then there these they this to too was we were what when where which who
will with you your vs via amid after before
""".split())

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
    for e in getattr(f, "entries", [])[:120]:
        title = clean(getattr(e, "title", ""))
        link = getattr(e, "link", "")
        if title and link:
            out.append({"title": title, "url": link, "source": source_name})
    return out

def is_tragic(title: str) -> bool:
    t = normalize(title)
    return any(k in t for k in TRAGEDY_KEYWORDS)

def shorten_title(t: str, max_len: int = 120) -> str:
    t = clean(t)
    return t if len(t) <= max_len else t[: max_len - 1].rstrip() + "…"

def looks_like_old_neutral(snark: str) -> bool:
    s = normalize(snark)
    if any(p in s for p in OLD_NEUTRAL_PREFIXES):
        return True
    if any(frag in s for frag in OLD_NEUTRAL_FRAGMENTS):
        return True
    return False

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
        # Prefer Business/Top for burger; allow fallback to Tech if needed
        if sec not in ["Business", "Top", "Tech"]:
            continue
        t = normalize(it.get("title", ""))
        if any(trig in t for trig in NOTHING_BURGER_TRIGGERS):
            pool.append(it)
    if not pool:
        pool = [it for it in candidates if (not it.get("tragic")) and it.get("section") in ["Business", "Top", "Tech"]]
    if not pool:
        return None
    return pool[(day_seed * 3 + 7) % len(pool)]

def extract_cap_phrases(title: str):
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

    seen = set()
    out = []
    for p in phrases:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out

def extract_keywords(title: str):
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
    Auto-generates 3 bullets based on topics most repeated in Breaking+Top.
    Ranked by:
      1) distinct sources mentioning topic
      2) total mentions
    """
    pool = [c for c in candidates if c.get("section") in ["Breaking", "Top"]]
    if not pool:
        return []

    topic_to_sources = {}
    topic_to_titles = {}

    for c in pool:
        title = c.get("title", "")
        src = c.get("source", "")
        # Topics: cap phrases, else a few keywords
        topics = extract_cap_phrases(title)
        kws = extract_keywords(title)[:3]

        for t in topics:
            key = t.lower()
            topic_to_sources.setdefault(key, set()).add(src)
            topic_to_titles.setdefault(key, []).append(title)

        if not topics:
            for kw in kws:
                key = kw.lower()
                topic_to_sources.setdefault(key, set()).add(src)
                topic_to_titles.setdefault(key, []).append(title)

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
        rep = sorted(titles, key=lambda s: len(s))[0] if titles else key
        rep = shorten_title(rep, 120)
        display = " ".join([w.capitalize() for w in key.split()]) if " " in key else key.capitalize()
        bullets.append(f"• {display}: {rep}")

    return bullets

def pick_unique_snark(used_sublines: set) -> str:
    # best-effort uniqueness; falls back if exhausted
    tries = 0
    while tries < 40:
        s = random.choice(SNARK_POOL)
        if s not in used_sublines:
            return s
        tries += 1
    return random.choice(SNARK_POOL)

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
    random.seed(day_seed + now.hour)

    used_urls = set()
    used_sublines = set()

    # start with a shuffled pool so the page “feels” fresh
    snark_pool = SNARK_POOL[:]
    random.shuffle(snark_pool)

    columns = []
    ages_candidates = []
    today_candidates = []

    def sanitize_item(section_name: str, it: dict):
        """Fix reused legacy fields so old neutral/cadence text can’t survive."""
        title = it.get("title", "")
        tragic = is_tragic(title)

        # enforce tragedy-safe tone
        if tragic:
            it["snark"] = random.choice(TRAGEDY_SUBLINES)
            it["ages_poorly"] = False
        else:
            # purge old neutral cadence lines from older versions
            if looks_like_old_neutral(it.get("snark", "")):
                it["snark"] = pick_unique_snark(used_sublines)

        # ages poorly ONLY Business/Tech
        if section_name not in ["Business", "Tech"]:
            it["ages_poorly"] = False

        # collect sublines to avoid duplicates
        if it.get("snark"):
            used_sublines.add(it["snark"])

        return tragic

    for col in LAYOUT:
        col_out = {"sections": []}

        for section_name, feeds in col:
            refresh = should_refresh(section_name, now)

            # Reuse previous section if not refreshing — but SANITIZE so old content can't linger
            if not refresh and prev:
                reused_section = None
                for pcol in prev.get("columns", []):
                    for psec in pcol.get("sections", []):
                        if psec.get("name") == section_name:
                            reused_section = psec
                            break
                    if reused_section:
                        break

                if reused_section:
                    # sanitize reused items
                    for it in reused_section.get("items", []):
                        tragic = sanitize_item(section_name, it)
                        today_candidates.append({
                            "title": it.get("title", ""),
                            "url": it.get("url", ""),
                            "source": it.get("source", ""),
                            "section": section_name,
                            "tragic": tragic,
                        })

                    col_out["sections"].append(reused_section)
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
                    if snark_pool:
                        sub = snark_pool.pop()
                        if sub in used_sublines:
                            sub = pick_unique_snark(used_sublines)
                    else:
                        sub = pick_unique_snark(used_sublines)

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

                # Ages poorly candidates ONLY Business + Tech, non-tragic
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

    # Mark exactly one item/day as "IF THIS AGES POORLY" (Business/Tech only)
    if ages_candidates:
        pick = ages_candidates[day_seed % len(ages_candidates)]
        for col in columns:
            for sec in col.get("sections", []):
                sec_name = sec.get("name")
                for it in sec.get("items", []):
                    if it.get("url") == pick and sec_name in ["Business", "Tech"] and (not is_tragic(it.get("title", ""))):
                        it["ages_poorly"] = True

    # Feature: One Line Everyone Missed
    missed = pick_one_line_missed(today_candidates, day_seed)

    # Feature: Nothing Burger of the Day
    burger = pick_nothing_burger(today_candidates, day_seed)

    # Feature: Language Watch
    language_watch = build_language_watch([c.get("title", "") for c in today_candidates])

    # Week in Hindsight (auto from Breaking+Top)
    week_in_hindsight = build_week_in_hindsight(today_candidates)
    if not week_in_hindsight:
        week_in_hindsight = [
            "• Not enough overlap yet to summarize. Check back after the next refresh.",
            "• Breaking updates more often than other sections by design.",
            "• Business/Tech get the one daily 'If This Ages Poorly' tag.",
        ]

    out = {
        "site": {"name": SITE_NAME, "tagline": TAGLINE},
        "generated_utc": now.isoformat(),
        "columns": columns,
        "one_line_everyone_missed": missed,
        "nothing_burger": burger,
        "language_watch": language_watch,
        "week_in_hindsight": week_in_hindsight,
    }

    with open("headlines.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

if __name__ == "__main__":
    main()