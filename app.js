(() => {
  // ===== SETTINGS =====
  const REFRESH_EVERY_MS = 5 * 60 * 1000;
  const HISTORY_DAYS = 7;

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
            section: s(sec.name || ""),
            published_utc: s(it.published_utc || "")
          });
        }
      }
    }
    return out;
  }

  // ===== rendering (XSS-safe: no innerHTML with feed data) =====
  function renderStory(item){
    const div = document.createElement("div");
    div.className = "story" + (item.feature ? " feature" : "");

    // Headline row
    const headRow = document.createElement("div");
    headRow.style.display = "flex";
    headRow.style.flexWrap = "wrap";
    headRow.style.alignItems = "baseline";
    headRow.style.gap = "8px";

    if (item.badge) {
      const b = document.createElement("span");
      b.className = "badge";
      b.textContent = item.badge;
      headRow.appendChild(b);
    }

    const a = document.createElement("a");
    a.href = item.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = item.title || "(untitled)";
    a.addEventListener("click", () => trackClick(item.url));
    headRow.appendChild(a);

    if (item.source) {
      const src = document.createElement("span");
      src.className = "source";
      // IMPORTANT: leading separator so it doesn’t “glue” to title
      src.textContent = `• ${item.source}`;
      headRow.appendChild(src);
    }

    div.appendChild(headRow);

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

  // ===== layout (2 columns, consistent with your CSS) =====
  function stripBadgesAndFeatures(items){
    return (items || []).map(it => ({
      ...it,
      badge: "",
      feature: false
    }));
  }

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

    const breakingSec = findSection(data, SPECIAL_NAMES.breaking);
    if (breakingSec) {
      col1.appendChild(renderSection(SPECIAL_NAMES.breaking, breakingSec.items || [], { breaking:true }));
    }

    col1.appendChild(renderSection(
      SPECIAL_NAMES.burger,
      burgerPick ? [burgerPick] : [],
      { note: burgerPick ? "Auto-picked: low-stakes + tragedy-filtered." : "No suitable pick found today." }
    ));

    // Column 2: Your JSON sections except Breaking
    const skipNames = new Set([
      SPECIAL_NAMES.burger.toLowerCase(),
      SPECIAL_NAMES.missed.toLowerCase(),
      SPECIAL_NAMES.week.toLowerCase(),
      SPECIAL_NAMES.breaking.toLowerCase()
    ]);

    for (const col of (data.columns || [])){
      for (const sec of (col.sections || [])){
        const name = s(sec.name);
        if (!name) continue;
        if (skipNames.has(name.toLowerCase())) continue;
        col2.appendChild(renderSection(name, sec.items || []));
      }
    }

    // Specials at bottom of col2 (badge/feature stripped)
    col2.appendChild(renderSection(
      SPECIAL_NAMES.missed,
      missedPick ? stripBadgesAndFeatures([missedPick]) : [],
      { note: mi
