const HEADLINES_URL = "headlines.json";

/* Military keyword detection (explicit, deterministic) */
const MILITARY_RE = /\b(
  military|war|drone|missile|army|navy|air force|troops|soldiers|
  strike|airstrike|bomb|bombing|rocket|defense|defence|weapon|
  attack|conflict|battle
)\b/i;

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function fetchHeadlines() {
  const res = await fetch(`${HEADLINES_URL}?v=${Date.now()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Fetch failed");
  return res.json();
}

function renderSection(containerId, items, { cap = null, checkMilitary = false } = {}) {
  const el = document.getElementById(containerId);
  if (!el) return;

  const list = Array.isArray(items) ? items : [];
  const use = cap ? list.slice(0, cap) : list;

  el.innerHTML = use.length
    ? use.map(it => {
        const title = escapeHtml(it.title);
        const source = escapeHtml(it.source || "");
        const url = it.url || "#";
        const snark = it.snark ? `<div class="source">${escapeHtml(it.snark)}</div>` : "";

        const isMilitary = checkMilitary && MILITARY_RE.test(it.title || "");
        const classes = `headline${isMilitary ? " military" : ""}`;

        return `
          <a class="${classes}" href="${url}" target="_blank" rel="noopener noreferrer">
            <div class="title">${title}</div>
            <div class="meta-row">
              <div class="source">${source}</div>
            </div>
            ${snark}
          </a>
        `;
      }).join("")
    : `<div class="empty">No items right now.</div>`;
}

function formatUtcIso(iso) {
  try { return new Date(iso).toUTCString(); } catch { return "Unknown"; }
}

async function init() {
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
  } catch {
    ["breaking","developing","nothingburger","world","politics","markets","tech","weird","missed"]
      .forEach(id => renderSection(id, []));
  }
}

init();
