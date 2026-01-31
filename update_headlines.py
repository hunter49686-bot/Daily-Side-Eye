import json
import random
import re
from datetime import datetime, timezone

import feedparser

# =====================
# TUNING
# =====================
MAX_ITEMS_PER_SECTION = 18
MAX_PER_SOURCE_PER_SECTION = 3  # lower = more diversity

# =====================
# RSS FEEDS
# =====================
BREAKING_FEEDS = [
    ("BBC Front Page", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/front_page/rss.xml"),
    ("BBC World", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/world/rss.xml"),
    ("CNN Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
    ("AP Top News", "https://apnews.com/rss"),
]

TOP_FEEDS = [
    ("BBC World", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/world/rss.xml"),
    ("Guardian World", "https://www.theguardian.com/world/rss"),
    ("NYT HomePage", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"),
]

BUSINESS_FEEDS = [
    ("BBC Business", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/business/rss.xml"),
    ("Guardian Business", "https://www.theguardian.com/business/rss"),
    ("CNBC Top News", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
]

TECH_FEEDS = [
    ("BBC Tech", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/technology/rss.xml"),
    ("Guardian Tech", "https://www.theguardian.com/technology/rss"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index/"),
]

WEIRD_FEEDS = [
    ("Reuters Oddly Enough", "https://www.reutersagency.com/feed/?best-sectors=oddly-enough"),
    ("Guardian US", "https://www.theguardian.com/us/rss"),
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
    # death / loss
    "dead", "death", "dies", "died", "dying",
    "killed", "kill", "killing", "fatal", "fatally",
    "passed", "passing", "obituary", "funeral", "memorial",
    "grief", "grieving", "mourning",
    "loss", "lost",

    # injury / harm / medical crisis
    "injured", "injury", "hurt", "hurting", "wounded",
    "pain", "painful", "suffering", "suffered",
    "critical", "critical condition", "hospitalized", "hospitalised",
    "icu", "intensive care", "life-threatening", "life threatening",
    "overdose",

    # violence / crime / abuse
    "shooting", "shooter", "shot", "gunfire",
    "stabbing", "stabbed",
    "assault", "attack", "attacked",
    "murder", "homicide", "manslaughter",
    "rape", "sexual assault",
    "abduction", "kidnap", "kidnapped", "hostage",
    "domestic violence", "abuse",

    # self-harm / suicide
    "suicide", "self-harm", "self harm",

    # disasters / accidents
    "fire", "wildfire", "blaze", "burning",
    "explosion", "exploded", "blast",
    "bomb", "bombing",
    "crash", "collision", "wreck", "pileup",
    "earthquake", "quake", "aftershock",
    "flood", "flooding",
    "storm", "hurricane", "tornado", "cyclone",
    "landslide", "mudslide",

    # war / conflict / terror
    "war", "combat", "fighting",
    "airstrike", "strike", "missile", "shelling",
    "invasion", "siege",
    "terror", "terrorist", "terrorism",

    # emotional / human tragedy
    "sad", "sorrow", "heartbreaking", "tragic",
    "tragedy", "devastating", "devastation",
    "trauma", "traumatic",

    # victims / missing
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

def parse_feed(source, url):
    items = []
    feed = feedparser.parse(url)
    for e in getattr(feed, "entries", [])[:60]:
        title = clean(getattr(e, "title", ""))
        link = getattr(e, "link", "")
        if title and link:
            items.append({"title": title[:180], "url": link, "source": source})
    return items

def load_previous():
    try:
        with open("headlines.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

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

# =====================
# MAIN
# =====================
def main():
    prev = load_previous()
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

                used_urls.add(it["url"])
                per_source[src] += 1

                section_items.append({
                    "title": it["title"],
                    "url": it["url"],
                    "source": it["source"],
                    "badge": badge,
                    "feature": feature,
                    "snark": sub,
                })

                if len(section_items) >= MAX_ITEMS_PER_SECTION:
                    break

            col_out["sections"].append({"name": section_name, "items": section_items})

        columns.append(col_out)

    out = {
        "site": {
            "name": "THE DAILY SIDE-EYE",
            "tagline": "Headlines with a raised eyebrow.",
        },
        "generated_utc": now.isoformat(),
        "columns": columns,
        "refresh": {
            "breaking": "hourly",
            "others": "every 3 hours (UTC boundary)",
            "three_hour_boundary": three_hour_boundary,
            "max_per_source_per_section": MAX_PER_SOURCE_PER_SECTION,
        },
    }

    with open("headlines.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()