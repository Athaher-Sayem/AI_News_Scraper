import { h, icon, replace, renderIf, $, debounce, fmtNum, rowChip, ROW_STATUS } from "../dom.js";
import { api } from "../api.js";
import { pageHead, banner, emptyState, errorState, pager, field, setTitle, openDrawer, closeDrawer, isDrawerOpen, tree, button } from "../ui.js";

const PAGE_SIZE = 20;

export function mount(ctx) {
  setTitle("Review");
  const state = { status: "", source: "", q: "", page: 1, data: null, error: null, open: null, loading: true };
  const readQuery = (query) => {
    state.status = query.get("status") || ""; state.source = query.get("source") || ""; state.q = query.get("q") || ""; state.page = Math.max(1, Number(query.get("page")) || 1);
  };
  readQuery(ctx.route.query);

  const chips = h("div", { class: "row", role: "group", "aria-label": "Filter by result status" });
  const status = h("select", { id: "rv-status", class: "select" });
  const source = h("select", { id: "rv-source", class: "select" });
  const search = h("input", { id: "rv-q", class: "input", type: "search", placeholder: "Search titles", autocomplete: "off", value: state.q });
  const results = h("div", { "aria-live": "polite" });
  const toolbar = h("div", { class: "toolbar" },
    h("div", { class: "field" }, h("label", { class: "label", for: "rv-q" }, "Search"), h("div", { class: "search" }, icon("search"), search)),
    field("Status", status, { id: "rv-status" }), field("Source", source, { id: "rv-source" }),
    button({ label: "Clear", variant: "ghost", onclick: () => { state.status = state.source = state.q = ""; state.page = 1; search.value = ""; pushQuery(); } }));
  replace(ctx.main, pageHead("Review", "Inspect what the model produced: generated article, extracted facts and the verifier’s decision."), h("div", { class: "stack" }, chips, toolbar, results));

  const pushQuery = (openRow = state.open, replace = true) => ctx.go(ctx.hashFor("review", openRow != null ? [String(openRow)] : [], { status: state.status, source: state.source, q: state.q, page: state.page > 1 ? state.page : "" }), { replace });

  function paintFilters() {
    const o = ctx.store.overview;
    if (!o) return;
    renderIf(status, Object.keys(o.by_status), () => [h("option", { value: "" }, "All statuses"), Object.keys(ROW_STATUS).map((k) => h("option", { value: k }, ROW_STATUS[k].label))]);
    renderIf(source, o.sources.map((s) => s.name), () => [h("option", { value: "" }, "All sources"), o.sources.map((s) => h("option", { value: s.name }, s.name))]);
    status.value = state.status; source.value = state.source;
    renderIf(chips, [o.by_status, state.status], () => {
      const total = Object.values(o.by_status).reduce((a, b) => a + b, 0);
      const make = (key, label, count) => h("button", { type: "button", class: `chip ${state.status === key ? "accent" : ""}`, "aria-pressed": state.status === key ? "true" : "false", onclick: () => { state.status = key; state.page = 1; pushQuery(); } },
        `${label} · ${fmtNum(count)}`);
      return [make("", "All", total), Object.entries(o.by_status).filter(([k]) => k).sort((a, b) => b[1] - a[1]).map(([k, n]) => make(k, ROW_STATUS[k]?.label || k, n))];
    });
  }

  let controller = null;
  async function load() {
    controller?.abort(); controller = new AbortController();
    state.loading = true;
    try {
      state.data = await api("/api/v1/processed/", { signal: controller.signal, params: { status: state.status, source: state.source, q: state.q, page: state.page, page_size: PAGE_SIZE } });
      state.error = null;
    } catch (error) { if (error.name === "AbortError") return; state.error = error; }
    state.loading = false;
    paint();
    if (state.open != null && !isDrawerOpen()) showRow(state.open);
  }
  function paint() {
    paintFilters();
    renderIf(results, state.error ? `e:${state.error.message}` : state.data && [state.data.meta, state.data.items.map((r) => [r.row, r.status])], () => {
      if (state.error) return errorState(state.error, load);
      if (!state.data) return h("div", { class: "skel", "data-h": "120" });
      const { items, meta } = state.data;
      if (!items.length) return h("div", { class: "card" }, emptyState({ iconName: "review", title: meta.total === 0 && !state.status && !state.q && !state.source ? "No results yet" : "No results match these filters",
        text: meta.total === 0 && !state.status && !state.q && !state.source ? "Processed articles appear here after a pipeline run." : "Try clearing a filter or searching for a different title." }));
      return [h("div", { class: "table-wrap" }, h("table", { class: "table stack-narrow" },
        h("caption", { class: "sr-only" }, "Processed articles"),
        h("thead", null, h("tr", null, ["#", "Status", "Title", "Source", "Category"].map((t) => h("th", { scope: "col" }, t)))),
        h("tbody", null, items.map((row) => h("tr", null,
          h("td", { "data-label": "Row", class: "num faint" }, String(row.row)),
          h("td", { "data-label": "Status" }, rowChip(row.status)),
          h("td", { class: "cell-main cell-title" }, h("button", { class: "row-btn", type: "button", onclick: () => open(row.row), "aria-label": `Open ${row.title}` }, h("span", { class: "cell-clip" }, row.title || "(untitled)"))),
          h("td", { "data-label": "Source" }, row.source || "—"),
          h("td", { "data-label": "Category" }, row.category || "—")))))), pager(meta, (p) => { state.page = p; pushQuery(); window.scrollTo({ top: 0 }); })];
    });
  }

  function open(row) { pushQuery(row, false); }
  async function showRow(row) {
    const items = state.data?.items || [];
    const index = items.findIndex((r) => r.row === row);
    const nav = [
      h("button", { class: "icon-btn", type: "button", "aria-label": "Previous article", disabled: index <= 0, onclick: () => open(items[index - 1].row) }, icon("chevron-left")),
      h("button", { class: "icon-btn", type: "button", "aria-label": "Next article", disabled: index < 0 || index >= items.length - 1, onclick: () => open(items[index + 1].row) }, icon("chevron-right"))];
    const body = h("div", { class: "stack" }, h("div", { class: "skel", "data-h": "120" }));
    openDrawer({ title: "Result " + row, subtitle: items[index]?.title || "", nav: index >= 0 ? nav : null, body, onClose: () => { state.open = null; pushQuery(); } });
    try {
      const detail = await api(`/api/v1/processed/${row}/`);
      if (state.open !== row) return;
      $("#drawer-title").textContent = detail.title || `Result ${row}`;
      $("#drawer-sub").textContent = [detail.source, detail.category].filter(Boolean).join(" · ");
      replace(body, detailView(detail));
    } catch (error) { replace(body, errorState(error, () => showRow(row))); }
  }

  function sync(route) {
    const before = JSON.stringify([state.status, state.source, state.q, state.page]);
    readQuery(route.query);
    const id = route.segs[0] != null ? Number(route.segs[0]) : null;
    const changed = before !== JSON.stringify([state.status, state.source, state.q, state.page]);
    if (search.value !== state.q) search.value = state.q;
    if (id == null || Number.isNaN(id)) { if (isDrawerOpen()) closeDrawer({ silent: true }); state.open = null; }
    else if (state.open !== id) { state.open = id; if (state.data) showRow(id); }
    if (changed || !state.data) load(); else paintFilters();
  }

  search.addEventListener("input", debounce(() => { state.q = search.value.trim(); state.page = 1; pushQuery(); }, 300));
  status.addEventListener("change", () => { state.status = status.value; state.page = 1; pushQuery(); });
  source.addEventListener("change", () => { state.source = source.value; state.page = 1; pushQuery(); });
  ctx.subscribe("overview", paintFilters);
  const id0 = ctx.route.segs[0] != null ? Number(ctx.route.segs[0]) : null;
  if (id0 != null && !Number.isNaN(id0)) state.open = id0;
  load();
  return { onRoute: sync, unmount() { controller?.abort(); if (isDrawerOpen()) closeDrawer({ silent: true }); }, reload: load };
}

