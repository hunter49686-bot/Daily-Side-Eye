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


def dedupe_list(items):
    seen = set()
    out = []
    for it in items:
        key = (it.get("title", "").lower(), it.get("url", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def pull_sources(sources, take_each):
    combined = []
    for name, url in sources:
        parsed = fetch_feed(url)
        combined.extend(items_from_feed(parsed, name, max_items=take_each))
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
            key = (it.get("title", "").lower(), it.get("url", ""))
            if key in seen:
                continue
            seen.add(key)
            filtered.append(it)
        section_map[sec] = filtered
    return section_map, seen


# ----------------------------
# Snark generation (unique per page, NO hash suffixes)
# Ensure templates > max non-tragic items so we never run out.
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
    "Today’s sponsor is… oh wait, no promos allowed.",
    "Somebody is about to ‘clarify’ for 72 hours straight.",
    "The ‘sources say’ era continues.",
    "This is the kind of certainty that ages poorly.",
    "If this is leadership, where’s the adult supervision?",
    "A lot of words to say ‘we’ll see.’",
    "The strategy appears to be vibes and prayer.",
    "This is what happens when group chats run government.",
    "A thrilling episode of ‘nobody read the memo.’",
    "Consider this your daily reminder to check the fine print.",
    "The confidence-to-competence ratio is alarming.",
    "It’s a bold claim for someone with no citations.",
    "We love a plan that collapses on contact.",
    "Reality remains undefeated.",
    "This could’ve been prevented by reading the room.",
    "Somebody mistook a hunch for a policy.",
    "The optics are doing the heavy lifting.",
    "Another victory for the ‘wait, what?’ community.",
    "A proud moment for chaos enthusiasts.",
    "It’s giving ‘we’ll workshop it later.’",
    "They chose violence. Bureaucratic violence.",
    "This is a great way to lose a weekend.",
    "The narrative is sprinting; the facts are strolling.",
    "This is why adults shouldn’t be allowed to improvise.",
    "An exciting new chapter in ‘avoidable.’",
    "The plan is simple: pretend this is fine.",
    "The justification is thin, like hotel towels.",
    "Somebody’s lawyer just sighed.",
    "The PR team is about to earn their keep.",
    "A reminder: punctuation is not accountability.",
    "This is the kind of headline that needs a disclaimer.",
    "This is not a solution; it’s an activity.",
    "The follow-up will be spectacular.",
    "We are all trapped in a pilot episode.",
    "The certainty is loud; the evidence is shy.",
    "This is a situation, not a strategy.",
    "Somebody pressed ‘send’ and immediately regretted it.",
    "The headline is spicy; the details are plain oatmeal.",
    "If this is the plan, what’s the backup?",
    "This is why we can’t have nice institutions.",
    "The vibes are immaculate. The logic is not.",
    "This will age like milk in July.",
    "A brave attempt at narrative control.",
    "Somebody is allergic to straightforward answers.",
    "This is a strong argument for naps.",
    "A bold swing at basic arithmetic.",
    "The explanation is doing interpretive dance.",
    "Today in ‘choices were made.’",
    "This is what happens when nobody owns the decision.",
    "The headline is a promise; the article is an apology.",
    "We’ve entered the ‘walk it back’ portion of the program.",
    "Somebody confused attention with approval.",
    "This is a case study in how not to do this.",
    "This is the kind of plan that needs adult supervision.",
    "The details are thin, but the confidence is thick.",
    "We love a theory that ignores reality.",
    "This is the chaos tax coming due.",
    "A thrilling update from the land of consequences.",
    "The subtext is screaming.",
    "This is why you don’t let vibes drive the bus.",
    "The headline is yelling; the facts are whispering.",
    "This is not a pivot, it’s a wobble.",
    "Somebody is about to discover what ‘oversight’ means.",
    "This is a bold claim for a Tuesday.",
    "The strategy appears to be ‘hope.’",
    "The evidence is missing; the confidence is present.",
    "It’s giving ‘we’ll circle back’ forever.",
    "This is why we read past the headline.",
    "A gentle reminder that reality keeps receipts.",
    "This is a classic case of ‘nice try.’",
    "The plan is evolving. That’s not comforting.",
    "We are watching an idea escape containment.",
    "This is a good way to create a new problem.",
    "A bold move from someone who hates follow-ups.",
    "The spin is impressive, in a concerning way.",
    "This feels like an intern wrote the timeline.",
    "The details are here to ruin the story.",
    "A proud moment for unintended consequences.",
    "This is not a headline; it’s a cry for help.",
    "The argument is strong… emotionally.",
    "This will be clarified into oblivion.",
    "This is why we can’t have simple news.",
    "The logic is on vacation.",
    "This is an ambitious misunderstanding.",
    "The headline is doing the most.",
    "The details are a jump scare.",
    "This is an interesting choice for people with reputations.",
    "The vibes are confident; the math is not.",
    "A bold attempt to redefine ‘working.’",
    "This is an expensive way to learn a lesson.",
    "We are witnessing the consequences draft itself.",
    "The headline is confident; the plan is vibes.",
    "This is what ‘minimum viable’ looks like in the wild.",
    "A heroic effort to avoid responsibility.",
    "This is a high-stakes game of ‘maybe.’",
    "The narrative is doing gymnastics.",
    "This is a real sentence someone approved.",
    "A reminder: words are not a substitute for plans.",
    "The plot twist is: nobody checked.",
    "This is the ‘find out’ portion of the program.",
    "The confidence is so loud it’s clipping.",
    "An exciting new way to be wrong.",
    "This is what happens when you skip step two.",
    "We love a headline that begs for context.",
    "The logic has left the building.",
    "This is a bold choice for people with jobs.",
    "The accountability is not in the room.",
    "This is the kind of optimism that needs a helmet.",
    "Another day, another ‘temporary’ policy.",
    "This is how meetings become headlines.",
    "This reads like a dare.",
    "The solution is… vibes.",
    "This is an inventive approach to being unprepared.",
    "A confident move from the land of assumptions.",
    "This is a strategic misunderstanding.",
    "The vibe is ‘we tried nothing.’",
    "This is a plan made of duct tape.",
    "The details are doing damage control.",
    "This is the kind of headline that needs adult supervision.",
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

        # If we somehow run out (should not), show nothing instead of adding hashes.
        if chosen is None:
            it["snark"] = ""
            continue

        used.add(chosen)
        it["snark"] = chosen


def load_existing_sections(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        return existing.get("sections"), existing.get("meta", {})
    except FileNotFoundError:
        return None, {}
    except Exception:
        return None, {}


def stable_sections_hash(sections_obj) -> str:
    blob = json.dumps(
        sections_obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ----------------------------
# Source pools (balance buckets)
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


def main():
    sections = {}

    cfg = {
        "breaking":      {"limit": 7,  "take_each": 18, "left": LEFT_GENERAL,  "right": RIGHT_GENERAL,  "filter_fn": None},
        "developing":    {"limit": 14, "take_each": 18, "left": LEFT_GENERAL,  "right": RIGHT_GENERAL,  "filter_fn": None},
        "nothingburger": {"limit": 10, "take_each": 30, "left": LEFT_GENERAL,  "right": RIGHT_GENERAL,  "filter_fn": is_nothingburger},

        "world":         {"limit": 14, "take_each": 18, "left": LEFT_GENERAL,  "right": RIGHT_GENERAL,  "filter_fn": None},
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

    priority = ["breaking", "developing", "nothingburger", "world", "politics", "markets", "tech", "weird"]
    sections, used = global_dedupe_in_priority(sections, priority)

    missed_left_sources = LEFT_GENERAL + LEFT_POLITICS + LEFT_MARKETS + LEFT_TECH + LEFT_WEIRD
    missed_right_sources = RIGHT_GENERAL + RIGHT_POLITICS + RIGHT_MARKETS + RIGHT_TECH + RIGHT_WEIRD

    missed_left = pull_sources(missed_left_sources, take_each=12)
    missed_right = pull_sources(missed_right_sources, take_each=12)

    missed_left = [it for it in missed_left if (it["title"].lower(), it["url"]) not in used]
    missed_right = [it for it in missed_right if (it["title"].lower(), it["url"]) not in used]

    sections["missed"] = dedupe_list(alternate(missed_left, missed_right, 12))

    final = {
        "breaking": sections.get("breaking", [])[:7],
        "developing": sections.get("developing", []),
        "nothingburger": sections.get("nothingburger", []),
        "world": sections.get("world", []),
        "politics": sections.get("politics", []),
        "markets": sections.get("markets", []),
        "tech": sections.get("tech", []),
        "weird": sections.get("weird", []),
        "missed": sections.get("missed", []),
    }

    # Optional but recommended: deterministic ordering to reduce churn from feed ordering
    for sec, items in final.items():
        final[sec] = sorted(items, key=lambda it: (it.get("source", ""), it.get("title", ""), it.get("url", "")))

    # Assign snark after final ordering so uniqueness collisions are stable
    all_items = []
    for sec in ["breaking", "developing", "nothingburger", "world", "politics", "markets", "tech", "weird", "missed"]:
        all_items.extend(final.get(sec, []))
    assign_unique_snark(all_items)

    # If sections did not change vs previous run, do NOT rewrite file (prevents meta-only diffs)
    existing_sections, _existing_meta = load_existing_sections(HEADLINES_PATH)
    new_hash = stable_sections_hash(final)
    old_hash = stable_sections_hash(existing_sections) if existing_sections else None

    if old_hash == new_hash:
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
