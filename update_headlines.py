import json
import random
import re
from datetime import datetime, timezone, timedelta

import feedparser

# =====================
# TUNING
# =====================
MAX_ITEMS_PER_SECTION = 18
MAX_PER_SOURCE_PER_SECTION = 3  # lower = more diversity

HISTORY_FILE = "history.json"
HISTORY_MAX_DAYS = 10  # keep small for a static repo

# =====================
# RSS FEEDS
# =====================
BREAKING_FEEDS = [
    ("BBC Front Page", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/front_page/rss.xml"),
    ("BBC World", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/world/rss.xml"),
    ("CNN Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
    ("NYT HomePage", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"),
    ("Guardian World", "https://www.theguardian.com/world/rss"),
]

TOP_FEEDS = [
    ("BBC World", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/world/rss.xml"),
    ("Guardian US", "https://www.theguardian.com/us/rss"),
    ("NYT HomePage", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"),
    ("Reuters World", "https://feeds.reuters.com/Reuters/worldNews"),
]

BUSINESS_FEEDS = [
    ("BBC Business", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/business/rss.xml"),
    ("Guardian Business", "https://www.theguardian.com/business/rss"),
    ("CNBC Top News", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
]

TECH_FEEDS = [
    ("BBC Tech", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/technology/rss.xml"),
    ("Guardian Tech", "https://www.theguardian.com/technology/rss"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
]

WEIRD_FEEDS = [
    ("Reuters Oddly Enough", "https://feeds.reuters.com/reuters/oddlyEnoughNews"),
    ("Guardian Science", "https://www.theguardian.com/science/rss"),
    ("BBC Science", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/sci/tech/rss.xml"),
]

# 3 columns; Breaking at top of column 1
LAYOUT = [
    [("Breaking", BREAKING_FEEDS), ("Top", TOP_FEEDS)],
    [("Business", BUSINESS_FEEDS)],
    [("Tech", TECH_FEEDS), ("Weird", WEIRD_FEEDS)],
]

# =====================
# COPY (no visible v2/v3)
# =====================
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
    "A surprise move surprises exactly nobody.",
    "A headline confidently outruns the facts.",
    "A temporary measure enters its permanent era.",
    "The optics are doing most of the work here.",
    "A strategy is announced. Execution sold separately.",
]

NEUTRAL_FALLBACKS = [
    "Developing story.",
    "Details are still emerging.",
    "Authorities are investigating.",
    "Situation remains unclear.",
    "More information expected soon.",
    "Updates may follow.",
    "Reporting continues.",
    "This is still unfolding.",
    "Context is still being gathered.",
    "Key details remain unconfirmed.",
    "A fuller picture is forming.",
    "Early reports are still being verified.",
    "Additional confirmation is pending.",
    "Officials have not released full information.",
    "No clear timeline yet.",
    "More to come as this develops.",
    "Information remains partial at this time.",
    "The facts are still coming in.",
    "This remains under review.",
]

VARIANT_PREFIX = ["For now:", "As of now:", "Currently:", "So far:", "At this point:"]
VARIANT_SUFFIX = ["More soon.", "Updates expected.", "Details pending.", "More as it develops.", "Awaiting confirmation."]

# =====================
# TRAGEDY SAFETY
# =====================
TRAGEDY_KEYWORDS = [
    "dead", "death", "dies", "died", "dying",
    "killed", "kill", "killing", "fatal", "fatally",
    "passed", "passing", "obituary", "funeral", "memorial",
    "grief", "grieving", "mourning",
    "loss", "lost",

    "injured", "injury", "hurt", "hurting", "wounded",
    "pain", "painful", "suffering", "suffered",
    "critical", "critical condition", "hospitalized", "hospitalised",
    "icu", "intensive care", "life-threatening", "life threatening",
    "overdose",

    "shooting", "shooter", "shot", "gunfire",
    "stabbing", "stabbed",
    "assault", "attack", "attacked",
    "murder", "homicide", "manslaughter",
    "rape", "sexual assault",
    "abduction", "kidnap", "kidnapped", "hostage",
    "domestic violence", "abuse",

    "suicide", "self-harm", "self harm",

    "fire", "wildfire", "blaze", "burning",
    "explosion", "exploded", "blast",
    "bomb", "bombing",
    "crash", "collision", "wreck", "pileup",
    "earthquake", "quake", "aftershock",
    "flood", "flooding",
    "storm", "hurricane", "tornado", "cyclone",
    "landslide", "mudslide",

    "war", "combat", "fighting",
    "airstrike", "strike", "missile", "shelling",
    "invasion", "siege",
    "terror", "terrorist", "terrorism",

    "sad", "sorrow", "heartbreaking", "tragic",
    "tragedy", "devastating", "devastation",
    "trauma", "traumatic",

    "victim", "victims",
    "casualty", "casualties",
    "missing", "disappeared",
    "search and rescue", "rescue",
    "presumed dead",
]

TRAGEDY_PHRASES = [
    "in critical condition",
    "pronounced dead",
    "died at the scene",
    "lost their life",
    "lost his life",
    "lost her life",
    "killed in",
    "shot and killed",
    "shot dead",
    "found dead",
    "taken to hospital",
    "taken to the hospital",
    "mass shooting",
    "mass casualty",
    "victims identified",
    "community mourns",
]

# =====================
# SIDE-EYE METER + AGES POORLY RULES
# =====================
SIDE_EYE_TRIGGERS = [
    "officials", "reportedly", "sources", "claims", "denies", "denied",
    "investigation", "probe", "review", "inquiry",
    "leak", "leaked",
    "report", "reports",
    "talks", "negotiations",
    "plan", "strategy",
    "announced", "announcement",
    "timeline",
    "deal",
    "crisis",
    "warning", "warns",
    "sanctions",
    "election",
    "court", "lawsuit", "judge",
    "inflation", "recession", "rates", "central bank", "fed",
]

AGES_POORLY_TRIGGERS = [
    # things that often flip quickly (no tragedy, just volatility)
    "will", "could", "may", "might",
    "forecast", "predict", "prediction",
    "expected", "expects",
    "plan", "pledge", "promise",
    "deal", "talks",
    "nominee", "pick",
    "ruling", "court",
    "rates", "inflation",
    "election", "poll",
    "ceasefire",
    "launch",
]

# =====================
# HELPERS
# =====================
def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()

def is_tragic_title(title):
    t = (title or "").lower()
    t = " ".join(t.split())
    for p in TRAGEDY_PHRASES:
        if p in t:
            return True
    for k in TRAGEDY_KEYWORDS:
        if k in t:
            return True
    return False

def side_eye_score(title):
    """
    Returns 0..5 (higher = more skeptical).
    Conservative, keyword-based, no sentiment model.
    """
    t = (title or "").lower()
    hits = 0
    for w in SIDE_EYE_TRIGGERS:
        if w in t:
            hits += 1
    # Map hits to 0..5
    if hits <= 0:
        return 1
    if hits == 1:
        return 2
    if hits == 2:
        return 3
    if hits == 3:
        return 4
    return 5

def eligible_for_ages_poorly(section_name, title):
    """
    Choose from non-tragic Top/Business (and sometimes Breaking if you want),
    but we will keep it conservative: Top + Business only.
    """
    if section_name not in ["Top", "Business"]:
        return False
    if is_tragic_title(title):
        return False
    t = (title or "").lower()
    # must contain at least one volatility trigger
    return any(w in t for w in AGES_POORLY_TRIGGERS)

def parse_feed(source, url):
    items = []
    feed = feedparser.parse(url)
    for e in getattr(feed, "entries", [])[:60]:
        title = clean(getattr(e, "title", ""))
        link = getattr(e, "link", "")
        if title and link:
            items.append({"title": title[:180], "url": link, "source": source})
    return items

def load_json_file(path, default_value):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_value

def save_json_file(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def unique_text_from_pool(pool, used_set, fallback_base):
    while pool:
        candidate = pool.pop()
        if candidate not in used_set:
            used_set.add(candidate)
            return candidate

    for _ in range(300):
        candidate = clean(random.choice(VARIANT_PREFIX) + " " + fallback_base + " " + random.choice(VARIANT_SUFFIX))
        if candidate not in used_set:
            used_set.add(candidate)
            return candidate

    if fallback_base not in used_set:
        used_set.add(fallback_base)
        return fallback_base

    candidate = fallback_base + " "
    used_set.add(candidate)
    return candidate

def pick_neutral_unique(used_sublines, i):
    base = NEUTRAL_FALLBACKS[i % len(NEUTRAL_FALLBACKS)]
    return unique_text_from_pool([], used_sublines, base)

def pick_snark_unique(snark_pool, used_sublines):
    fallback = random.choice(NEUTRAL_FALLBACKS)
    return unique_text_from_pool(snark_pool, used_sublines, fallback)

def ymd_from_utc_iso(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None

def build_week_in_hindsight(history):
    """
    Build dry, factual-ish lines from last 7 days of saved snapshots.
    We avoid claiming events happened; we summarize patterns in the headlines.
    """
    # Flatten titles from last 7 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    titles = []
    for day in history:
        day_utc = day.get("generated_utc", "")
        try:
            dt = datetime.fromisoformat(day_utc.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            continue
        if dt < cutoff:
            continue
        for t in day.get("titles", []):
            titles.append((t or "").lower())

    if not titles:
        return [
            "Not enough history yet. Check back after a few updates.",
        ]

    def count_contains(needle):
        n = needle.lower()
        c = 0
        for t in titles:
            if n in t:
                c += 1
        return c

    developing = count_contains("develop")
    investigate = count_contains("investigat") + count_contains("probe") + count_contains("review")
    talks = count_contains("talk") + count_contains("deal") + count_contains("negotiat")
    warn = count_contains("warn")
    plan = count_contains("plan") + count_contains("strategy")

    lines = []
    # Only include lines that have non-zero counts
    if developing > 0:
        lines.append("Developing stayed popular: " + str(developing) + " headline(s) used it (or close variants).")
    if investigate > 0:
        lines.append("Investigations were plentiful: about " + str(investigate) + " headline(s) referenced probes/reviews.")
    if talks > 0:
        lines.append("Talks and deals appeared often: about " + str(talks) + " headline(s).")
    if warn > 0:
        lines.append("Warnings were issued: about " + str(warn) + " headline(s).")
    if plan > 0:
        lines.append("Plans and strategies were announced: about " + str(plan) + " headline(s).")

    if not lines:
        lines = ["This week was oddly low on recurring buzzwords."]

    # Keep it short and readable
    return lines[:5]

# =====================
# MAIN
# =====================
def main():
    prev = load_json_file("headlines.json", None)
    now = datetime.now(timezone.utc)

    # Breaking refreshes every run. Others refresh every 3 hours (UTC boundary).
    three_hour_boundary = (now.hour % 3 == 0)
    reuse_sections = []
    if not three_hour_boundary:
        reuse_sections = ["Top", "Business", "Tech", "Weird"]

    used_urls = set()
    used_sublines = set()

    # Seed used sets from reused sections so Breaking does not duplicate
    if prev and reuse_sections:
        for col in prev.get("columns", []):
            for sec in col.get("sections", []):
                if sec.get("name") in reuse_sections:
                    for it in sec.get("items", []):
                        u = (it.get("url") or "").strip()
                        s = (it.get("snark") or "").strip()
                        if u:
                            used_urls.add(u)
                        if s:
                            used_sublines.add(s)

    snark_pool = [s for s in SNARK if s not in used_sublines]
    random.shuffle(snark_pool)

    columns = []
    # Collect candidates for the daily "ages poorly" pick
    ages_poorly_candidates = []
    today_key = now.strftime("%Y-%m-%d")

    for col in LAYOUT:
        col_out = {"sections": []}

        for section_name, feeds in col:
            refresh = (section_name == "Breaking") or three_hour_boundary

            # Reuse section if not refreshing
            if (not refresh) and prev:
                reused = None
                for pcol in prev.get("columns", []):
                    for psec in pcol.get("sections", []):
                        if psec.get("name") == section_name:
                            reused = psec
                            break
                    if reused:
                        break
                if reused:
                    # While reusing, still track potential candidates for "ages poorly"
                    for it in reused.get("items", []):
                        if eligible_for_ages_poorly(section_name, it.get("title", "")):
                            ages_poorly_candidates.append((section_name, it.get("url", "")))
                    col_out["sections"].append(reused)
                    continue

            # Build fresh section
            raw = []
            for src, url in feeds:
                raw.extend(parse_feed(src, url))

            # De-dup within section by URL
            seen_local = set()
            raw2 = []
            for it in raw:
                if it["url"] in seen_local:
                    continue
                seen_local.add(it["url"])
                raw2.append(it)

            section_items = []
            per_source = {}

            for i, it in enumerate(raw2):
                if it["url"] in used_urls:
                    continue

                src = it["source"]
                per_source[src] = per_source.get(src, 0)
                if per_source[src] >= MAX_PER_SOURCE_PER_SECTION:
                    continue

                is_first_item = (len(section_items) == 0)
                badge = "BREAK" if (section_name == "Breaking" and is_first_item) else ""
                feature = bool(section_name == "Breaking" and is_first_item)

                tragic = is_tragic_title(it["title"])
                if tragic:
                    sub = pick_neutral_unique(used_sublines, i)
                else:
                    sub = pick_snark_unique(snark_pool, used_sublines)

                meter = side_eye_score(it["title"])

                item_out = {
                    "title": it["title"],
                    "url": it["url"],
                    "source": it["source"],
                    "badge": badge,
                    "feature": feature,
                    "snark": sub,
                    "meter": meter,              # 1..5
                    "ages_poorly": False,         # set later
                    "tragic": tragic,             # for UI decisions if desired
                }

                used_urls.add(it["url"])
                per_source[src] += 1
                section_items.append(item_out)

                # Candidate pool for daily "ages poorly"
                if eligible_for_ages_poorly(section_name, it["title"]):
                    ages_poorly_candidates.append((section_name, it["url"]))

                if len(section_items) >= MAX_ITEMS_PER_SECTION:
                    break

            col_out["sections"].append({"name": section_name, "items": section_items})

        columns.append(col_out)

    # Pick ONE "ages poorly" headline per day (stable-ish)
    # We do this by hashing the day into the candidate list index.
    ages_poorly_url = ""
    if ages_poorly_candidates:
        # deterministic selection based on date so it does not jump each run
        idx = sum(ord(c) for c in today_key) % len(ages_poorly_candidates)
        ages_poorly_url = ages_poorly_candidates[idx][1]

    if ages_poorly_url:
        for col in columns:
            for sec in col.get("sections", []):
                for it in sec.get("items", []):
                    if it.get("url") == ages_poorly_url:
                        it["ages_poorly"] = True

    # Build/update history.json to support "Week in Hindsight"
    history = load_json_file(HISTORY_FILE, [])
    # Add snapshot for today (one per day)
    existing_days = set()
    for h in history:
        k = ymd_from_utc_iso(h.get("generated_utc", ""))
        if k:
            existing_days.add(k)

    if today_key not in existing_days:
        titles_today = []
        for col in columns:
            for sec in col.get("sections", []):
                for it in sec.get("items", []):
                    titles_today.append(it.get("title", ""))

        history.append({
            "generated_utc": now.isoformat(),
            "titles": titles_today[:200],  # cap
        })

    # Trim history to last N days
    # Keep entries with valid ISO times, sort by generated_utc
    def sort_key(x):
        return x.get("generated_utc", "")
    history = sorted(history, key=sort_key)[-HISTORY_MAX_DAYS:]
    save_json_file(HISTORY_FILE, history)

    week_lines = build_week_in_hindsight(history)

    out = {
        "site": {
            "name": "THE DAILY SIDE-EYE",
            "tagline": "Headlines with a raised eyebrow.",
        },
        "generated_utc": now.isoformat(),
        "columns": columns,
        "features": {
            "side_eye_meter": True,
            "ages_poorly": True,
            "week_in_hindsight": True,
        },
        "week_in_hindsight": week_lines,
        "refresh": {
            "breaking": "hourly",
            "others": "every 3 hours (UTC boundary)",
            "three_hour_boundary": three_hour_boundary,
            "max_per_source_per_section": MAX_PER_SOURCE_PER_SECTION,
        },
    }

    save_json_file("headlines.json", out)

if __name__ == "__main__":
    main()