(() => {
  // ===== SETTINGS =====
  const REFRESH_EVERY_MS = 5 * 60 * 1000; // check for updated headlines.json every 5 minutes
  const HISTORY_DAYS = 7;

  // Local storage keys (per-device)
  const HISTORY_KEY = "dse_history_v4";
  const CLICKS_KEY  = "dse_clicks_v4";

  const SPECIAL_NAMES = {
    burger: "Nothing Burger of the Day",
    missed: "A Line Most People Missed",
    week:   "Week in Review",
    same:   "Same Story, Different Outlet",
    breaking: "Breaking",
    developing: "Developing"
  };

  // ===== helpers =====
  const qs = (id) => document.getElementById(id);
  const s = (x) => (x ?? "").toString().trim();

  function showError(msg){
    const el = qs("err");
    if (!el) return;
    el.style.display = "block";
    el.textContent = msg;
  }
  function clearError(){
    const el = qs("err");
    if (!el) return;
    el.style.display = "none";
    el.textContent = "";
  }

  function getLS(key, fallback){
    try { return JSON.parse(localStorage.getItem(key) || ""); }
    catch { return fallback; }
  }
  function setLS(key, val){
    localStorage.setItem(key, JSON.stringify(val));
  }

  function trackClick(url){
    if (!url) return;
    const clicks = getLS(CLICKS_KEY, {});
    clicks[url] = Date.now();
    setLS(CLICKS_KEY, clicks);
  }

  function pruneHistory(history){
    const cutoff = Date.now() - HISTORY_DAYS*24*60*60*1000;
    return (history || []).filter(x => x && x.t && x.t >= cutoff && x.url && x.title);
  }

  function uniqByUrl(items){
    const seen = new Set();
    const out = [];
    for (const it of (items || [])){
      if (!it || !it.url) continue;
      if (seen.has(it.url)) continue;
      seen.add(it.url);
      out.push(it);
    }
    return out;
  }

  function flattenAllItems(data){
    const out = [];
    for (const col of (data?.columns || [])){
      for (const sec of (col?.sections || [])){
        for (const it of (sec?.items || [])){
          if (!it) continue;
          const url = s(it.url);
          const title = s(it.title);
          if (!url || !title) continue;
          out.push({
            title,
            url,
            source: s(it.source),
            snark: s(it.snark),
            feature: !!it.feature,
            badge: s(it.badge || ""),
            section: s(sec.name || "")
          });
        }
      }
    }
    return out;
  }

  // ===== rendering =====
  function renderStory(item){
    const div = document.createElement("div");
    div.className = "story" + (item.feature ? " feature" : "");

    if (item.badge) {
      const b = document.createElement("span");
      b.className = "badge";
      b.textContent = item.badge;
      div.appendChild(b);
    }

    const a = document.createElement("a");
    a.href = item.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = item.title;
    a.addEventListener("click", () => trackClick(item.url));
    div.appendChild(a);

    if (item.source) {
      const src = document.createElement("span");
      src.className = "source";
      src.textContent = `(${item.source})`;
      div.appendChild(src);
    }

    if (item.snark) {
      const sn = document.createElement("div");
      sn.className = "snark";
      sn.textContent = item.snark;
      div.appendChild(sn);
    }

    return div;
  }

  function renderSection(name, items, { breaking=false, note="" } = {}){
    const sec = document.createElement("div");
    sec.className = "section";

    const title = document.createElement("div");
    title.className = "section-title" + (breaking ? " breaking" : "");
    title.textContent = name;
    sec.appendChild(title);

    const safeItems = (items || []).filter(it => it && it.url && it.title);

    if (!safeItems.length){
      const empty = document.createElement("div");
      empty.className = "note";
      empty.textContent = "No items right now.";
      sec.appendChild(empty);
      return sec;
    }

    safeItems.forEach(it => sec.appendChild(renderStory(it)));

    if (note){
      const n = document.createElement("div");
      n.className = "note";
      n.textContent = note;
      sec.appendChild(n);
    }

    return sec;
  }

  function findSection(data, exactName){
    for (const col of (data?.columns || [])){
      for (const sec of (col?.sections || [])){
        if (s(sec?.name) === exactName) return sec;
      }
    }
    return null;
  }

  function mapItems(sec){
    return (sec?.items || []).map(it => ({
      title: s(it?.title),
      url: s(it?.url),
      source: s(it?.source),
      snark: s(it?.snark),
      feature: !!it?.feature,
      badge: s(it?.badge || "")
    })).filter(it => it.url && it.title);
  }

  function stripBadgesAndFeatures(items){
    return (items || []).filter(Boolean).map(it => ({ ...it, badge:"", feature:false }));
  }

  // ===== algorithmic sections =====
  function pickNothingBurger(todayItems){
    const LOW = [
      "celebrity","royal","netflix","tiktok","iphone","android","review","tips","recipe",
      "fashion","beauty","dating","viral","meme","trend","podcast","travel","diet",
      "coffee","sleep","study","app","streaming"
    ];
    const TRAGIC = /(dead|dies|killed|death|shooting|attack|war|bomb|explosion|terror|crash|earthquake|wildfire|flood|victim|injured)/i;

    const candidates = (todayItems || []).filter(it => {
      const t = (it?.title || "").toLowerCase();
      return it?.url && !TRAGIC.test(t) && LOW.some(k => t.includes(k));
    });

    return candidates[0] || (todayItems || []).find(x => x && x.url && !x.feature) || (todayItems || [])[0] || null;
  }

  function pickMostMissed(history){
    const clicks = getLS(CLICKS_KEY, {});
    const unclicked = (history || []).filter(it => it?.url && !clicks[it.url] && !it.feature && it.badge !== "BREAK");
    return unclicked[0] || null;
  }

  function buildWeekInReview(history){
    const counts = new Map();
    for (const it of (history || [])){
      if (!it?.url) continue;
      counts.set(it.url, (counts.get(it.url) || 0) + 1);
    }

    return [...counts.entries()]
      .sort((a,b) => b[1]-a[1])
      .slice(0, 7)
      .map(([url]) => (history || []).find(h => h && h.url === url))
      .filter(Boolean);
  }

  function normalizeKey(title){
    const t = (title || "")
      .toLowerCase()
      .replace(/&/g, " and ")
      .replace(/[^a-z0-9\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    const stop = new Set(["the","a","an","to","of","in","on","for","and","or","with","as","at","by","from","into","after","before","over","under","is","are","was","were"]);
    const parts = t.split(" ").filter(w => w.length >= 4 && !stop.has(w));
    return parts.slice(0, 12).join(" ");
  }

  function findSameStoryPair(todayItems){
    const items = (todayItems || []).filter(it => it && it.title && it.url && it.source);
    const tokens = items.map(it => {
      const key = normalizeKey(it.title);
      const set = new Set(key.split(" ").filter(Boolean));
      return { it, set };
    });

    let best = null;
    let bestScore = 0;

    for (let i=0; i<tokens.length; i++){
      for (let j=i+1; j<tokens.length; j++){
        const a = tokens[i], b = tokens[j];
        if (a.it.source === b.it.source) continue;

        let shared = 0;
        for (const w of a.set) if (b.set.has(w)) shared++;
        if (shared < 2) continue;

        const union = a.set.size + b.set.size - shared;
        const score = union > 0 ? (shared / union) : 0;

        if (score > bestScore){
          bestScore = score;
          best = [a.it, b.it];
        }
      }
    }

    if (!best) return null;

    // For this section, do NOT show badge/feature/snark (keeps it clean)
    return best.map(x => ({ ...x, badge:"", feature:false, snark:"" }));
  }

  // ===== layout =====
  function render3Columns(data){
    const colsEl = qs("columns");
    if (!colsEl) return;
    colsEl.innerHTML = "";

    // Collect today items
    const todayItems = uniqByUrl(flattenAllItems(data));

    // Update & persist 7-day history (per device)
    let history = pruneHistory(getLS(HISTORY_KEY, []));
    const existing = new Set(history.map(h => h.url));

    for (const it of todayItems){
      if (!existing.has(it.url)){
        history.push({ ...it, t: Date.now() });
        existing.add(it.url);
      }
    }
    history = pruneHistory(history);
    setLS(HISTORY_KEY, history);

    const burgerPick = pickNothingBurger(todayItems);
    const missedPick = pickMostMissed(history);
    const weekList   = buildWeekInReview(history);
    const samePair   = findSameStoryPair(todayItems);

    const col1 = document.createElement("div");
    const col2 = document.createElement("div");
    const col3 = document.createElement("div");

    // Column 1: Breaking + Developing + Burger
    const breakingSec = findSection(data, SPECIAL_NAMES.breaking);
    if (breakingSec) col1.appendChild(renderSection(SPECIAL_NAMES.breaking, mapItems(breakingSec), { breaking:true }));

    const developingSec = findSection(data, SPECIAL_NAMES.developing);
    if (developingSec) col1.appendChild(renderSection(SPECIAL_NAMES.developing, mapItems(developingSec)));

    col1.appendChild(renderSection(
      SPECIAL_NAMES.burger,
      burgerPick ? [burgerPick] : [],
      { note: burgerPick ? "Auto-picked: low-stakes + tragedy-filtered." : "No suitable pick found today." }
    ));

    // Column 2: Your real categories (no Top)
    const businessSec = findSection(data, "Business");
    if (businessSec) col2.appendChild(renderSection("Business", mapItems(businessSec)));

    const wtwSec = findSection(data, "World / Tech / Weird");
    if (wtwSec) col2.appendChild(renderSection("World / Tech / Weird", mapItems(wtwSec)));

    // Column 3: Algorithmic extras
    col3.appendChild(renderSection(
      SPECIAL_NAMES.missed,
      missedPick ? stripBadgesAndFeatures([missedPick]) : [],
      { note: "" }
    ));

    col3.appendChild(renderSection(
      SPECIAL_NAMES.same,
      samePair ? samePair : [],
      { note: samePair ? "" : "No clean pair found today." }
    ));

    col3.appendChild(renderSection(
      SPECIAL_NAMES.week,
      stripBadgesAndFeatures(weekList),
      { note: "" }
    ));

    colsEl.appendChild(col1);
    colsEl.appendChild(col2);
    colsEl.appendChild(col3);
  }

  // ===== loading =====
  async function fetchHeadlinesNoCache(){
    // Cache-busting query param + cache: "no-store" keeps clients current
    const url = "./headlines.json?ts=" + Date.now();
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return await r.json();
  }

  let lastGeneratedUTC = null;

  async function refresh({ force=false } = {}){
    try{
      clearError();
      const data = await fetchHeadlinesNoCache();

      // Only redraw when generator timestamp changes (unless forced)
      const gen = s(data?.generated_utc);
      if (!force && gen && gen === lastGeneratedUTC) return;
      lastGeneratedUTC = gen || lastGeneratedUTC;

      // Header text updates (icon cannot be overwritten because it's separate)
      const nameEl = qs("siteNameText");
      if (nameEl && data?.site?.name) nameEl.textContent = data.site.name;

      const tagEl = qs("siteTagline");
      if (tagEl && data?.site?.tagline) tagEl.textContent = data.site.tagline;

      const updEl = qs("updated");
      if (updEl){
        updEl.textContent = data?.generated_utc
          ? "Last updated: " + new Date(data.generated_utc).toLocaleString() + (force ? " • Updated ✓" : "")
          : "";
      }

      render3Columns(data);

    } catch (e){
      showError("Load error: " + (e?.message || String(e)));
      const updEl = qs("updated");
      if (updEl) updEl.textContent = "Unable to load headlines right now.";
      const colsEl = qs("columns");
      if (colsEl) colsEl.innerHTML = "";
    }
  }

  // Update button: refresh the JSON right now (without changing URL)
  const btn = qs("updateBtn");
  if (btn) btn.addEventListener("click", () => refresh({ force:true }));

  refresh({ force:true });
  setInterval(() => refresh({ force:false }), REFRESH_EVERY_MS);
})();
