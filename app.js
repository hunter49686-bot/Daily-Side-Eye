const HEADLINES_URL = "headlines.json";
const LKG_KEY = "dse_last_known_good_headlines_v1";

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
      data: { meta: { generated_at: null, version: 1 }, sections: { breaking: [], policy: [], money: [], tech: [], weird: [] } },
      fromCache: true,
      cacheAgeMs: null
    };
  }
}

function renderSection(containerId, items, { cap = null } = {}) {
  const el = document.getElementById(containerId);
  if (!el) return;

  const safeItems = Array.isArray(items) ? items : [];
  const useItems = cap ? safeItems.slice(0, cap) : safeItems;

  el.innerHTML = useItems.length
    ? useItems.map(it => `
      <a class="headline" href="${it.url}" target="_blank" rel="noopener noreferrer">
        <div class="title">${escapeHtml(it.title)}</div>
        <div class="source">${escapeHtml(it.source || "")}</div>
      </a>
    `).join("")
    : `<div class="empty">No items right now.</div>`;
}

function formatUtcIso(iso) {
  try {
    const d = new Date(iso);
    return d.toUTCString();
  } catch {
    return "Unknown";
  }
}

async function init() {
  const { data, fromCache, cacheAgeMs } = await fetchHeadlines();
  const sections = data.sections || {};

  // TOP REMOVED: no rendering for "top"
  renderSection("breaking", sections.breaking, { cap: 7 });
  renderSection("policy", sections.policy);
  renderSection("money", sections.money);
  renderSection("tech", sections.tech);
  renderSection("weird", sections.weird);

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
