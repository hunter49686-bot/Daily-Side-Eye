import json
import random
import re
from datetime import datetime, timezone
import feedparser

# -----------------------------
# CONFIG
# -----------------------------
MAX_ITEMS_PER_SECTION = 18
MAX_PER_SOURCE_PER_SECTION = 3

# Breaking refreshes every run. Others refresh only on UTC hours divisible by 3.
# (If you changed your cron/timezone in Actions, keep this as-is; it uses UTC inside runner.)
# -----------------------------

# -----------------------------
# RSS FEEDS
# -----------------------------
BREAKING_FEEDS = [
    ("BBC Front Page", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/front_page/rss.xml"),
    ("CNN Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
    ("AP Top News", "https://apnews.com/apf-topnews?output=rss"),
]

TOP_FEEDS = [
    ("BBC World", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/world/rss.xml"),
    ("Guardian US", "https://www.theguardian.com/us/rss"),
    ("Reuters World", "https://feeds.reuters.com/Reuters/worldNews"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
]

BUSINESS_FEEDS = [
    ("BBC Business", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/business/rss.xml"),
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("WSJ World News", "https://feeds.a.dj.com/rss/RSSWorldNews.xml"),
]

TECH_FEEDS = [
    ("BBC Tech", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/technology/rss.xml"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Wired", "https://www.wired.com/feed/rss"),
]

WEIRD_FEEDS = [
    ("Reuters Oddly Enough", "https://feeds.reuters.com/reuters/oddlyEnoughNews"),
    ("BBC Science", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/sci/tech/rss.xml"),
    ("Smithsonian", "https://www.smithsonianmag.com/rss/latest_articles/"),
]

# Layout: 3 columns. Breaking at top of column 1.
LAYOUT = [
    [("Breaking", BREAKING_FEEDS), ("Top", TOP_FEEDS)],
    [("Business", BUSINESS_FEEDS)],
    [("Tech", TECH_FEEDS), ("Weird", WEIRD_FEEDS)],
]

# -----------------------------
# COPY POOLS
# -----------------------------
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
    "A review is underway.",
    "An update arrived. Clarity did not.",
    "Strong words were used. Outcomes remain TBD.",
]

# One "prefix-style" neutral per section max (prevents repetitive cadence)
NEUTRAL_BASE = [
    "Developing story.",
    "Details are still emerging.",
    "Authorities are investigating.",
    "Situation remains unclear.",
    "More information is expected.",
    "Reporting continues.",
    "This remains under review.",
]

PREFIXES = [
    "At present,",
    "Currently,",
    "For now,",
    "As things stand,",
    "At the moment,",
]

SUFFIXES = [
    "more information is expected.",
    "details are still being verified.",
    "confirmation is pending.",
    "reporting continues.",
    "this remains under review.",
]

# Short neutrals after that (no repeated “As of now/So far” rhythm)
SOFT_NEUTRALS = [
    "More information expected.",
    "Reporting continues.",
    "Further details pending.",
    "Updates may follow.",
    "Confirmation pending.",
    "Still developing.",
    "More soon.",
    "Details pending.",
]

# Expanded tragedy keywords (respectful neutral only)
TRAGEDY_KEYWORDS = [
    "dead", "death", "dies", "died", "killed", "kill", "fatal",
    "passed", "pass away", "loss", "lost", "mourning", "funeral",
    "injured", "hurt", "pain", "sorrow", "sad", "grief",
    "shooting", "shot", "stabbed", "attack", "assault", "murder",
    "fire", "burn", "explosion", "blast", "crash", "collision",
    "war", "airstrike", "bomb", "terror", "hostage", "massacre",
    "missing", "disaster", "tragedy", "victim", "hospitalized",
]

# "If this ages poorly" candidates (non-tragic only, Top/Business only)
AGES_POORLY_TRIGGERS = [
    "will", "could", "may", "might", "expected", "plan", "deal", "talks",
    "nominee", "rates", "inflation", "election", "forecast", "poll",
]

# Language Watch terms (counts shown in footer)
LANGUAGE_WATCH_TERMS = [
    ("Developing", r"\bdevelop\w*\b"),
    ("Sources say", r"\bsources?\s+(say|said)\b"),
    ("Under review", r"\bunder\s+review\b"),
    ("Officials said", r"\bofficials?\s+(say|said)\b"),
    ("Expected to", r"\bexpected\s+to\b"),
]

# “One Line Everyone Missed” triggers (pick one headline containing these)
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

# Nothing Burger triggers (pick one headline that is inherently empty)
NOTHING_BURGER_TRIGGERS = [
    "talks",
    "discuss",
    "discussion",
    "meet",
    "meeting",
    "negotiat",
    "consider",
    "review",
    "framework",
    "plan",
    "proposal",
    "weigh",
    "weighs",
    "signal",
    "aims to",
    "expected",
    "set to",
]

# -----------------------------
# HELPERS
# -----------------------------
def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()

def parse_feed(source_name, url):
    out = []
    f = feedparser.parse(url)
    for e in getattr(f, "entries", [])[:80]:
        title = clean(getattr(e, "title", ""))
        link = getattr(e, "link", "")
        if title and link:
            out.append({"title": title, "url": link, "source": source_name})
    return out

def is_tragic(title):
    t = (title or "").lower()
    return any(k in t for k in TRAGEDY_KEYWORDS)

def one_prefix_neutral(used_sublines, idx):
    base = NEUTRAL_BASE[idx % len(NEUTRAL_BASE)]
    s = f"{random.choice(PREFIXES)} {base.lower()} {random.choice(SUFFIXES)}"
    tries = 0
    while s in used_sublines and tries < 10:
        s = f"{random.choice(PREFIXES)} {random.choice(NEUTRAL_BASE).lower()} {random.choice(SUFFIXES)}"
        tries += 1
    used_sublines.add(s)
    return s

def soft_neutral(used_sublines):
    random.shuffle(SOFT_NEUTRALS)
    for s in SOFT_NEUTRALS:
        if s not in used_sublines:
            used_sublines.add(s)
            return s
    s = random.choice(SOFT_NEUTRALS)
    used_sublines.add(s)
    return s

def normalize_for_match(s):
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s

def build_language_watch(all_titles):
    joined = "\n".join((t or "") for t in all_titles).lower()
    rows = []
    for label, pattern in LANGUAGE_WATCH_TERMS:
        try:
            n = len(re.findall(pattern, joined, flags=re.IGNORECASE))
        except Exception:
            n = 0
        rows.append({"label": label, "count": n})
    # Sort by count desc, then label
    rows.sort(key=lambda x: (-x["count"], x["label"]))
    # Keep only non-zero; if all zero, keep top 3 with zeros
    nonzero = [r for r in rows if r["count"] > 0]
    if nonzero:
        return nonzero[:5]
    return rows[:3]

def pick_one_line_missed(candidates, day_seed):
    """
    candidates: list of dicts with title,url,source,section
    deterministically pick one per day among matches; fallback to any non-tragic.
    """
    matches = []
    for it in candidates:
        t = normalize_for_match(it.get("title", ""))
        if any(trig in t for trig in MISSED_TRIGGERS):
            matches.append(it)

    pool = matches if matches else [it for it in candidates if not it.get("tragic")]
    if not pool:
        pool = candidates[:]

    if not pool:
        return None

    idx = day_seed % len(pool)
    return pool[idx]

def pick_nothing_burger(candidates, day_seed):
    """
    Pick one per day from Business/Top candidates that look like empty process headlines.
    """
    pool = []
    for it in candidates:
        if it.get("tragic"):
            continue
        sec = it.get("section")
        if sec not in ["Top", "Business"]:
            continue
        t = normalize_for_match(it.get("title", ""))
        if any(trig in t for trig in NOTHING_BURGER_TRIGGERS):
            pool.append(it)

    if not pool:
        # fallback: any non-tragic from Top/Business
        pool = [it for it in candidates if (not it.get("tragic")) and it.get("section") in ["Top", "Business"]]

    if not pool:
        return None

    idx = (day_seed * 3 + 7) % len(pool)
    return pool[idx]

# -----------------------------
# MAIN
# -----------------------------
def main():
    prev = None
    try:
        with open("headlines.json", "r", encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        prev = None

    now = datetime.now(timezone.utc)
    three_hour = (now.hour % 3 == 0)
    day_seed = int(now.strftime("%Y%m%d"))

    used_urls = set()
    used_sublines = set()

    snark_pool = SNARK_POOL[:]
    random.shuffle(snark_pool)

    neutral_used_by_section = {}

    columns = []
    ages_candidates = []         # urls
    today_candidates = []        # for missed + nothing burger + language watch

    for col in LAYOUT:
        col_out = {"sections": []}

        for section_name, feeds in col:
            refresh = (section_name == "Breaking") or three_hour

            # Reuse previous section if not refreshing
            if not refresh and prev:
                reused = False
                for pcol in prev.get("columns", []):
                    for psec in pcol.get("sections", []):
                        if psec.get("name") == section_name:
                            col_out["sections"].append(psec)
                            reused = True
                            break
                    if reused:
                        break
                if reused:
                    # also add reused items to candidates for missed/nothing/language watch
                    for it in psec.get("items", []):
                        today_candidates.append({
                            "title": it.get("title",""),
                            "url": it.get("url",""),
                            "source": it.get("source",""),
                            "section": section_name,
                            "tragic": is_tragic(it.get("title","")),
                        })
                    continue

            neutral_used_by_section.setdefault(section_name, False)

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

                # Subheadline logic:
                # - Tragic: neutral only
                # - Non-tragic: snark preferred
                # - Only ONE prefix-neutral per section per run
                if tragic:
                    if not neutral_used_by_section[section_name]:
                        sub = one_prefix_neutral(used_sublines, i)
                        neutral_used_by_section[section_name] = True
                    else:
                        sub = soft_neutral(used_sublines)
                else:
                    if snark_pool:
                        sub = snark_pool.pop()
                        used_sublines.add(sub)
                    else:
                        sub = soft_neutral(used_sublines)

                item = {
                    "title": title,
                    "url": url,
                    "source": src,
                    "badge": "BREAK" if (section_name == "Breaking" and len(items) == 0) else "",
                    "feature": True if (section_name == "Breaking" and len(items) == 0) else False,
                    "snark": sub,
                    "ages_poorly": False,
                }

                # Ages poorly candidate (Top/Business only, non-tragic only)
                if section_name in ["Top", "Business"] and not tragic:
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

    # ONE LINE EVERYONE MISSED (deterministic per day)
    missed = pick_one_line_missed(today_candidates, day_seed)

    # NOTHING BURGER OF THE DAY (deterministic per day)
    burger = pick_nothing_burger(today_candidates, day_seed)

    # LANGUAGE WATCH (TODAY)
    titles_today = [c.get("title", "") for c in today_candidates]
    language_watch = build_language_watch(titles_today)

    out = {
        "site": {"name": "THE DAILY SIDE-EYE", "tagline": "Headlines with a raised eyebrow."},
        "generated_utc": now.isoformat(),
        "columns": columns,

        # Features 1–3 data
        "one_line_everyone_missed": missed,     # dict or None
        "nothing_burger": burger,               # dict or None
        "language_watch": language_watch,       # list of {label,count}

        # Keep your existing section for now (can be made real later)
        "week_in_hindsight": [
            "Language tends to repeat because newsrooms repeat. Today, you can see which phrases won.",
            "If this ages poorly is one per day, non-tragic by design.",
        ],
    }

    with open("headlines.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

if __name__ == "__main__":
    main()