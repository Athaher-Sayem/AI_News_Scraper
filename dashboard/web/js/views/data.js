import { h, icon, replace, renderIf, debounce, fmtNum, fmtPct, fmtDate, fmtRel, fmtBytes, chip } from "../dom.js";
import { api, download } from "../api.js";
import { pageHead, banner, emptyState, errorState, pager, field, setTitle, openDrawer, closeDrawer, isDrawerOpen, toast, button } from "../ui.js";

const TABS = [["sources", "Sources"], ["articles", "Collected articles"], ["files", "Data files"], ["system", "System"]];
const ROLE = { raw: { label: "Raw scrape", tone: "info", icon: "data" }, unique: { label: "Deduplicated", tone: "accent", icon: "pipeline" }, processed: { label: "Results", tone: "ok", icon: "review" }, other: { label: "Other", tone: "plain", icon: "file" } };

export function mount(ctx) {
  setTitle("Data");
  const state = { tab: TABS.some(([id]) => id === ctx.route.segs[0]) ? ctx.route.segs[0] : "sources", view: null };
  const tabList = h("div", { class: "tabs", role: "tablist", "aria-label": "Data sections" });
  const panel = h("div", { role: "tabpanel", id: "data-panel", tabindex: "0" });
  replace(ctx.main, pageHead("Data", "Publishers, collected articles, files on disk, and system configuration."), tabList, panel);

  TABS.forEach(([id, label]) => tabList.append(h("a", { class: "tab", role: "tab", id: `tab-${id}`, href: ctx.hashFor("data", [id]), "aria-controls": "data-panel" }, label)));
  tabList.addEventListener("keydown", (event) => {
    if (!["ArrowRight", "ArrowLeft"].includes(event.key)) return;
    const i = TABS.findIndex(([id]) => id === state.tab);
    const next = TABS[(i + (event.key === "ArrowRight" ? 1 : -1) + TABS.length) % TABS.length][0];
    ctx.go(ctx.hashFor("data", [next])); document.getElementById(`tab-${next}`)?.focus(); event.preventDefault();
  });

  function show() {
    TABS.forEach(([id]) => { const t = document.getElementById(`tab-${id}`); t.setAttribute("aria-selected", String(id === state.tab)); t.tabIndex = id === state.tab ? 0 : -1; });
    panel.setAttribute("aria-labelledby", `tab-${state.tab}`);
    state.view?.unmount?.();
    if (isDrawerOpen()) closeDrawer({ silent: true });
    replace(panel);
    state.view = { sources, articles, files, system }[state.tab](ctx, panel);
  }
  show();
  return {
    onRoute(route) {
      const next = TABS.some(([id]) => id === route.segs[0]) ? route.segs[0] : "sources";
      if (next !== state.tab) { state.tab = next; show(); } else state.view?.onRoute?.(route);
    },
    unmount() { state.view?.unmount?.(); if (isDrawerOpen()) closeDrawer({ silent: true }); },
    reload() { state.view?.reload?.(); },
  };
}

