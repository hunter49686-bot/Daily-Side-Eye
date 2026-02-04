import json
import re
import hashlib
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import requests

HEADLINES_PATH = "headlines.json"
USER_AGENT = "DailySideEyeBot/1.0 (+https://dailysideeye.com)"
GOOGLE_NEWS_BASE = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def google_news_rss(query: str) -> str:
    return GOOGLE_NEWS_BASE.format(q=quote_plus(query))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


PROMO_RE = re.compile(
    r"\bsponsored\b|\badvertisement\b|\bpromo\b|\bpromotion\b|\bcoupon\b|\bdeal\b|\bdeals\b|"
    r"\bshopping\b|\bsubscribe\b|\bsubscription\b|\bpartner content\b",
    re.IGNORECASE,
)

TRAGIC_RE = re.compile(
    r"\bkilled\b|\bdead\b|\bdeath\b|\bmurder\b|\bshooting\b|\bstabbing\b|\bmassacre\b|"
    r"\bterror\b|\bterrorist\b|\bwar\b|\binvasion\b|\bairstrike\b|\bearthquake\b|\bhurricane\b|"
    r"\btornado\b|\bflood\b|\bcrash\b|\bexplosion\b|\bhostage\b",
    re.IGNORECASE,
)

NOTHINGBURGER_RE = re.compile(
    r"\bbacklash\b|\boutcry\b|\boutrage\b|\bslammed\b|\bclaps back\b|\bgoes viral\b|"
    r"\binternet reacts\b|\bfans react\b|\bresponds\b|\bmeltdown\b|\bcontroversy\b|\bstuns\b|"
    r"\byou won'?t believe\b",
    re.IGNORECASE,
)


def is_promo(title: str) -> bool:
    return bool(PROMO_RE.search(title or ""))


def is_tragic(title: str) -> bool:
    return bool(TRAGIC_RE.search(title or ""))


def is_nothingburger(title: str) -> bool:
    return bool(NOTHINGBURGER_RE.search(title or "")) and not is_tragic(title)


def normalize_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip())


def fetch_feed(url: str, timeout: int = 20):
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return feedparser.parse(r.content)


def items_from_feed(parsed, source_name: str, max_items: int):
    out = []
    for e in parsed.entries[: max_items * 4]:
        title = normalize_title(getattr(e, "title", ""))
        link = getattr(e, "link", None)
        if not title or not link:
            continue
        if is_promo(title):
            continue
        out.append(
            {
                "title": title,
                "url": link,
                "source": source_name,
                "tragic": is_tragic(title),
                "snark": "",
            }
        )
        if len(out) >= max_items:
            break
    return out


def item_key(it) -> tuple:
    return (it.get("title", "").strip().lower(), it.get("url", "").strip())


def dedupe_list(items):
    seen = set()
    out = []
    for it in items:
        key = item_key(it)
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


# SAFE pull_sources: one broken RSS source won't fail the whole run
def pull_sources(sources, take_each):
    combined = []
    for name, url in sources:
        try:
            parsed = fetch_feed(url)
            combined.extend(items_from_feed(parsed, name, max_items=take_each))
        except Exception as e:
            print(f"[warn] source failed: {name} {url} :: {e}")
            continue
    return dedupe_list(combined)


def alternate(left_items, right_items, limit):
    out = []
    i = j = 0
    while len(out) < limit and (i < len(left_items) or j < len(right_items)):
        if i < len(left_items):
            out.append(left_items[i])
            i += 1
            if len(out) >= limit:
                break
        if j < len(right_items):
            out.append(right_items[j])
            j += 1
    return out[:limit]


def global_dedupe_in_priority(section_map, priority):
    seen = set()
    for sec in priority:
        filtered = []
        for it in section_map.get(sec, []):
            key = item_key(it)
            if key in seen:
                continue
            seen.add(key)
            filtered.append(it)
        section_map[sec] = filtered
    return section_map, seen


