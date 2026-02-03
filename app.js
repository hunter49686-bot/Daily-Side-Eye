const HEADLINES_URL = "headlines.json";
const LKG_KEY = "dse_last_known_good_v6";

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function fetchHeadlines() {
  const cacheBust = `?v=${Date.now()}`;
  try {
    const res = await fetch(HEADLINES_URL + cacheBust, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!data?.sections) throw new Error("Invalid schema: missing sections");
    localStorage.setItem(LKG_KEY, JSON.stringify({ savedAt: Date.now(), data }));
    return { data, fromCache: false, cacheAgeMs: 0 };
  } catch (err) {
    const lkg = localStorage.getItem(LKG_KEY);
    if (lkg) {
      try {
        const parsed = JSON.parse(lkg);
        const age = Date.now() - (parsed.savedAt || Date.now());
        return { data: parsed.data, fromCache: true, cacheAgeMs: age };
      } catch (_) {}
    }
    return {
      data: {
        meta: { generated_at: null, version: 6 },
        sections: {
          breaking: [], developing: [], nothingburger: [],
          world: [], politics: [], markets: [],
          tech: [], weird: [], missed: []
        }
      },
      fromCache: true,
      cacheAgeMs: null
    };
  }
}

function renderSection(containerId, items, { cap = null } = {}) {
  const el = document.getElementById(containerId);
  if (!el) return;

  const safe = Array.isArray(items) ? items : [];
  const use = cap ? safe.slice(0, cap) : safe;

  el.innerHTML = use.length
    ? use.map(it => {
        const title = escapeHtml(it.title);
        const source = escapeHtml(it.source || "");
        const url = it.url || "#";

        const snarkLine = (it.snark && typeof it.snark === "string")
          ? `<div class="source">${escapeHtml(it.snark)}</div>`
          : "";

        return `
          <a class="headline" href="${url}" target="_blank" rel="noopener noreferrer">
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

async function init() {
  const { data, fromCache, cacheAgeMs } = await fetchHeadlines();
  const s = data.sections || {};

  renderSection("breaking", s.breaking, { cap: 7 });
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
    const gen = data?.meta?.generated_at ? formatUtcIso(data.meta.generated_at) : "Not available";
    const cacheNote = fromCache
      ? (cacheAgeMs === null ? " (fallback)" : ` (cached fallback, age ~${Math.round(cacheAgeMs / 60000)} min)`)
      : "";
    metaEl.textContent = `Generated (UTC): ${gen}${cacheNote}`;
  }
}

init();
