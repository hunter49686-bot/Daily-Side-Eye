import json
import random
import re
import socket
import time
from datetime import datetime, timezone, timedelta
import feedparser

# =====================
# HARD NETWORK SAFETY (prevents Actions hangs)
# =====================
HTTP_TIMEOUT_SECONDS = 10
socket.setdefaulttimeout(HTTP_TIMEOUT_SECONDS)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

# =====================
# SECTION RULES
# =====================
BREAKING_MAX = 7
DEVELOPING_MAX = 8
MAX_PER_SOURCE_PER_SECTION = 3

BALANCE_TARGETS = [
    "Fox News",
    "New York Post",
    "Washington Examiner",
    "National Review",
    "RealClearPolitics",
]

# =====================
# FEEDS
# =====================
BREAKING_FEEDS = [
    ("BBC Front Page", "https://feeds.bbci.co.uk/news/rss.xml"),
    ("CNN Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
    ("The Guardian World", "https://www.theguardian.com/world/rss"),
    ("Fox News", "https://feeds.foxnews.com/foxnews/latest"),
    ("New York Post", "https://nypost.com/feed/"),
    ("RealClearPolitics", "https://www.realclearpolitics.com/index.xml"),
]

# We still use "Top-ish" feeds as inputs for Developing, but Top section is removed.
TOP_INPUT_FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("CNN Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
    ("The Guardian UK", "https://www.theguardian.com/uk/rss"),
    ("Fox News", "https://feeds.foxnews.com/foxnews/latest"),
    ("New York Post", "https://nypost.com/feed/"),
    ("RealClearPolitics", "https://www.realclearpolitics.com/index.xml"),
]

BUSINESS_FEEDS = [
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("CNN Business", "http://rss.cnn.com/rss/money_latest.rss"),
    ("NPR Business", "https://feeds.npr.org/1006/rss.xml"),
    ("The Guardian Business", "https://www.theguardian.com/business/rss"),
    ("Washington Examiner", "https://www.washingtonexaminer.com/rss.xml"),
    ("National Review", "https://www.nationalreview.com/feed/"),
]

WORLD_TECH_WEIRD_FEEDS = [
    ("BBC Tech", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("NPR Technology", "https://feeds.npr.org/1019/rss.xml"),
    ("The Guardian Tech", "https://www.theguardian.com/technology/rss"),
    ("National Review", "https://www.nationalreview.com/feed/"),
    ("RealClearPolitics", "https://www.realclearpolitics.com/index.xml"),
]

# Final output layout (Top removed)
LAYOUT = [
    [("Breaking", BREAKING_FEEDS), ("Developing", [])],
    [("Business", BUSINESS_FEEDS)],
    [("World / Tech / Weird", WORLD_TECH_WEIRD_FEEDS)],
]

# =====================
# COPY
# =====================
SNARK = [
    "The optics are doing most of the work here.",
    "This will surely be handled with nuance.",
    "A statement was issued. Substance not included.",
    "A confident plan has been announced. Reality is pending.",
    "A compromise is proposed. Someone will hate it.",
    "Numbers were cited. Interpretation may vary.",
    "Experts disagree, loudly and on schedule.",
    "A decision was made. Consequences scheduled for later.",
    "The fine print is doing most of the work.",
    "Everyone is calm. On paper.",
    "A bold claim meets inconvenient details.",
    "A timeline was provided. Nobody believes it.",
    "The explanation is technically words.",
    "An investigation begins. Again.",
    "A big announcement, with a small footnote doing cardio.",
    "The plan is simple. The details are complicated.",
    "A 'common sense' solution sparks uncommon disagreement.",
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
]

TRAGEDY_KEYWORDS = [
    "dead", "dies", "killed", "death", "shooting", "attack",
    "war", "bomb", "explosion", "terror", "crash",
    "earthquake", "wildfire", "flood", "victim", "injured",
]

# Aggressive ad / promo filters
PROMO_PATTERNS = [
    r"\bbonus code\b",
    r"\bpromo code\b",
    r"\bdiscount\b",
    r"\bcoupon\b",
    r"\bdeal\b",
    r"\bsale\b",
    r"\bsubscribe\b",
    r"\bsponsored\b",
    r"\badvertis",
    r"\bbetmgm\b",
    r"\bfanduel\b",
    r"\bdraftkings\b",
    r"\bsportsbook\b",
    r"\bodds\b",
    r"\bbetting\b",
    r"\bfree bet\b",
    r"\bdeposit match\b",
]
PROMO_RE = re.compile("|".join(PROMO_PATTERNS), re.I)

# =====================
# HELPERS
# =====================
def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def is_tragic(title: str) -> bool:
    t = (title or "").lower()
    return any(k in t for k in TRAGEDY_KEYWORDS)

def is_promo(title: str) -> bool:
    return bool(PROMO_RE.search(title or ""))

def load_previous():
    try:
        with open("headlines.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def unique_line(pool, used_set, fallback):
    pool = list(pool or [])
    random.shuffle(pool)
    for line in pool:
        line = clean(line)
        if line and line not in used_set:
            used_set.add(line)
            return line

    base = clean(fallback) or "Updates may follow."
    pad = ""
    while base + pad in used_set:
        pad += " "
    used_set.add(base + pad)
    return base + pad

def entry_epoch_seconds(entry):
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not t:
        return None
    try:
        return int(time.mktime(t))
    except Exception:
        return None

def parse_feed(source: str, url: str):
    items = []
    try:
        feed = feedparser.parse(url, agent=USER_AGENT)
    except Exception:
        return items

    for e in getattr(feed, "entries", [])[:90]:
        title = clean(getattr(e, "title", ""))
        link = clean(getattr(e, "link", ""))

        if not title or not link:
            continue
        if is_promo(title):
            continue

        epoch = entry_epoch_seconds(e)
        published_utc = None
        if epoch:
            published_utc = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()

        items.append({
            "title": title[:180],
            "url": link,
            "source": source,
            "published_utc": published_utc,
        })
    return items

def dedupe_by_url(items):
    seen = set()
    out = []
    for it in items:
        u = clean(it.get("url", ""))
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out

def norm_title_key(title: str) -> str:
    t = clean(title).lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:160]

def dedupe_by_title(items):
    seen = set()
    out = []
    for it in items:
        k = norm_title_key(it.get("title", ""))
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out

def parse_dt_safe(iso_str: str):
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except Exception:
        return None

def freshness_filter(items, now_utc: datetime, days: int, allow_unknown=False):
    cutoff = now_utc - timedelta(days=days)
    fresh = []
    unknown = []
    for it in items:
        dt = parse_dt_safe(it.get("published_utc"))
        if dt is None:
            unknown.append(it)
            continue
        if dt >= cutoff:
            fresh.append(it)
    return fresh + (unknown if allow_unknown else [])

def importance_score(it, now_utc: datetime):
    # Priority: recency (when known), plus mild boost for balance targets.
    dt = parse_dt_safe(it.get("published_utc"))
    if dt is None:
        rec = 0.0
    else:
        age_hours = max(0.0, (now_utc - dt).total_seconds() / 3600.0)
        rec = max(0.0, 200.0 - age_hours)  # newer => higher, flattens after ~8 days

    src = it.get("source") or ""
    boost = 12.0 if src in BALANCE_TARGETS else 0.0

    # Penalize "evergreen" / listicle vibes lightly
    title = (it.get("title") or "").lower()
    penalty = 0.0
    for w in ["gift", "best ", "top ", "how to", "tips", "guide"]:
        if w in title:
            penalty += 18.0
            break

    return rec + boost - penalty

def pick_section_items_importance(raw_items, used_urls, used_sublines, section_name, now_utc, max_items):
    raw_items = dedupe_by_url(raw_items)
    raw_items = dedupe_by_title(raw_items)

    # Freshness discipline
    if section_name == "Breaking":
        raw_items = freshness_filter(raw_items, now_utc, days=3, allow_unknown=False)
    elif section_name == "Developing":
        raw_items = freshness_filter(raw_items, now_utc, days=4, allow_unknown=False)
    else:
        raw_items = freshness_filter(raw_items, now_utc, days=21, allow_unknown=True)

    # Sort by importance
    raw_items.sort(key=lambda it: importance_score(it, now_utc), reverse=True)

    section_items = []
    per_source = {}

    # Step 1: ensure balance targets if available
    pool_by_source = {}
    for it in raw_items:
        pool_by_source.setdefault(it["source"], []).append(it)

    for target in BALANCE_TARGETS:
        if len(section_items) >= max_items:
            break
        if target not in pool_by_source:
            continue

        picked = None
        for it in pool_by_source[target]:
            if it["url"] in used_urls:
                continue
            if per_source.get(target, 0) >= MAX_PER_SOURCE_PER_SECTION:
                break
            picked = it
            break

        if not picked:
            continue

        tragic = is_tragic(picked["title"])
        sub = unique_line([], used_sublines, random.choice(NEUTRAL)) if tragic else unique_line(SNARK, used_sublines, random.choice(NEUTRAL))

        is_first = (len(section_items) == 0)
        section_items.append({
            "title": picked["title"],
            "url": picked["url"],
            "source": picked["source"],
            "badge": "BREAK" if section_name == "Breaking" and is_first else "",
            "feature": bool(section_name == "Breaking" and is_first),
            "snark": clean(sub),
            "published_utc": picked.get("published_utc"),
        })
        used_urls.add(picked["url"])
        per_source[target] = per_source.get(target, 0) + 1

    # Step 2: fill remaining
    for it in raw_items:
        if len(section_items) >= max_items:
            break
        if it["url"] in used_urls:
            continue

        src = it["source"]
        if per_source.get(src, 0) >= MAX_PER_SOURCE_PER_SECTION:
            continue

        tragic = is_tragic(it["title"])
        sub = unique_line([], used_sublines, random.choice(NEUTRAL)) if tragic else unique_line(SNARK, used_sublines, random.choice(NEUTRAL))

        is_first = (len(section_items) == 0)
        section_items.append({
            "title": it["title"],
            "url": it["url"],
            "source": it["source"],
            "badge": "BREAK" if section_name == "Breaking" and is_first else "",
            "feature": bool(section_name == "Breaking" and is_first),
            "snark": clean(sub),
            "published_utc": it.get("published_utc"),
        })
        used_urls.add(it["url"])
        per_source[src] = per_source.get(src, 0) + 1

    return section_items

def collect_prev_breaking(prev):
    if not prev:
        return []
    for col in prev.get("columns", []):
        for sec in col.get("sections", []):
            if sec.get("name") == "Breaking":
                out = []
                for it in sec.get("items", []):
                    url = clean(it.get("url", ""))
                    title = clean(it.get("title", ""))
                    if not url or not title:
                        continue
                    if is_promo(title):
                        continue
                    out.append({
                        "title": title,
                        "url": url,
                        "source": clean(it.get("source", "")),
                        "published_utc": it.get("published_utc"),  # may exist after update; ok if absent
                        # keep original snark if present; we will not reuse it as subline uniqueness constraint
                        "snark": clean(it.get("snark", "")),
                    })
                return out
    return []

# =====================
# MAIN
# =====================
def main():
    prev = load_previous()
    now = datetime.now(timezone.utc)

    # Reuse slower sections between 3-hour boundaries
    three_hour_boundary = (now.hour % 3 == 0)

    used_urls = set()
    used_sublines = set()

    # Preserve used urls/sublines from reused sections to prevent duplicates
    if prev and not three_hour_boundary:
        for col in prev.get("columns", []):
            for sec in col.get("sections", []):
                if sec.get("name") in ("Business", "World / Tech / Weird"):
                    for it in sec.get("items", []):
                        u = clean(it.get("url", ""))
                        sub = clean(it.get("snark", ""))
                        if u:
                            used_urls.add(u)
                        if sub:
                            used_sublines.add(sub)

    columns = []

    # --- Build Breaking first (always refresh) ---
    breaking_raw = []
    for src, url in BREAKING_FEEDS:
        breaking_raw.extend(parse_feed(src, url))
    random.shuffle(breaking_raw)

    breaking_items = pick_section_items_importance(
        breaking_raw, used_urls, used_sublines, "Breaking", now, BREAKING_MAX
    )

    # --- Build Developing (always refresh) ---
    # Mix:
    # 1) Prior Breaking items that are NOT in current Breaking (still unfolding)
    # 2) Heating-up items not chosen yet (from broad pool)
    prev_breaking = collect_prev_breaking(prev)

    breaking_urls = set(it["url"] for it in breaking_items if it.get("url"))

    carried = []
    for it in prev_breaking:
        if it["url"] in breaking_urls:
            continue
        if it["url"] in used_urls:
            continue
        # carry only a few; keep snark from prior item (still counts as snark staying)
        carried.append({
            "title": it["title"],
            "url": it["url"],
            "source": it.get("source", ""),
            "published_utc": it.get("published_utc"),
        })

    # sort carried by "importance" too (if published_utc exists, it helps; otherwise it will be low)
    carried.sort(key=lambda it: importance_score(it, now), reverse=True)
    carried = carried[: max(0, DEVELOPING_MAX // 2)]  # half budget

    # Heating-up pool
    developing_raw = []
    for src, url in (BREAKING_FEEDS + TOP_INPUT_FEEDS):
        developing_raw.extend(parse_feed(src, url))
    random.shuffle(developing_raw)

    # Add carried first without BREAK badge/feature, with fresh snark assigned (not reusing old subline to avoid stale)
    developing_items = []
    per_source_dev = {}
    for it in carried:
        if len(developing_items) >= DEVELOPING_MAX:
            break
        if it["url"] in used_urls:
            continue
        src = it.get("source", "")
        if per_source_dev.get(src, 0) >= MAX_PER_SOURCE_PER_SECTION:
            continue

        tragic = is_tragic(it["title"])
        sub = unique_line([], used_sublines, random.choice(NEUTRAL)) if tragic else unique_line(SNARK, used_sublines, random.choice(NEUTRAL))

        developing_items.append({
            "title": it["title"],
            "url": it["url"],
            "source": src,
            "badge": "",
            "feature": False,
            "snark": clean(sub),
            "published_utc": it.get("published_utc"),
        })
        used_urls.add(it["url"])
        per_source_dev[src] = per_source_dev.get(src, 0) + 1

    # Fill remaining Developing slots from importance-sorted pool, avoiding breaking + used
    # We temporarily pick with the same selector but with a smaller max and then merge.
    dev_needed = DEVELOPING_MAX - len(developing_items)

    if dev_needed > 0:
        dev_picked = pick_section_items_importance(
            developing_raw, used_urls, used_sublines, "Developing", now, dev_needed
        )
        # Ensure no BREAK styling carries over
        for it in dev_picked:
            it["badge"] = ""
            it["feature"] = False
        developing_items.extend(dev_picked)

    # --- Build Business / World-Tech-Weird (refresh on 3-hr boundary; otherwise reuse) ---
    def reuse_or_build(section_name, feeds, max_items, freshness_days_allow_unknown):
        # Reuse
        if prev and not three_hour_boundary:
            for col in prev.get("columns", []):
                for sec in col.get("sections", []):
                    if sec.get("name") == section_name:
                        return sec.get("items", [])

        raw = []
        for src, url in feeds:
            raw.extend(parse_feed(src, url))
        random.shuffle(raw)

        # Use importance picker; for these sections allow unknown dates (handled inside by section_name)
        items = pick_section_items_importance(
            raw, used_urls, used_sublines, section_name, now, max_items
        )
        # strip BREAK styling if any (shouldn't happen, but defensively)
        for it in items:
            it["badge"] = ""
            it["feature"] = False
        return items

    business_items = reuse_or_build("Business", BUSINESS_FEEDS, 14, True)
    wtw_items = reuse_or_build("World / Tech / Weird", WORLD_TECH_WEIRD_FEEDS, 14, True)

    # --- Assemble columns (Top removed) ---
    columns = [
        {"sections": [
            {"name": "Breaking", "items": breaking_items},
            {"name": "Developing", "items": developing_items},
        ]},
        {"sections": [
            {"name": "Business", "items": business_items},
            {"name": "World / Tech / Weird", "items": wtw_items},
        ]},
        {"sections": [
            # Column 3 is algorithmic on the client side (Missed / Same Story / Week)
            # Keep empty in JSON to avoid duplication.
        ]},
    ]

    out = {
        "site": {
            "name": "THE DAILY SIDE-EYE",
            "tagline": "Headlines with a raised eyebrow.",
        },
        "generated_utc": now.isoformat(),
        "columns": columns,
    }

    with open("headlines.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