function safeHref(url) { return /^https?:\/\//i.test(url || "") ? url : null; }

function detailView(d) {
  const tabs = [
    { id: "article", label: "Generated article", render: () => d.generated_article ? h("div", { class: "prose" }, d.generated_article) : h("p", { class: "muted" }, "No article was generated for this row.") },
    { id: "facts", label: "Facts", render: () => d.facts && typeof d.facts === "object" ? tree(d.facts) : d.facts ? h("pre", { class: "pre" }, String(d.facts)) : h("p", { class: "muted" }, "No facts were extracted.") },
    { id: "verification", label: "Verification", render: () => verification(d.verification) },
    { id: "source", label: "Source text", render: () => h("div", { class: "prose" }, d.content || "No source text.") },
  ];
  const panel = h("div", { class: "stack", role: "tabpanel", tabindex: "0", id: "rv-panel" });
  const list = h("div", { class: "tabs", role: "tablist", "aria-label": "Result sections" });
  const select = (id, focus) => {
    const tab = tabs.find((t) => t.id === id);
    [...list.children].forEach((b) => { const on = b.dataset.id === id; b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1; if (on && focus) b.focus(); });
    panel.setAttribute("aria-labelledby", `rv-tab-${id}`);
    replace(panel, tab.render());
  };
  tabs.forEach((t) => list.append(h("button", { class: "tab", role: "tab", type: "button", id: `rv-tab-${t.id}`, "aria-controls": "rv-panel", dataset: { id: t.id }, onclick: () => select(t.id) }, t.label)));
  list.addEventListener("keydown", (event) => {
    const keys = { ArrowRight: 1, ArrowLeft: -1 };
    if (!(event.key in keys)) return;
    const i = tabs.findIndex((t) => t.id === list.querySelector('[aria-selected="true"]').dataset.id);
    select(tabs[(i + keys[event.key] + tabs.length) % tabs.length].id, true);
    event.preventDefault();
  });
  select(d.generated_article ? "article" : "source");
  const link = safeHref(d.url);
  return [
    h("div", { class: "row between" }, rowChip(d.status), link && h("a", { class: "btn btn-secondary btn-sm", href: link, target: "_blank", rel: "noopener noreferrer" }, "Original article", icon("external"))),
    d.reason && banner(d.status === "APPROVED" ? "info" : d.status.endsWith("_FAILED") ? "bad" : "warn", d.status === "APPROVED" ? "info" : "alert", [h("strong", null, "Reason: "), d.reason]),
    h("div", { class: "meta-line" }, d.author && h("span", null, `By ${d.author}`), d.published_date && h("span", null, d.published_date), d.language && h("span", null, d.language.toUpperCase())),
    list, panel,
  ];
}

function verification(v) {
  if (v == null) return h("p", { class: "muted" }, "Verification did not run for this row.");
  if (typeof v !== "object") return h("pre", { class: "pre" }, String(v));
  const approved = v.approved === true;
  return [h("div", { class: "row" }, h("span", { class: `chip ${approved ? "ok" : "warn"}` }, icon(approved ? "check" : "alert"), approved ? "Approved by verifier" : "Not approved")), v.summary && h("p", null, v.summary), tree(Object.fromEntries(Object.entries(v).filter(([k]) => k !== "summary" && k !== "approved")))];
}
