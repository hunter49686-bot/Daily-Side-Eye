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
            title: it.title,
            url: it.url,
            source: it.source,
            snark: it.snark,
            feature: !!it.feature,
            badge: it.badge || "",
            section: sec.name || ""
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

    const badge = item.badge ? `<span class="badge">${item.badge}</span>` : "";
    div.innerHTML = `
      ${badge}
      <a href="${item.url}" target="_blank" rel="noopener noreferrer">${item.title}</a>
      <span class="source">(${item.source})</span>
      ${item.snark ? `<div class="snark">${item.snark}</div>` : ``}
    `;

    const a = div.querySelector("a");
    if (a) a.addEventListener("click", () => trackClick(item.url));
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
      "coffee","sleep","study","ai","app","streaming"
    ];
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
    // “Top recurring” based on how often an item remained in your 7-day local history
    // (This is per-device; there’s no server tracking on GitHub Pages.)
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

  // ===== layout =====
  function renderAllSectionsAsGiven(data){
    const colsEl = qs("columns");
    colsEl.innerHTML = "";

    for (const col of (data.columns || [])){
      const colDiv = document.createElement("div");
      for (const sec of (col.sections || [])){
        colDiv.appendChild(renderSection(
          s(sec.name),
          sec.items || [],
          { breaking: s(sec.name).toLowerCase() === "breaking" }
        ));
      }
      colsEl.appendChild(colDiv);
    }
  }

  function renderWithAlgorithmicExtras(data){
    const colsEl = qs("columns");
    colsEl.innerHTML = "";

    // Collect today items from the feed
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

    // Algorithmic picks
    const burgerPick = pickNothingBurger(todayItems);
    const missedPick = pickMostMissed(history);
    const weekList   = buildWeekInReview(history);

    // Column 1: Breaking + Nothing Burger
    const col1 = document.createElement("div");

    // Find Breaking section from your JSON (exact name match)
    const breakingSec = findSection(data, SPECIAL_NAMES.breaking);
    if (breakingSec) {
      col1.appendChild(renderSection(SPECIAL_NAMES.breaking, breakingSec.items || [], { breaking:true }));
    }

    // Nothing Burger section algorithmic
    col1.appendChild(renderSection(
      SPECIAL_NAMES.burger,
      burgerPick ? [burgerPick] : [],
      { note: burgerPick ? "Auto-picked: low-stakes + tragedy-filtered." : "No suitable pick found today." }
    ));

    // Column 2: Everything else from your JSON, EXCEPT we skip if it duplicates our algorithmic names
    const col2 = document.createElement("div");
    const skipNames = new Set([
      SPECIAL_NAMES.burger,
      SPECIAL_NAMES.missed,
      SPECIAL_NAMES.week
    ].map(x => x.toLowerCase()));

    // Render your existing sections normally (keeps your current site structure)
    for (const col of (data.columns || [])){
      for (const sec of (col.sections || [])){
        const name = s(sec.name);
        if (!name) continue;
        if (skipNames.has(name.toLowerCase())) continue; // don’t double-render
        if (name.toLowerCase() === SPECIAL_NAMES.breaking.toLowerCase()) continue; // already placed in col1
        col2.appendChild(renderSection(name, sec.items || [], { breaking: name.toLowerCase()==="breaking" }));
      }
    }

    // Column 3: Most Missed + Week in Review
    const col3 = document.createElement("div");

    col3.appendChild(renderSection(
      SPECIAL_NAMES.missed,
      missedPick ? [missedPick] : [],
      { note: missedPick ? "From your unclicked items (this device only)." : "No history yet (or you clicked everything)." }
    ));

    col3.appendChild(renderSection(
      SPECIAL_NAMES.week,
      weekList,
      { note: weekList.length ? "Top recurring items from your last 7 days (this device only)." : "No 7-day history yet." }
    ));

    // If your site is currently two columns, this still works: the third column will wrap under on mobile.
    // Desktop will show 2 columns unless your CSS is 3 columns. Your index.html is 2 columns currently.
    // We can change it to 3 columns later if you want.
    colsEl.appendChild(col1);
    colsEl.appendChild(col2);
    colsEl.appendChild(col3);
  }

  function findSection(data, exactName){
    for (const col of (data.columns || [])){
      for (const sec of (col.sections || [])){
        if (s(sec.name) === exactName) return sec;
      }
    }
    return null;
  }

  // ===== loading =====
  async function fetchHeadlinesNoCache(){
    const url = "./headlines.json?v=" + Date.now();
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return await r.json();
  }

  let lastGeneratedUTC = null;

  async function refresh(){
    try{
      clearError();
      const data = await fetchHeadlinesNoCache();

      // Only redraw when the generator timestamp changes (reduces flicker)
      const gen = s(data.generated_utc);
      if (gen && gen === lastGeneratedUTC) return;
      lastGeneratedUTC = gen;

      // Header
      if (data.site?.name) qs("siteName").textContent = data.site.name;
      if (data.site?.tagline) qs("siteTagline").textContent = data.site.tagline;

      qs("updated").textContent = data.generated_utc
        ? "Last updated: " + new Date(data.generated_utc).toLocaleString()
        : "";

      // Render with algorithmic sections
      renderWithAlgorithmicExtras(data);

    } catch (e){
      showError("Load error: " + (e?.message || String(e)));
      qs("updated").textContent = "Unable to load headlines right now.";
      qs("columns").innerHTML = "";
    }
  }

  // Hard refresh: force a brand-new URL so mobile cache can’t lie
  qs("hardRefreshBtn").addEventListener("click", () => {
    const base = location.href.split("?")[0];
    location.href = base + "?v=" + Date.now();
  });

  // Run
  refresh();
  setInterval(refresh, REFRESH_EVERY_MS);
})();