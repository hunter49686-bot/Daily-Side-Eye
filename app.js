(() => {
  // ===== SETTINGS =====
  const REFRESH_EVERY_MS = 5 * 60 * 1000; // 5 minutes
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

  // ===== layout =====
  function renderWithAlgorithmicExtras(data){
    const colsEl = qs("columns");
    colsEl.innerHTML = "";

    const todayItems = uniqByUrl(flattenAllItems(data));

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
    const col3 = document.createElement("div");

    const breakingSec = findSection(data, SPECIAL_NAMES.breaking);
    if (breakingSec) {
      col1.appendChild(renderSection(SPECIAL_NAMES.breaking, breakingSec.items || [], { breaking:true }));
    }

    col1.appendChild(renderSection(
      SPECIAL_NAMES.burger,
      burgerPick ? [burgerPick] : [],
      { note: burgerPick ? "Auto-picked: low-stakes + tragedy-filtered." : "No suitable pick found today." }
    ));

    // Middle column: all “normal” sections except Breaking (your main content)
    for (const col of (data.columns || [])){
      for (const sec of (col.sections || [])){
        const name = s(sec.name);
        if (!name) continue;
        if (name.toLowerCase() === SPECIAL_NAMES.breaking.toLowerCase()) continue;
        col2.appendChild(renderSection(name, sec.items || [], { breaking:false }));
      }
    }

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

    colsEl.appendChild(col1);
    colsEl.appendChild(col2);
    colsEl.appendChild(col3);
  }

  // ===== loading =====
  async function fetchHeadlinesNoCache(){
    const url = "./headlines.json?v=" + Date.now();

    const r = await fetch(url, {
      cache: "no-store",
      headers: {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache"
      }
    });

    if (!r.ok) throw new Error("HTTP " + r.status);

    // Helpful: show whether we got anything cached (some browsers expose this)
    return await r.json();
  }

  let lastGeneratedUTC = null;

  function setMetaLine(data){
    const gen = s(data?.generated_utc);
    const genLocal = gen ? new Date(gen).toLocaleString() : "unknown";
    const nowLocal = new Date().toLocaleString();

    qs("updated").textContent = gen
      ? `Last updated: ${genLocal}  •  Checked: ${nowLocal}`
      : `Checked: ${nowLocal}`;
  }

  async function refresh(){
    try{
      clearError();

      const data = await fetchHeadlinesNoCache();
      const gen = s(data.generated_utc);

      setMetaLine(data);

      // Only redraw when generator timestamp changes (reduces flicker)
      if (gen && gen === lastGeneratedUTC) return;
      lastGeneratedUTC = gen;

      if (data.site?.name) qs("siteName").textContent = data.site.name;
      if (data.site?.tagline) qs("siteTagline").textContent = data.site.tagline;

      renderWithAlgorithmicExtras(data);

    } catch (e){
      showError("Load error: " + (e?.message || String(e)));
      qs("updated").textContent = "Unable to load headlines right now.";
      qs("columns").innerHTML = "";
    }
  }

  // Buttons
  qs("hardRefreshBtn").addEventListener("click", () => {
    const base = location.href.split("?")[0];
    location.href = base + "?v=" + Date.now();
  });

  const updateBtn = qs("updateNowBtn");
  if (updateBtn){
    updateBtn.addEventListener("click", () => refresh());
  }

  // Run
  refresh();
  setInterval(refresh, REFRESH_EVERY_MS);
})();