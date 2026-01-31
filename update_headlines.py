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
# RSS FEEDS (expanded)
# =====================
BREAKING_FEEDS = [
    ("BBC Front Page", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/front_page/rss.xml"),
    ("BBC World", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/world/rss.xml"),
    ("CNN Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
    ("NYT HomePage", "http://feeds.nytimes.com/nyt/rss/HomePage"),
    ("The Guardian World", "https://www.theguardian.com/world/rss"),
]

TOP_FEEDS = [
    ("BBC Front Page", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/front_page/rss.xml"),
    ("BBC World", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/world/rss.xml"),
    ("CNN Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
    ("NYT HomePage", "http://feeds.nytimes.com/nyt/rss/HomePage"),
    ("The Guardian UK", "https://www.theguardian.com/uk/rss"),
]

BUSINESS_FEEDS = [
    ("BBC Business", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/business/rss.xml"),
    ("The Guardian Business", "https://www.theguardian.com/business/rss"),
]

MISC_FEEDS = [
    ("BBC Tech", "http://newsrss.bbc.co.uk/rss/newsonline_uk_edition/technology/rss.xml"),
    ("The Guardian Tech", "https://www.theguardian.com/technology/rss"),
    ("The Guardian Science", "https://www.theguardian.com/science/rss"),
]

# 3 columns; Breaking at top of column 1
LAYOUT = [
    [("Breaking", BREAKING_FEEDS), ("Top", TOP_FEEDS)],
    [("Business", BUSINESS_FEEDS)],
    [("World / Tech / Weird", MISC_FEEDS)],
]


# =====================
# COPY (no visible v2/v3)
# =====================
SNARK = [
    "A confident plan has been announced. Reality is pending.",
    "Officials say it's under control. So that's something.",
    "A decision was made. Consequences scheduled for later.",
    "Experts disagree, loudly and on schedule.",
    "The plan is simple. The details are complicated.",
    "Numbers were cited. Interpretation may vary.",
    "This will surely be handled with nuance.",
    "A big announcement, with a small footnote doing cardio.",
    "A statement was issued. Substance not included.",
    "A compromise is proposed. Someone will hate it.",
    "The situation remains fluid. Like Jell-O.",
    "A timeline was provided. Nobody believes it.",
    "A bold prediction, fresh out of context.",
    "Everyone is calm. On paper.",
    "An investigation begins. Again.",
    "A quick fix becomes the long-term architecture.",
    "A review is underway. Translation: not today.",
    "A win is declared. The scoreboard is unavailable.",
    "The fine print is doing most of the work here.",
    "Expectations were managed. Results were not.",
    "A surprise move surprises exactly nobody.",
    "A headline confidently outruns the facts.",
]

NEUTRAL = [
    "Developing story.",
    "Details are still emerging.",
    "Authorities are investigating.",
    "Situation remains unclear.",
    "More information expected soon.",
    "Reporting continues.",
    "Updates may follow.",
    "Context is still being gathered.",
    "Key details remain unconfirmed.",
    "A fuller picture is forming.",
    "Additional confirmation is pending.",
    "No clear timeline yet.",
]

# Used only when we need *uniqueness* but pools are exhausted (no visible numbering)
VARIANT_PREFIX = ["For now:", "As of now:", "Currently:", "So far:", "At this point:"]
VARIANT_SUFFIX = ["More soon.", "Updates expected.", "Details pending.", "More as it develops.", "Awaiting confirmation."]

TRAGEDY_KEYWORDS = [
    "dead", "dies", "killed", "death", "shooting", "shooter",
    "attack", "war", "bomb", "explosion", "terror",
    "crash", "collision", "earthquake", "wildfire", "flood",
    "victim", "victims", "injured", "wounded",
]


# =====================
# HELPERS
# =====================
def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_tragic(title: str) -> bool:
    t = (title or "").lower()
    return any(k in t for k in TRAGEDY_KEYWORDS)


def parse_feed(source: str, url: str):
    items = []
    feed = feedparser.parse(url)
    for e in feed.entries[:60]:
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


def unique_from_pool(pool, used, fallback_base):
    """
    Pick an unused line from pool; otherwise generate a unique variant without "(v2)".
    """
    # try pool first
    random.shuffle(pool)
    for s in pool:
        if s not in used:
            used.add(s)
            return s

    # generate unique variants
    for _ in range(400):
        candidate = f"{random.choice(VARIANT_PREFIX)} {fallback_base} {random.choice(VARIANT_SUFFIX)}"
        candidate = clean(candidate)
        if candidate not in used:
            used.add(candidate)
            return candidate

    # last-resort tiny tweak
    candidate = fallback_base + " "
    if candidate not in used:
        used.add(candidate)
        return candidate

    used.add(fallback_base)
    return fallback_base


def choose_neutral_unique(used):
    base = random.choice(NEUTRAL)
    return unique_from_pool([], used, base)


# =====================
# MAIN
# =====================
def main():
    prev = load_previous()
    now = datetime.now(timezone.utc)

    # Refresh non-breaking sections every 3 hours (UTC). Breaking always refreshes.
    three_hour_boundary = (now.hour % 3 == 0)

    # Between 3-hour boundaries, reuse these sections unchanged
    reuse_sections = []
    if not three_hour_boundary:
        reuse_sections = ["Top", "Business", "World / Tech / Weird"]

    used_urls = set()
    used_sublines = set()

    # Seed used sets from reused sections so Breaking won't duplicate
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

    # Make a snark pool that excludes already-used sublines (from reused sections)
    snark_pool = [s for s in SNARK if s not in used_sublines]

    columns = []

    for col in LAYOUT:
        col_out = {"sections": []}

        for name, feeds in col:
            refresh = name.startswith("Breaking") or three_hour_boundary

            # Reuse section if not refreshing
            if (not refresh) and prev:
                reused = None
                for pcol in prev.get("columns", []):
                    for psec in pcol.get("sections", []):
                        if psec.get("name") == name:
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

            # Dedup within section by URL while preserving order
            seen_local = set()
            raw2 = []
            for it in raw:
                if it["url"] in seen_local:
                    continue
                seen_local.add(it["url"])
                raw2.append(it)

            section_items = []
            per_source = {}

            for it in raw2:
                # global dedupe across page
                if it["url"] in used_urls:
                    continue

                # per-source cap in this section
                src = it["source"]
                per_source[src] = per_source.get(src, 0)
                if per_source[src] >= MAX_PER_SOURCE_PER_SECTION:
                    continue

                # determine badge/feature for first Breaking item BEFORE appending
                is_first_item = (len(section_items) == 0)
                badge = "BREAK" if (name.startswith("Breaking") and is_first_item) else ""
                feature = bool(name.startswith("Breaking") and is_first_item)

                # subheadline (unique across whole page)
                tragic = is_tragic(it["title"])
                if tragic:
                    sub = choose_neutral_unique(used_sublines)
                else:
                    fallback = random.choice(NEUTRAL)
                    sub = unique_from_pool(snark_pool, used_sublines, fallback)

                # commit selection
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

            col_out["sections"].append({"name": name, "items": section_items})

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
            "others": "every 3 hours",
            "three_hour_boundary": three_hour_boundary,
            "max_per_source_per_section": MAX_PER_SOURCE_PER_SECTION,
        },
    }

    with open("headlines.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()