import json
import re
import random
from datetime import datetime, timezone

import feedparser

# -------------------------
# FEEDS
# -------------------------
BREAKING_FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
]

TOP_FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
]

BUSINESS_FEEDS = [
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("NPR Business", "https://feeds.npr.org/1006/rss.xml"),
]

WORLD_TECH_WEIRD_FEEDS = [
    ("BBC Tech", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("NPR Technology", "https://feeds.npr.org/1019/rss.xml"),
]

# Exactly 3 columns. Breaking at top of Column 1.
LAYOUT = [
    [("Breaking", BREAKING_FEEDS), ("Top", TOP_FEEDS)],
    [("Business", BUSINESS_FEEDS)],
    [("World / Tech / Weird", WORLD_TECH_WEIRD_FEEDS)],
]

# -------------------------
# SNARK (large, dry, sarcastic)
# -------------------------
SNARK = [
    "Officials say it's under control. So that's something.",
    "A confident plan has been announced. Reality is pending.",
    "Everyone is calm. On paper.",
    "Sources confirm: people have opinions.",
    "This will surely be handled with nuance.",
    "A decision was made. Consequences scheduled for later.",
    "A timeline was provided. Nobody believes it.",
    "A new policy arrives, wearing a trench coat of exceptions.",
    "Experts disagree, loudly and on schedule.",
    "An investigation begins. Again.",
    "A statement was issued. Substance not included.",
    "This is either nothing or everything. Stay tuned.",
    "Leaders urged restraint, then did the opposite.",
    "A 'temporary' measure enters its permanent era.",
    "A bold prediction, fresh out of context.",
    "Officials clarified the confusion with more confusion.",
    "The situation remains fluid. Like Jell-O.",
    "A committee has been formed. Problem solved, basically.",
    "Numbers were cited. Interpretation may vary.",
    "A spokesperson reassured everyone with vowels and verbs.",
    "A compromise is proposed. Someone will hate it.",
    "A surprise move surprises exactly nobody.",
    "The plan is simple. The details are complicated.",
    "An 'unprecedented' event, right on schedule.",
    "A leak appears. Accountability does not.",
    "A 'hard line' is drawn in pencil.",
    "Expectations were managed. Results were not.",
    "A win is declared. The scoreboard is unavailable.",
    "A debate erupts over what words mean.",
    "A headline confidently outruns the facts.",
    "The fine print is doing most of the work here.",
    "A promise is made. The follow-through is optional.",
    "A familiar problem returns for an encore performance.",
    "A big announcement, with a small footnote doing cardio.",
    "A reform effort begins by renaming things.",
    "A decisive moment, sponsored by ambiguity.",
    "The issue is complex. The takes are not.",
    "A new strategy arrives: hope.",
    "Another day, another 'exclusive' that isn't.",
    "The market reacted emotionally. As usual.",
    "A breakthrough is claimed. Validation pending.",
    "A 'common sense' solution sparks uncommon disagreement.",
    "A statement walks back the statement.",
    "A plan is unveiled. Implementation sold separately.",
    "Officials 'welcomed' the news. Whatever that means.",
    "A technical glitch causes human drama.",
    "A quick fix becomes the long-term architecture.",
    "Everyone asked questions. Few liked the answers.",
    "A review is underway. Translation: not today.",
    "A new record is set. Whether that's good is unclear.",
    "A timeline slips quietly into the night.",
    "A decision is postponed for maximum efficiency.",
    "A 'transparent' process offers frosted glass.",
    "The report recommends more reports.",
    "A new rule appears. Enforcement TBD.",
    "A 'surprising' twist, telegraphed for weeks.",
    "A simple explanation is bravely ignored.",
    "A plan meets reality. Reality wins.",
    "A spokesperson says the quiet part out loud.",
    "A revised estimate replaces the previous guess.",
    "A confident narrative meets inconvenient data.",
    "The details are scarce, but the certainty is abundant.",
    "A bold pivot, executed in slow motion.",
    "A dispute escalates. Calm statements follow.",
    "The solution is obvious, except for everyone disagreeing.",
]

# -------------------------
# TRAGEDY FILTER (no snark)
# -------------------------
TRAGEDY_KEYWORDS = [
    "killed", "dead", "death", "dies", "shooting", "shooter",
    "murder", "war", "bomb", "explosion", "attack",
    "crash", "collision", "earthquake", "wildfire", "flood",
    "victim", "victims", "injured", "wounded", "terror"
]

NEUTRAL_FALLBACKS = [
    NEUTRAL_FALLBACKS = [
    "Developing story.",
    "Details are still emerging.",
    "Authorities are investigating.",
    "Situation remains unclear.",
    "More information expected soon.",
    "A fuller picture is forming.",
    "Updates may follow.",
    "Reporting continues.",
    "This is still unfolding.",
    "Context is still being gathered.",
    "Key details remain unconfirmed.",
    "Officials have not released full information.",
    "No clear timeline yet.",
    "More to come as this develops.",
    "Early reports are still being verified.",
    "Additional confirmation is pending.",
    "Expect revisions as reporting advances.",
    "Information remains partial at this time.",
    "The facts are still coming in.",
    "This remains under review.",
]
]

# -------------------------
# JSON reuse helpers (so Top/Business/World stay static between 3h refreshes)
# -------------------------
def load_previous_json(path="headlines.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def get_previous_section(prev_data, section_name):
    if not prev_data:
        return None
    try:
        for col in prev_data.get("columns", []):
            for sec in col.get("sections", []):
                if sec.get("name") == section_name:
                    return sec
    except Exception:
        return None
    return None

def collect_existing_sublines(prev_data, section_names_to_reuse):
    """
    Collect already-used subheadline strings (snark or neutral) from
    reused sections so Breaking doesn't duplicate them.
    """
    used = set()
    if not prev_data:
        return used
    for name in section_names_to_reuse:
        sec = get_previous_section(prev_data, name)
        if not sec:
            continue
        for it in sec.get("items", []):
            s = (it.get("snark") or "").strip()
            if s:
                used.add(s)
    return used

# -------------------------
# Core helpers
# -------------------------
def clean_title(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:160]

def is_tragic(title):
    t = (title or "").lower()
    return any(word in t for word in TRAGEDY_KEYWORDS)

def parse_feed(source, url):
    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:25]:
            title = clean_title(getattr(entry, "title", ""))
            link = getattr(entry, "link", "")
            if title and link:
                items.append({"title": title, "url": link, "source": source})
    except Exception:
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

def build_snark_pool(exclude_set):
    pool = [s for s in SNARK if s not in exclude_set]
    random.shuffle(pool)
    return pool

def get_unique_line(pool, used_set, fallback_base):
    """
    Always returns a string not already in used_set.
    - Pops from pool first (no repeats).
    - If exhausted, appends a unique suffix to guarantee uniqueness.
    """
    while pool:
        candidate = pool.pop()
        if candidate not in used_set:
            used_set.add(candidate)
            return candidate

    i = 2
    candidate = fallback_base
    while candidate in used_set:
        candidate = f"{fallback_base} (v{i})"
        i += 1
    used_set.add(candidate)
    return candidate

def neutral_line_unique(i, used_set):
    base = NEUTRAL_FALLBACKS[i % len(NEUTRAL_FALLBACKS)]
    return get_unique_line([], used_set, base)

def build_section(section_name, feeds, badge_first, feature_first, snark_pool, used_sublines):
    combined = []
    for source, url in feeds:
        combined.extend(parse_feed(source, url))

    combined = dedupe(combined)[:12]

    rendered = []
    for i, item in enumerate(combined):
        title = item["title"]
        tragic = is_tragic(title)

        if tragic:
            sub = neutral_line_unique(i, used_sublines)
        else:
            sub = get_unique_line(snark_pool, used_sublines, "Everyone is monitoring the situation.")

        rendered.append({
            "title": title,
            "url": item["url"],
            "source": item["source"],
            "badge": badge_first if i == 0 else "",
            "feature": True if (feature_first and i == 0) else False,
            "snark": sub
        })

    return {"name": section_name, "items": rendered}

# -------------------------
# MAIN
# -------------------------
def main():
    prev = load_previous_json("headlines.json")
    now_utc = datetime.now(timezone.utc)

    # Refresh non-breaking sections every 3 hours (UTC boundary).
    # Breaking refreshes every hour.
    three_hour_boundary = (now_utc.hour % 3 == 0)

    reuse_sections = []
    if not three_hour_boundary:
        reuse_sections = ["Top", "Business", "World / Tech / Weird"]

    used_sublines = collect_existing_sublines(prev, reuse_sections)
    snark_pool = build_snark_pool(used_sublines)

    columns = []
    for col in LAYOUT:
        col_obj = {"sections": []}

        for section_name, feeds in col:
            should_refresh = (section_name == "Breaking") or three_hour_boundary

            if not should_refresh:
                prev_sec = get_previous_section(prev, section_name)
                if prev_sec:
                    col_obj["sections"].append(prev_sec)
                    continue

            if section_name == "Breaking":
                sec = build_section(section_name, feeds, "BREAK", True, snark_pool, used_sublines)
            elif section_name == "Top":
                sec = build_section(section_name, feeds, "TOP", True, snark_pool, used_sublines)
            else:
                sec = build_section(section_name, feeds, "", False, snark_pool, used_sublines)

            col_obj["sections"].append(sec)

        columns.append(col_obj)

    data = {
        "site": {
            "name": "THE DAILY SIDE-EYE",
            "tagline": "Headlines with a raised eyebrow."
        },
        "generated_utc": now_utc.isoformat(),
        "columns": columns,
        "refresh": {
            "breaking": "hourly",
            "others": "every 3 hours",
            "three_hour_boundary": three_hour_boundary
        }
    }

    with open("headlines.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()