# ----------------------------
# Snark generation (unique per page)
# ----------------------------
SNARK_TEMPLATES = [
    "Bold strategy. Let’s see if it survives contact with reality.",
    "Everyone is very confident. That’s usually a bad sign.",
    "This has the energy of a meeting that should’ve been an email.",
    "The vibes are loud, the facts are on mute.",
    "A helpful reminder: headlines are not evidence.",
    "If irony had a newsletter, this would be the lead story.",
    "Somebody’s about to discover consequences have a return address.",
    "The plot thickens, mostly with nonsense.",
    "A brave new chapter in ‘we meant well.’",
    "Reality called. It wants its narrative back.",
    "Nothing says ‘serious’ like a sudden rush to explain.",
    "This is either important or excellent performance art.",
    "Somewhere, a spreadsheet is crying.",
    "It’s giving ‘emergency’ but in a very optional way.",
    "High drama, low signal.",
    "We are once again speed-running avoidable confusion.",
    "Truly inspiring levels of self-assurance.",
    "A classic case of ‘sounds right’ vs ‘is right.’",
    "The audacity is doing cardio today.",
    "The headline is confident. The details are shy.",
    "This feels like a subplot that escaped containment.",
    "Nothing to see here except the entire thing.",
    "A modest proposal: maybe verify things.",
    "The timeline is stressed and so are we.",
    "Everyone involved thinks they’re the main character.",
    "This is why the comment section exists (unfortunately).",
    "A masterclass in saying a lot while committing to nothing.",
    "Please hold while reality updates its firmware.",
    "Another day, another ‘unprecedented’ event.",
    "We’re calling it a plan. That’s generous.",
    "The spin cycle is set to ‘maximum.’",
    "This is what happens when certainty outruns competence.",
    "If this is the fix, what was the problem?",
    "Somebody just reinvented a mistake from 2009.",
    "A bold pivot into ‘let’s just try it.’",
    "Being loud is not the same as being right.",
    "This reads like a draft that went live.",
    "Ambitious levels of wishful thinking.",
    "The stakes are unclear but the confidence is astronomical.",
    "We regret to inform you the plot has thickened again.",
    "A quick reminder: correlation isn’t a personality trait.",
    "The headline wants applause; the details want supervision.",
    "This is either a breakthrough or a rerun.",
    "The rationale is missing, but the confidence is not.",
    "We are watching a plan develop in real time. Unfortunately.",
    "The explanation is doing parkour around the point.",
    "This is why people drink decaf—less optimism.",
    "The timeline is creative, in the worst way.",
    "A bold move from the Department of ‘Trust Me Bro.’",
    "Somebody is about to ‘clarify’ for 72 hours straight.",
    "The ‘sources say’ era continues.",
    "This is the kind of certainty that ages poorly.",
    "If this is leadership, where’s the adult supervision?",
    "A lot of words to say ‘we’ll see.’",
    "The strategy appears to be vibes and prayer.",
    "This is what happens when group chats run government.",
    "Consider this your daily reminder to check the fine print.",
    "The confidence-to-competence ratio is alarming.",
    "It’s a bold claim for someone with no citations.",
    "We love a plan that collapses on contact.",
    "Reality remains undefeated.",
    "This could’ve been prevented by reading the room.",
    "Somebody mistook a hunch for a policy.",
    "The optics are doing the heavy lifting.",
    "Another victory for the ‘wait, what?’ community.",
    "It’s giving ‘we’ll workshop it later.’",
    "This is a great way to lose a weekend.",
    "The narrative is sprinting; the facts are strolling.",
    "An exciting new chapter in ‘avoidable.’",
    "The plan is simple: pretend this is fine.",
    "Somebody’s lawyer just sighed.",
    "The PR team is about to earn their keep.",
    "This is the kind of headline that needs a disclaimer.",
    "The follow-up will be spectacular.",
    "We are all trapped in a pilot episode.",
    "This is a situation, not a strategy.",
    "Somebody pressed ‘send’ and immediately regretted it.",
    "The headline is spicy; the details are plain oatmeal.",
    "This is why we can’t have nice institutions.",
    "The vibes are immaculate. The logic is not.",
    "This will age like milk in July.",
    "Somebody is allergic to straightforward answers.",
    "This is a strong argument for naps.",
    "The vibe is ‘we tried nothing.’",
    "This is what happens when you skip step two.",
    "The evidence is missing; the confidence is present.",
    "We’ve entered the ‘walk it back’ portion of the program.",
    "This is a case study in how not to do this.",
    "The headline is doing the most.",
    "They chose violence. Bureaucratic violence.",
    "This is not a headline; it’s a cry for help.",
    "This is a high-stakes game of ‘maybe.’",
    "This is why we read past the headline.",
    "The strategy appears to be ‘hope.’",
    "The details are here to ruin the story.",
    "The spin is impressive, in a concerning way.",
]