// ---- sources ---------------------------------------------------------------------------
function sources(ctx, root) {
  const state = { key: "articles", dir: "desc" };
  const holder = h("div");
  root.append(holder);
  const cols = [["name", "Source", false], ["articles", "Articles", true], ["categories", "Categories", true], ["latest_scraped", "Last scrape", false], ["processed", "Processed", true], ["approved", "Approved", true], ["rate", "Approval", true]];
  const value = (row, key) => (key === "rate" ? (row.processed ? row.approved / row.processed : -1) : key === "latest_scraped" ? row.latest_scraped || "" : row[key]);

  function paint() {
    const o = ctx.store.overview;
    if (!o) { replace(holder, h("div", { class: "skel", "data-h": "120" })); return; }
    renderIf(holder, [o.sources, state.key, state.dir], () => {
      const rows = [...o.sources].sort((a, b) => {
        const x = value(a, state.key), y = value(b, state.key);
        const cmp = typeof x === "string" ? x.localeCompare(y) : x - y;
        return state.dir === "asc" ? cmp : -cmp;
      });
      return h("div", { class: "table-wrap" }, h("table", { class: "table stack-narrow" },
        h("caption", { class: "sr-only" }, "Configured publishers with collection and processing counts"),
        h("thead", null, h("tr", null, cols.map(([key, label, numeric]) =>
          h("th", { scope: "col", class: numeric ? "r" : "", "aria-sort": state.key === key ? (state.dir === "asc" ? "ascending" : "descending") : "none" },
            h("button", { class: "th-sort", type: "button", onclick: () => { state.dir = state.key === key && state.dir === "desc" ? "asc" : "desc"; state.key = key; paint(); } }, label, h("span", { class: "arrow", "aria-hidden": "true" }, state.key === key ? (state.dir === "asc" ? "▲" : "▼") : "↕"))))), h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Actions"))),
        h("tbody", null, rows.map((r) => h("tr", null,
          h("td", { class: "cell-main" }, h("strong", null, r.name), !r.configured && h("span", { class: "chip plain" }, "not configured")),
          h("td", { class: "r num", "data-label": "Articles" }, fmtNum(r.articles)),
          h("td", { class: "r num", "data-label": "Categories" }, fmtNum(r.categories)),
          h("td", { "data-label": "Last scrape" }, r.latest_scraped ? h("span", { title: fmtDate(r.latest_scraped) }, fmtRel(r.latest_scraped)) : "never"),
          h("td", { class: "r num", "data-label": "Processed" }, fmtNum(r.processed)),
          h("td", { class: "r num", "data-label": "Approved" }, fmtNum(r.approved)),
          h("td", { class: "r num", "data-label": "Approval" }, fmtPct(r.approved, r.processed)),
          h("td", null, r.configured && h("a", { class: "btn btn-ghost btn-sm", href: ctx.hashFor("pipeline", [], { mode: "full", sources: r.name }), "aria-label": `Scrape ${r.name} with a new run` }, icon("play"), "Scrape"))))))));
    });
  }
  ctx.subscribe("overview", paint);
  paint();
  return {};
}

