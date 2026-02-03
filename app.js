const HEADLINES_URL = "headlines.json";

/* Military keyword detection (Breaking only) */
const MILITARY_RE = /\b(military|war|drone|missile|army|navy|air force|troops|soldiers|strike|airstrike|bomb|bombing|rocket|defense|defence|weapon|attack|conflict|battle)\b/i;

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

/* Robust fetch: bust cache, and fall back to a plain fetch if a proxy/CDN acts up */
async function fetchHeadlines() {
  const url = `${HEADLINES_URL}?v=${Date.now()}`;
  let res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    res = await fetch(HEADLINES_URL, { cache: "no-store" });
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  if (!data || !data.sections) throw new Error("Invalid headlines.json (missing sections)");
  return data;
}

function renderSection(containerId, items, { cap = null, checkMilitary = false } = {}) {
  const el = document.getElementById(containerId);
  if (!el) return;

  const list = Array.isArray(items) ? items : [];
  const use = cap ? list.slice(0, cap) : list;

  el.innerHTML = use.length
    ? use.map(it => {
        const title = escapeHtml(it.title || "");
        const source = escapeHtml(it.source || "");
        const url = it.url || "#";

        const snarkText = (it.snark && typeof it.snark === "string") ? it.snark.trim() : "";
        const snarkLine = snarkText ? `<div class="source snark">${escapeHtml(snarkText)}</div>` : "";

        const isMilitary = checkMilitary && MILITARY_RE.test(it.title || "");
        const classes = `headline${isMilitary ? " military" : ""}`;

        return `
          <a class="${classes}" href="${url}" target="_blank" rel="noopener noreferrer">
            <div class="title">${title}</div>
            <div class="meta-row">
              <div class="source">${source}</div>
            </div>
            ${snarkLine}
          </a>
        `;
      }).join("")
    : `<div class="empty">No items right now.</div>`;
}

function formatUtcIso(iso) {
  try { return new Date(iso).toUTCString(); } catch { return "Unknown"; }
}

function showLoading() {
  // Ensure content appears immediately under headers, even while fetching
  const loadingHtml = `<div class="empty">Loading…</div>`;
  ["breaking","developing","nothingburger","world","politics","markets","tech","weird","missed"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = loadingHtml;
  });
}

async function init() {
  showLoading();

  try {
    const data = await fetchHeadlines();
    const s = data.sections || {};

    renderSection("breaking", s.breaking, { cap: 7, checkMilitary: true });
    renderSection("developing", s.developing);
    renderSection("nothingburger", s.nothingburger);

    renderSection("world", s.world);
    renderSection("politics", s.politics);
    renderSection("markets", s.markets);

    renderSection("tech", s.tech);
    renderSection("weird", s.weird);
    renderSection("missed", s.missed);

    const metaEl = document.getElementById("meta");
    if (metaEl) {
      metaEl.textContent = `Generated (UTC): ${
        data?.meta?.generated_at ? formatUtcIso(data.meta.generated_at) : "Not available"
      }`;
    }
  } catch (e) {
    // If fetch fails, show the failure clearly under the headers (not blank space)
    ["breaking","developing","nothingburger","world","politics","markets","tech","weird","missed"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = `<div class="empty">Couldn’t load headlines.json.</div>`;
    });

    const metaEl = document.getElementById("meta");
    if (metaEl) metaEl.textContent = "Generated (UTC): Not available";
  }
}

init();
