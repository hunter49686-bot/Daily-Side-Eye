#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import random
import hashlib
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

import feedparser

# -----------------------------
# CONFIG
# -----------------------------

SITE_NAME = "THE DAILY SIDE-EYE"
DEFAULT_TAGLINE = "Headlines with a raised eyebrow."

OUTPUT_JSON = "headlines.json"

# Run hourly, but only refresh non-breaking every 3 hours
FULL_REFRESH_EVERY_HOURS = 3

# Item counts
BREAKING_MAX_ITEMS = 12
SECTION_MAX_ITEMS = 14  # per section (non-breaking)

# Deduping / filtering
MAX_AGE_HOURS = 48  # ignore items older than this (best effort; RSS dates are inconsistent)

USER_AGENT = "Daily-Side-Eye/1.0 (+https://github.com/)"

# Expanded RSS sources (mix so it doesn't look like all BBC)
# Note: Some publishers occasionally block RSS fetches from GitHub Actions.
FEEDS: Dict[str, List[Tuple[str, str]]] = {
    "Breaking": [
        ("BBC Front Page", "https://feeds.bbci.co.uk/news/rss.xml"),
        ("CNN Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
        ("The Guardian US", "https://www.theguardian.com/world/usa/rss"),
        ("NBC Top Stories", "http://feeds.nbcnews.com/feeds/topstories"),
        ("ABC Top Stories", "https://feeds.abcnews.com/abcnews/topstories"),
        ("LA Times - Nation", "http://www.latimes.com/nation/rss2.0.xml"),
    ],
    "Business": [
        ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
        ("CNN Money", "http://rss.cnn.com/rss/money_latest.rss"),
        ("NBC Business", "http://feeds.nbcnews.com/feeds/business"),
        ("ABC Business", "https://feeds.abcnews.com/abcnews/businessheadlines"),
        # Washington Post feeds sometimes return 403; keep as optional variety
        ("Washington Post - Business", "https://feeds.washingtonpost.com/rss/business"),
    ],
    "World / Politics": [
        ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("BBC US & Canada", "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"),
        ("The Guardian World", "https://www.theguardian.com/world/rss"),
        ("NBC World", "http://feeds.nbcnews.com/feeds/worldnews"),
        ("ABC US Headlines", "https://feeds.abcnews.com/abcnews/usheadlines"),
        ("LA Times - World", "http://www.latimes.com/world/rss2.0.xml"),
        ("Washington Post - National", "https://feeds.washingtonpost.com/rss/national"),
    ],
    "Tech / Science": [
        ("BBC Tech", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
        ("Ars Technica", "http://feeds.arstechnica.com/arstechnica/index/"),
        ("TechCrunch", "http://feeds.feedburner.com/TechCrunch/"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Wired", "https://www.wired.com/feed/rss"),
        ("NASA Breaking News", "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
    ],
}

# Snark: larger pool + ensure no duplicates on a page.
SNARK_POOL = [
    "This will surely be handled with nuance.",
    "A statement was issued. Substance not included.",
    "Developing story. Developing patience.",
    "Everyone is monitoring the situation. Vigorously.",
    "A plan exists. The details are on a separate planet.",
    "Officials promise transparency, then immediately dim the lights.",
    "Experts weigh in; nobody gains weight from it.",
    "A breakthrough—followed by a breakdown.",
    "A bold move, executed in pencil.",
    "Sources say. Sources always say.",
    "The timeline is fluid. Like a spilled drink.",
    "A 'common sense' solution sparks uncommon disagreement.",
    "The numbers were cited. Interpretation may vary.",
    "Calm statements follow. Loud consequences remain.",
    "Now featuring: consequences.",
    "Updates may follow. So may regret.",
    "A compromise is proposed. Someone will hate it.",
    "A quick fix becomes the long-term architecture.",
    "They've considered all options. Except the obvious one.",
    "This is fine. (It is not fine.)",
    "A promise was made. A reminder will be needed.",
    "Nothing to see here—please stop looking.",
    "The plot thickens. The facts thin out.",
    "Expect clarity shortly. Bring snacks.",
    "A minor detail becomes the main event.",
    "A committee will decide, eventually.",
    "A victory lap, taken before the race.",
    "A measured response, using a broken ruler.",
    "An investigation begins. Answers do not.",
    "Confidence was expressed. Evidence was not.",
    "A big announcement, with a small footnote doing cardio.",
    "This will age… interestingly.",
    "More soon, they assure us. They always do.",
    "Proceeding exactly as predicted—badly.",
    "Another day, another 'unprecedented' thing.",
    "Nothing says stability like emergency meetings.",
    "The situation is dynamic. Like a runaway shopping cart.",
    "A 'final' decision enters its sequel era.",
    "A headline that begs for an edit button.",
    "The bar was low. They brought a shovel.",
    "Expect pushback. Expect spin.",
    "Everyone agrees. On nothing.",
    "A solution appears, then immediately asks for a manager.",
    "A 'temporary' measure settles in permanently.",
    "A confident forecast meets chaotic reality.",
    "If this was the plan, yikes.",
    "A minor tweak triggers major drama.",
    "We'll circle back. Forever.",
    "File under: avoidable.",
    "A straight answer takes a scenic route.",
    "This is either progress or performance art.",
    "They said 'soon.' They meant 'sometime.'",
    "The optics are doing most of the work.",
    "A bold claim enters witness protection.",
    "New details emerge. Old questions remain.",
    "A reminder that 'simple' is a marketing term.",
    "It's complicated, but so is the excuse.",
    "A delay, with extra delay.",
    "Confidence is high. Accuracy is TBD.",
    "A decision was made. Accountability was not.",
    "Everyone is shocked. Again.",
    "The headline writes checks the facts can't cash.",
    "A reset button is requested.",
    "This is why we can’t have nice things.",
    "Now with 20% more uncertainty.",
    "A quick briefing. A long aftermath.",
    "The truth is out there. Not here.",
    "An 'update' that raises more questions than it answers.",
    "The consequences are loading…",
    "A new chapter in an old mess.",
    "A calm exterior, frantic interior.",
    "Unclear. Remains unclear. Probably will stay unclear.",
    "A 'strategy' is announced. Execution sold separately.",
    "The explanation is technically words.",
    "A modest proposal, with immodest confidence.",
]

# -----------------------------
# UTILITIES
# -----------------------------

def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()

def parse_dt(struct_time_obj) -> Optional[dt.datetime]:
    if not struct_time_obj:
        return None
    try:
        return dt.datetime.fromtimestamp(time.mktime(struct_time_obj), tz=dt.timezone.utc)
    except Exception:
        return None

def stable_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def pick_unique_snark(used: set) -> str:
    # Randomly pick from pool ensuring uniqueness across the page.
    # If exhausted (unlikely), fall back to a hashed variant.
    for _ in range(50):
        s = random.choice(SNARK_POOL)
        if s not in used:
            used.add(s)
            return s
    # fallback (still unique)
    s = f"Updates pending. ({stable_hash(str(time.time()))})"
    used.add(s)
    return s

def safe_get_title(entry: Any) -> str:
    t = getattr(entry, "title", "") or ""
    return " ".join(t.split()).strip()

def safe_get_link(entry: Any) -> str:
    return getattr(entry, "link", "") or ""

def entry_published_utc(entry: Any) -> Optional[dt.datetime]:
    # Try published then updated
    d = parse_dt(getattr(entry, "published_parsed", None))
    if d:
        return d
    return parse_dt(getattr(entry, "updated_parsed", None))

def is_too_old(published: Optional[dt.datetime]) -> bool:
    if not published:
        return False  # can't tell, keep
    age = dt.datetime.now(dt.timezone.utc) - published
    return age > dt.timedelta(hours=MAX_AGE_HOURS)

def load_existing(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def should_full_refresh(existing: Optional[Dict[str, Any]]) -> bool:
    """
    Refresh non-breaking sections only every FULL_REFRESH_EVERY_HOURS.
    We store 'last_full_refresh_utc' in the JSON to control this.
    """
    now = dt.datetime.now(dt.timezone.utc)

    if not existing:
        return True

    meta = existing.get("_meta", {})
    last = meta.get("last_full_refresh_utc")
    if not last:
        return True

    try:
        last_dt = dt.datetime.fromisoformat(last.replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return True

    return (now - last_dt) >= dt.timedelta(hours=FULL_REFRESH_EVERY_HOURS)

# -----------------------------
# FETCH / BUILD
# -----------------------------

def fetch_feed_items(feed_name: str, url: str, max_items: int) -> List[Dict[str, Any]]:
    parsed = feedparser.parse(url, request_headers={"User-Agent": USER_AGENT})
    items: List[Dict[str, Any]] = []
    if getattr(parsed, "bozo", False):
        # bozo indicates parse error; still might have entries, so don't abort
        pass

    for e in getattr(parsed, "entries", [])[: max_items * 3]:
        title = safe_get_title(e)
        link = safe_get_link(e)
        if not title or not link:
            continue

        published = entry_published_utc(e)
        if is_too_old(published):
            continue

        items.append(
            {
                "title": title,
                "url": link,
                "source": feed_name,
                "published_utc": published.isoformat() if published else None,
            }
        )

        if len(items) >= max_items:
            break

    return items

def build_section(section_name: str, max_items: int, snark_used: set) -> Dict[str, Any]:
    feed_list = FEEDS.get(section_name, [])
    all_items: List[Dict[str, Any]] = []

    # Pull a few from each feed for variety
    per_feed_cap = max(2, max_items // max(1, len(feed_list)))
    per_feed_cap = min(per_feed_cap, 6)

    for (feed_name, url) in feed_list:
        try:
            got = fetch_feed_items(feed_name, url, per_feed_cap)
            all_items.extend(got)
        except Exception:
            continue

    # Deduplicate by URL, then shuffle to avoid one source dominating
    seen_urls = set()
    deduped: List[Dict[str, Any]] = []
    random.shuffle(all_items)
    for it in all_items:
        u = it["url"]
        if u in seen_urls:
            continue
        seen_urls.add(u)
        deduped.append(it)
        if len(deduped) >= max_items:
            break

    # Mark first item as "feature" if present
    final_items: List[Dict[str, Any]] = []
    for idx, it in enumerate(deduped):
        badge = ""
        feature = False
        if section_name == "Breaking" and idx == 0:
            badge = "BREAK"
            feature = True

        snark = pick_unique_snark(snark_used)

        final_items.append(
            {
                "title": it["title"],
                "url": it["url"],
                "source": it["source"],
                "badge": badge,
                "feature": feature,
                "snark": snark,
            }
        )

    return {"name": section_name, "items": final_items}

def build_payload(existing: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    snark_used = set()

    full_refresh = should_full_refresh(existing)

    # Always rebuild Breaking hourly
    breaking_section = build_section("Breaking", BREAKING_MAX_ITEMS, snark_used)

    # For other sections:
    # - If full refresh, rebuild them
    # - If not, reuse from existing to keep them stable between 3-hour refreshes
    other_sections: List[Dict[str, Any]] = []
    other_names = [k for k in FEEDS.keys() if k != "Breaking"]

    existing_sections_map: Dict[str, Dict[str, Any]] = {}
    if existing:
        try:
            cols = existing.get("columns", [])
            for col in cols:
                for sec in col.get("sections", []):
                    existing_sections_map[sec.get("name", "")] = sec
        except Exception:
            pass

    for name in other_names:
        if full_refresh:
            other_sections.append(build_section(name, SECTION_MAX_ITEMS, snark_used))
        else:
            reused = existing_sections_map.get(name)
            if reused and isinstance(reused, dict):
                # Still enforce unique snark on THIS page:
                # If reused snark collides with Breaking snark, rewrite snark only.
                fixed_items = []
                for it in reused.get("items", []):
                    it2 = dict(it)
                    s = (it2.get("snark") or "").strip()
                    if (not s) or (s in snark_used):
                        it2["snark"] = pick_unique_snark(snark_used)
                    else:
                        snark_used.add(s)
                    fixed_items.append(it2)
                other_sections.append({"name": name, "items": fixed_items})
            else:
                other_sections.append(build_section(name, SECTION_MAX_ITEMS, snark_used))

    # Layout: 3 sections total requested earlier? If you want exactly 3 sections:
    # Breaking + 2 others. Keep the first two other sections.
    # If you want more sections, delete the next line.
    other_sections = other_sections[:2]

    # Columns: 3 columns total with Breaking at top of column 1
    col1 = {"sections": [breaking_section]}
    col2 = {"sections": [other_sections[0]]} if len(other_sections) > 0 else {"sections": []}
    col3 = {"sections": [other_sections[1]]} if len(other_sections) > 1 else {"sections": []}

    now_iso = utc_now_iso()

    payload: Dict[str, Any] = {
        "site": {"name": SITE_NAME, "tagline": DEFAULT_TAGLINE},
        "generated_utc": now_iso,
        "columns": [col1, col2, col3],
        "_meta": {
            "full_refresh_every_hours": FULL_REFRESH_EVERY_HOURS,
            "last_full_refresh_utc": now_iso if full_refresh else (existing.get("_meta", {}).get("last_full_refresh_utc") if existing else now_iso),
        },
    }

    return payload

def main() -> None:
    random.seed()  # randomness is fine for variety

    existing = load_existing(OUTPUT_JSON)
    payload = build_payload(existing)
    write_json(OUTPUT_JSON, payload)

    print(f"Wrote {OUTPUT_JSON} @ {payload.get('generated_utc')} (UTC)")

if __name__ == "__main__":
    main()