// ---- collected articles --------------------------------------------------------------------
function articles(ctx, root) {
  const state = { source: "", category: "", q: "", page: 1, data: null, error: null, categories: [] };
  const results = h("div", { "aria-live": "polite" });
  const search = h("input", { id: "ar-q", class: "input", type: "search", placeholder: "Search title or text", autocomplete: "off" });
  const source = h("select", { id: "ar-source", class: "select" });
  const category = h("select", { id: "ar-category", class: "select" });
  replace(root, h("div", { class: "toolbar" },
    h("div", { class: "field" }, h("label", { class: "label", for: "ar-q" }, "Search"), h("div", { class: "search" }, icon("search"), search)),
    field("Source", source, { id: "ar-source" }), field("Category", category, { id: "ar-category" }),
    button({ label: "Clear", variant: "ghost", onclick: () => { state.source = state.category = state.q = ""; state.page = 1; search.value = ""; source.value = category.value = ""; load(); } })), results);

  let controller = null;
  async function load() {
    controller?.abort(); controller = new AbortController();
    try {
      state.data = await api("/api/v1/articles/", { signal: controller.signal, params: { source: state.source, category: state.category, q: state.q, page: state.page, page_size: 20 } });
      state.error = null;
    } catch (error) { if (error.name === "AbortError") return; state.error = error; }
    paint();
  }
  async function loadFilters() {
    try { state.categories = (await api("/api/v1/categories/")).items; } catch { /* filters stay empty */ }
    const names = ctx.store.overview?.sources.map((s) => s.name) || [];
    replace(source, h("option", { value: "" }, "All sources"), names.map((n) => h("option", { value: n }, n)));
    replace(category, h("option", { value: "" }, "All categories"), state.categories.map((c) => h("option", { value: c.category }, `${c.category} (${fmtNum(c.count)})`)));
    source.value = state.source; category.value = state.category;
  }
  function paint() {
    renderIf(results, state.error ? `e:${state.error.message}` : state.data && [state.data.meta, state.data.items.map((a) => a.id)], () => {
      if (state.error) return errorState(state.error, load);
      if (!state.data) return h("div", { class: "skel", "data-h": "120" });
      const { items, meta } = state.data;
      if (!items.length) return h("div", { class: "card" }, emptyState({ iconName: "data", title: "No articles found", text: "Collected articles appear here after a scrape. Adjust the filters if you expected results." }));
      return [h("div", { class: "table-wrap" }, h("table", { class: "table stack-narrow" },
        h("caption", { class: "sr-only" }, "Collected articles, newest first"),
        h("thead", null, h("tr", null, ["Title", "Source", "Category", "Language", "Scraped"].map((t) => h("th", { scope: "col" }, t)))),
        h("tbody", null, items.map((a) => h("tr", null,
          h("td", { class: "cell-main cell-title" }, h("button", { class: "row-btn", type: "button", onclick: () => view(a), "aria-label": `Open ${a.title}` }, h("span", { class: "cell-clip" }, a.title))),
          h("td", { "data-label": "Source" }, a.source), h("td", { "data-label": "Category" }, a.category || "—"), h("td", { "data-label": "Language" }, (a.language || "—").toUpperCase()),
          h("td", { "data-label": "Scraped" }, h("span", { title: fmtDate(a.scraped_date) }, fmtRel(a.scraped_date)))))))), pager(meta, (p) => { state.page = p; load(); })];
    });
  }
  function view(a) {
    const link = /^https?:\/\//i.test(a.url) ? a.url : null;
    const text = a.content || "";
    openDrawer({ title: a.title, subtitle: [a.source, a.category].filter(Boolean).join(" · "), body: h("div", { class: "stack" },
      h("div", { class: "row between" }, h("span", { class: "muted" }, `Scraped ${fmtDate(a.scraped_date)}`), link && h("a", { class: "btn btn-secondary btn-sm", href: link, target: "_blank", rel: "noopener noreferrer" }, "Original article", icon("external"))),
      h("div", { class: "meta-line" }, a.author && h("span", null, `By ${a.author}`), a.published_date && h("span", null, a.published_date)),
      text ? h("div", { class: "prose" }, text.length > 8000 ? `${text.slice(0, 8000)}…` : text) : h("p", { class: "muted" }, "No body text was captured.")) });
  }
  search.addEventListener("input", debounce(() => { state.q = search.value.trim(); state.page = 1; load(); }, 300));
  source.addEventListener("change", () => { state.source = source.value; state.page = 1; load(); });
  category.addEventListener("change", () => { state.category = category.value; state.page = 1; load(); });
  loadFilters(); load();
  return { unmount() { controller?.abort(); }, reload() { load(); loadFilters(); } };
}

