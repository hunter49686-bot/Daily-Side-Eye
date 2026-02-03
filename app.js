const HEADLINES_URL = "headlines.json";

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
  const res = await fetch(HEADLINES_URL + cacheBust, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  if (!data?.sections) throw new Error("Invalid schema: missing sections");
  return data;
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

        const snarkText = (it.snark && typeof it.snark === "string") ? it.snark.trim() : "";
        const snarkLine = snarkText ? `<div class="source">${escapeHtml(snarkText)}</div>` : "";

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
  try {
    const data = await fetchHeadlines();
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
      metaEl.textContent = `Generated (UTC): ${gen}`;
    }
  } catch (e) {
    // If fetch fails, show empty (no cached old snark)
    [
      "breaking","developing","nothingburger",
      "world","politics","markets",
      "tech","weird","missed"
    ].forEach(id => renderSection(id, []));

    const metaEl = document.getElementById("meta");
    if (metaEl) metaEl.textContent = "Generated (UTC): Not available";
  }
}

init();
