(() => {
  // ===== SETTINGS =====
  const REFRESH_EVERY_MS = 5 * 60 * 1000; // check for updated headlines.json every 5 minutes
  const HISTORY_DAYS = 7;

  // Local storage keys (per-device)
  const HISTORY_KEY = "dse_history_v2";
  const CLICKS_KEY  = "dse_clicks_v2";

  const SPECIAL_NAMES = {
    burger: "Nothing Burger of the Day",
    missed: "A Line Most People Missed",
    week:   "Week in Review",
    breaking: "Breaking"
  };

  // ===== helpers =====
  const qs = (id) => document.getElementById(id);
  const s = (x) => (x ?? "").toString().trim();

  function showError(msg){
    const el = qs("err");
    el.style.display = "block";
    el.textContent = msg;
  }
  function clearError(){
    const el = qs("err");
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
    for (const it of items){
      if (!it || !it.url) continue;
      if (seen.has(it.url)) continue;
      seen.add(it.url);
      out.push(it);
    }
    return out;
  }

  function flattenAllItems(data){
    const out = [];
    for (const col of (data.columns || [])){
      for (const sec of (col.sections || [])){
        for (const it of (sec.items || [])){
          out.push({
            title: s(it.title),
            url: s(it.url),
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

  // ===== SAFE rendering (no innerHTML for feed strings) =====
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
    a.textContent = item.title || "(untitled)";
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

    if (!items || !items.length){
      const empty = document.createElement("div");
      empty.className = "note";
      empty.textContent = "No items right now.";
      sec.appendChild(empty);
      return sec;
    }

    items.forEach(it => sec.appendChild(renderStory(it)));

    if (note){
      const n = document.createElement("div");
      n.className = "note";
      n.textContent = note;
      sec.appendChild(n);
    }

    return sec;
  }

  // ===== algorithmic sections =====
  function pickNothingBurger(todayItems){
    const LOW = [
      "celebrity","royal","netflix","tiktok","iphone","android","review","tips","recipe",
      "fashion","beauty","dating","viral","meme","trend","podcast","travel","diet",
      "coffee","sleep","study","app","streaming"
    ];
    // Note: removed "ai" (too common + can feel editorial)
    const TRAGIC = /(dead|dies|killed|death|shooting|attack|war|bomb|explosion|terror|crash|earthquake|wildfire|flood|victim|injured)/i;

    const candidates = todayItems.filter(it => {
      const t = (it.title || "").toLowerCase();
      return !TRAGIC.test(t) && LOW.some(k => t.includes(k));
    });

    return candidates[0] || todayItems.find(x => !x.feature) || todayItems[0] || null;
  }

  function pickMostMissed(history){
    const clicks = getLS(CLICKS_KEY, {});
    const unclicked = history.filter(it => it.url && !clicks[it.url] && !it.feature && it.badge !== "BREAK");
    return unclicked[0] || null;
  }

  function buildWeekInReview(history){
    const counts = new Map();
    for (const it of history){
      if (!it.url) continue;
      counts.set(it.url, (counts.get(it.url) || 0) + 1);
    }

    return [...counts.entries()]
      .sort((a,b) => b[1]-a[1])
      .slice(0, 7)
      .map(([url]) => history.find(h => h.url === url))
      .filter(Boolean);
  }

  function findSection(data, exactName){
    for (const col of (data.columns || [])){
      for (const sec of (col.sections || [])){
        if (s(sec.name) === exactName) return sec;
      }
    }
    return null;
  }

  // ===== 2-column layout (consistent with your CSS) =====
  function renderWithAlgorithmicExtras(data){
    const colsEl = qs("columns");
    colsEl.innerHTML = "";

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

    const col1 = document.createElement("div");
    const col2 = document.createElement("div");

    // Column 1: Breaking + Nothing Burger
    const breakingSec = findSection(data, SPECIAL_NAMES.breaking);
    if (breakingSec) {
      col1.appendChild(renderSection(SPECIAL_NAMES.breaking, breakingSec.items || [], { breaking:true }));
    }
    col1.appendChild(renderSection(
      SPECIAL_NAMES.burger,
      burgerPick ? [burgerPick] : [],
      { note: burgerPick ? "Auto-picked: low-stakes + tragedy-filtered." : "No suitable pick found today." }
    ));

    // Column 2: Your existing sections (except Breaking) + Most Missed + Week in Review at bottom
    for (const col of (data.columns || [])){
      for (const sec of (col.sections || [])){
        const name = s(sec.name);
        if (!name) continue;
        if (name.toLowerCase() === SPECIAL_NAMES.breaking.toLowerCase()) continue;
        // Avoid accidentally double-using your special names if they exist in JSON
        if ([SPECIAL_NAMES.burger, SPECIAL_NAMES.missed, SPECIAL_NAMES.week].some(x => x.toLowerCase() === name.toLowerCase())) continue;

        col2.appendChild(renderSection(name, sec.items || [], { breaking:false }));
      }
    }

    col2.appendChild(renderSection(
      SPECIAL_NAMES.missed,
      missedPick ? [missedPick] : [],
      { note: missedPick ? "From your unclicked items (this device only)." : "No history yet (or you clicked everything)." }
    ));

    col2.appendChild(renderSection(
      SPECIAL_NAMES.week,
      weekList,
      { note: weekList.length ? "Top recurring items from your last 7 days (this device only)." : "No 7-day history yet." }
    ));

    colsEl.appendChild(col1);
    colsEl.appendChild(col2);
  }

  // ===== loading / updates =====
  async function fetchHeadlinesNoCache(){
    const url = "./headlines.json?ts=" + Date.now();
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return await r.json();
  }

  let lastGeneratedUTC = null;

  function setUpdatedText(data, statusText=""){
    const gen = s(data?.generated_utc);
    const base = gen ? ("Last updated: " + new Date(gen).toLocaleString()) : "";
    qs("updated").textContent = statusText ? (base + " • " + statusText) : base;
  }

  async function refresh({ force=false } = {}){
    try{
      clearError();
      const data = await fetchHeadlinesNoCache();

      const gen = s(data.generated_utc);
      if (!force && gen && gen === lastGeneratedUTC) {
        // No redraw; still confirm if user explicitly asked
        if (force) setUpdatedText(data, "No changes");
        return;
      }

      lastGeneratedUTC = gen || lastGeneratedUTC;

      if (data.site?.name) qs("siteName").textContent = data.site.name;
      if (data.site?.tagline) qs("siteTagline").textContent = data.site.tagline;

      setUpdatedText(data, force ? "Updated ✓" : "");

      renderWithAlgorithmicExtras(data);

    } catch (e){
      showError("Load error: " + (e?.message || String(e)));
      qs("updated").textContent = "Unable to load headlines right now.";
      qs("columns").innerHTML = "";
    }
  }

  // Update button: force fetch + rerender (no full reload)
  qs("hardRefreshBtn").addEventListener("click", async () => {
    await refresh({ force:true });
  });

  // Run
  refresh();
  setInterval(() => refresh({ force:false }), REFRESH_EVERY_MS);
})();