def stable_int(s: str) -> int:
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def assign_unique_snark(all_items_in_order):
    used = set()
    n = len(SNARK_TEMPLATES)

    for it in all_items_in_order:
        if it.get("tragic"):
            it["snark"] = ""
            continue

        key = f"{it.get('title','')}|{it.get('source','')}|{it.get('url','')}"
        start = stable_int(key) % n

        chosen = None
        for offset in range(n):
            candidate = SNARK_TEMPLATES[(start + offset) % n]
            if candidate not in used:
                chosen = candidate
                break

        if chosen is None:
            it["snark"] = ""
            continue

        used.add(chosen)
        it["snark"] = chosen


def load_existing(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        return existing
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def stable_sections_hash(sections_obj) -> str:
    blob = json.dumps(sections_obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ----------------------------
# Source pools
# ----------------------------
LEFT_GENERAL = [
    ("Reuters", google_news_rss("site:reuters.com when:2d -inurl:/video -inurl:/graphics")),
    ("AP", google_news_rss("site:apnews.com when:2d")),
]
RIGHT_GENERAL = [
    ("Fox News", google_news_rss("site:foxnews.com when:2d")),
    ("NY Post", google_news_rss("site:nypost.com when:2d")),
]

LEFT_POLITICS = [
    ("Guardian", google_news_rss("site:theguardian.com (politics OR policy OR government) when:3d")),
    ("Reuters", google_news_rss("site:reuters.com (politics OR government OR election OR congress OR parliament) when:3d -inurl:/video")),
]
RIGHT_POLITICS = [
    ("Examiner", google_news_rss("site:washingtonexaminer.com (politics OR policy) when:7d")),
    ("Fox News", google_news_rss("site:foxnews.com (politics OR policy) when:3d")),
]

LEFT_MARKETS = [
    ("Bloomberg", google_news_rss("site:bloomberg.com (markets OR economy OR finance OR stocks) when:3d")),
    ("Reuters", google_news_rss("site:reuters.com (markets OR economy OR finance OR stocks) when:3d -inurl:/video")),
]
RIGHT_MARKETS = [
    ("WSJ", google_news_rss("site:wsj.com (markets OR economy OR finance OR stocks) when:3d")),
    ("Fox Business", google_news_rss("site:foxbusiness.com (markets OR economy OR finance OR stocks) when:3d")),
]

LEFT_TECH = [
    ("The Verge", google_news_rss("site:theverge.com when:3d")),
]
RIGHT_TECH = [
    ("Hacker News", "https://news.ycombinator.com/rss"),
]

LEFT_WEIRD = [
    ("Atlas Obscura", google_news_rss("site:atlasobscura.com when:30d")),
]
RIGHT_WEIRD = [
    ("Reuters OddlyEnough", google_news_rss("site:reuters.com ('oddly enough' OR oddly OR bizarre OR strange OR unusual) when:30d -inurl:/video")),
]

# World RSS (direct)
WORLD_LEFT = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
]
WORLD_RIGHT = [
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
]


def build_breaking_and_developing(prev_sections):
    prev_breaking = prev_sections.get("breaking", []) if isinstance(prev_sections, dict) else []
    prev_breaking_keys = {item_key(it) for it in prev_breaking}

    # Pull a decent pool so we can replace Breaking with "new" items
    left_pool = pull_sources(LEFT_GENERAL, take_each=25)
    right_pool = pull_sources(RIGHT_GENERAL, take_each=25)
    candidates = dedupe_list(alternate(left_pool, right_pool, 50))

    available_keys = {item_key(it) for it in candidates}

    # "Not updated since last update" => last run's Breaking is still present now
    dropped_from_breaking = [it for it in prev_breaking if item_key(it) in available_keys]

    # New Breaking: prefer items NOT in last Breaking
    fresh_breaking = [it for it in candidates if item_key(it) not in prev_breaking_keys]
    breaking = fresh_breaking[:7]

    # If we can't fill 7, allow reusing old ones (but still deduped)
    if len(breaking) < 7:
        fill = [it for it in candidates if item_key(it) not in {item_key(x) for x in breaking}]
        breaking = (breaking + fill)[:7]

    breaking_keys = {item_key(it) for it in breaking}

    # Developing: max 10, priority to dropped-from-breaking
    developing = []
    developing.extend([it for it in dropped_from_breaking if item_key(it) not in breaking_keys])

    # Fill rest from remaining candidates (excluding breaking and already included)
    dev_keys = {item_key(it) for it in developing}
    for it in candidates:
        k = item_key(it)
        if k in breaking_keys or k in dev_keys:
            continue
        developing.append(it)
        dev_keys.add(k)
        if len(developing) >= 10:
            break

    return breaking, developing


def main():
    existing = load_existing(HEADLINES_PATH)
    prev_sections = existing.get("sections", {}) if isinstance(existing, dict) else {}

    sections = {}

    # Breaking + Developing special rules
    breaking, developing = build_breaking_and_developing(prev_sections)
    sections["breaking"] = breaking
    sections["developing"] = developing

    # Other sections
    cfg = {
        "nothingburger": {"limit": 10, "take_each": 30, "left": LEFT_GENERAL,  "right": RIGHT_GENERAL,  "filter_fn": is_nothingburger},
        "world":         {"limit": 14, "take_each": 24, "left": WORLD_LEFT,   "right": WORLD_RIGHT,    "filter_fn": None},
        "politics":      {"limit": 14, "take_each": 18, "left": LEFT_POLITICS, "right": RIGHT_POLITICS, "filter_fn": None},
        "markets":       {"limit": 14, "take_each": 18, "left": LEFT_MARKETS,  "right": RIGHT_MARKETS,  "filter_fn": None},
        "tech":          {"limit": 14, "take_each": 24, "left": LEFT_TECH,     "right": RIGHT_TECH,     "filter_fn": None},
        "weird":         {"limit": 12, "take_each": 24, "left": LEFT_WEIRD,    "right": RIGHT_WEIRD,    "filter_fn": None},
    }

    for sec, c in cfg.items():
        left_pool = pull_sources(c["left"], take_each=c["take_each"])
        right_pool = pull_sources(c["right"], take_each=c["take_each"])

        fn = c["filter_fn"]
        if fn:
            left_pool = [x for x in left_pool if fn(x["title"])]
            right_pool = [x for x in right_pool if fn(x["title"])]

        sections[sec] = alternate(left_pool, right_pool, c["limit"])

    # Global dedupe in priority order
    priority = ["breaking", "developing", "nothingburger", "world", "politics", "markets", "tech", "weird"]
    sections, used = global_dedupe_in_priority(sections, priority)

    # Missed section
    missed_left_sources = LEFT_GENERAL + LEFT_POLITICS + LEFT_MARKETS + LEFT_TECH + LEFT_WEIRD + WORLD_LEFT
    missed_right_sources = RIGHT_GENERAL + RIGHT_POLITICS + RIGHT_MARKETS + RIGHT_TECH + RIGHT_WEIRD + WORLD_RIGHT

    missed_left = pull_sources(missed_left_sources, take_each=12)
    missed_right = pull_sources(missed_right_sources, take_each=12)

    missed_left = [it for it in missed_left if item_key(it) not in used]
    missed_right = [it for it in missed_right if item_key(it) not in used]

    sections["missed"] = dedupe_list(alternate(missed_left, missed_right, 12))

    final = {
        "breaking": sections.get("breaking", [])[:7],
        "developing": sections.get("developing", [])[:10],
        "nothingburger": sections.get("nothingburger", []),
        "world": sections.get("world", []),
        "politics": sections.get("politics", []),
        "markets": sections.get("markets", []),
        "tech": sections.get("tech", []),
        "weird": sections.get("weird", []),
        "missed": sections.get("missed", []),
    }

    # Snark assignment (preserves alternating order; no alphabetical sort)
    all_items = []
    for sec in ["breaking", "developing", "nothingburger", "world", "politics", "markets", "tech", "weird", "missed"]:
        all_items.extend(final.get(sec, []))
    assign_unique_snark(all_items)

    # Skip write if sections unchanged (prevents meta-only diffs/commits)
    old_sections = prev_sections if isinstance(prev_sections, dict) else None
    if old_sections is not None:
        if stable_sections_hash(old_sections) == stable_sections_hash(final):
            print("No section changes; skipping write.")
            return

    data = {
        "meta": {"generated_at": now_iso(), "version": 7},
        "sections": final,
    }

    with open(HEADLINES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Wrote headlines.json (sections changed).")


if __name__ == "__main__":
    main()