// ---- files ----------------------------------------------------------------------------------------
function files(ctx, root) {
  const holder = h("div");
  replace(root, holder);
  function paint() {
    const o = ctx.store.overview;
    if (!o) { replace(holder, h("div", { class: "skel", "data-h": "120" })); return; }
    renderIf(holder, o.files, () => {
      if (!o.files.length) return h("div", { class: "card" }, emptyState({ iconName: "file", title: "No CSV files in data/", text: "Files appear here after the first scrape." }));
      return [h("p", { class: "muted section-note" }, "CSV files inside the project’s data/ directory. Pipeline runs read and write only here."),
        h("div", { class: "table-wrap" }, h("table", { class: "table stack-narrow" },
          h("caption", { class: "sr-only" }, "Data files"),
          h("thead", null, h("tr", null, ["File", "Role", "Rows", "Size", "Modified", ""].map((t, i) => h("th", { scope: "col", class: i === 2 || i === 3 ? "r" : "" }, t || h("span", { class: "sr-only" }, "Download"))))),
          h("tbody", null, o.files.map((f) => h("tr", null,
            h("td", { class: "cell-main" }, h("span", { class: "mono" }, f.name)),
            h("td", { "data-label": "Role" }, chip(ROLE[f.role], f.role)),
            h("td", { class: "r num", "data-label": "Rows" }, fmtNum(f.rows)),
            h("td", { class: "r num", "data-label": "Size" }, fmtBytes(f.size)),
            h("td", { "data-label": "Modified" }, h("span", { title: fmtDate(f.modified) }, fmtRel(f.modified))),
            h("td", null, h("button", { class: "btn btn-secondary btn-sm", type: "button", "aria-label": `Download ${f.name}`, onclick: async (event) => {
              const btn = event.currentTarget; btn.disabled = true;
              try { await download(`/dashboard/api/files/${f.name.split("/").map(encodeURIComponent).join("/")}/download/`, f.name.split("/").pop()); } catch (e) { toast(e.message, "bad"); }
              btn.disabled = false; } }, icon("download"), "Download"))))))))];
    });
  }
  ctx.subscribe("overview", paint);
  paint();
  return {};
}

// ---- system ----------------------------------------------------------------------------------------
function system(ctx, root) {
  const holder = h("div", { class: "stack" });
  replace(root, holder);
  function kv(rows) { return h("dl", { class: "kv" }, rows.map(([k, v, mono]) => [h("dt", null, k), h("dd", { class: mono ? "mono" : "" }, v == null || v === "" ? "—" : String(v))])); }
  function paint() {
    const o = ctx.store.overview, health = ctx.store.health;
    if (!o) { replace(holder, h("div", { class: "skel", "data-h": "120" })); return; }
    renderIf(holder, [o.config, health], () => {
      const c = o.config;
      return [banner("info", "info", "Read-only snapshot. Change these in the .env file (or environment variables) and restart the server."),
        h("div", { class: "grid split-even" },
          h("section", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "Generation"), h("p", null, "Local language model used for facts, articles and verification"))),
            kv([["Service", health ? (health.generation.available ? "Reachable" : "Offline") : "Checking…"], ["Model", c.generation.model, true], ["Model installed", health ? (health.generation.model_installed ? "Yes" : "No") : "…"], ["Endpoint", c.generation.url, true], ["Temperature", c.generation.temperature], ["Max tokens", fmtNum(c.generation.max_tokens)]])),
          h("section", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "Pipeline"), h("p", null, "Paths and thresholds"))),
            kv([["Dedup threshold", c.deduplication.threshold], ["Raw CSV", c.paths.raw, true], ["Unique CSV", c.paths.unique, true], ["Results CSV", c.paths.processed, true], ["Sources", c.sources.join(", ")], ["Run history", `Last ${c.job_history_limit} runs, in memory`]])),
          h("section", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "Server"), h("p", null, "Runtime settings"))),
            kv([["Debug mode", c.server.debug ? "On" : "Off"], ["API key required", c.server.api_key_required ? "Yes" : "No"], ["Database", c.server.database], ["View retention", `${c.server.view_retention_days} days`]])),
          h("section", { class: "card" }, h("div", { class: "card-head" }, h("div", null, h("h2", null, "Shortcuts"), h("p", null, "Related tools"))),
            h("div", { class: "stack-sm" },
              h("a", { class: "btn btn-secondary", href: "/api/v1/docs/", target: "_blank", rel: "noopener" }, "API documentation", icon("external")),
              h("a", { class: "btn btn-secondary", href: "/admin/", target: "_blank", rel: "noopener" }, "Django admin", icon("external")),
              h("a", { class: "btn btn-secondary", href: "/collected/", target: "_blank", rel: "noopener" }, "Collected pages", icon("external")))))];
    });
  }
  ctx.subscribe("overview", paint); ctx.subscribe("health", paint);
  paint();
  return {};
}
