import { h, icon, replace, renderIf, fmtNum, fmtPct, fmtRel, fmtDate, fmtDur, ROW_STATUS, rowChip, runChip, modeLabel, limitLabel } from "../dom.js";
import { pageHead, button, banner, emptyState, errorState, hbars, columns, stackBar, setTitle } from "../ui.js";

const STAGE_TONE = { approved: "ok" };

export function mount(ctx) {
  setTitle("Overview");
  const refresh = button({ label: "Refresh", iconName: "refresh", onclick: () => ctx.refreshOverview() });
  const start = h("a", { class: "btn btn-primary", href: ctx.hashFor("pipeline") }, icon("play"), "Start a run");
  const els = {
    error: h("div"), health: h("section", { "aria-label": "Service health" }), active: h("div"), kpis: h("section", { "aria-label": "Key numbers" }),
    funnel: h("div", { class: "card" }), status: h("div", { class: "card" }), timeline: h("div", { class: "card" }), sources: h("div", { class: "card" }), latest: h("div"),
  };
  replace(ctx.main,
    pageHead("Overview", "Health, throughput and output quality across the whole pipeline.", [refresh, start]),
    h("div", { class: "stack" },
      els.error, els.health, els.active, els.kpis,
      h("div", { class: "grid split-even" }, els.funnel, els.status),
      h("div", { class: "grid split-even" }, els.timeline, els.sources),
      els.latest));

  const paint = () => {
    const { overview, health, error } = ctx.store;
    renderIf(els.error, error ? `${error.status}:${error.message}` : "", () => (error ? errorState(error, () => ctx.refreshOverview()) : null));
    if (!overview) { skeletons(els); return; }
    renderIf(els.health, { h: health, k: overview.config.server.api_key_required, a: !!overview.active_run, l: overview.latest_run?.status, n: overview.totals.articles }, () => healthStrip(overview, health));
    renderIf(els.active, overview.active_run && [overview.active_run.id, overview.active_run.progress.stages.map((s) => s.state + s.passed), overview.active_run.progress.row], () => (overview.active_run ? activeCard(ctx, overview.active_run) : null));
    renderIf(els.kpis, overview.totals, () => kpiGrid(overview));
    renderIf(els.funnel, overview.funnel, () => funnelCard(overview));
    renderIf(els.status, overview.by_status, () => statusCard(overview));
    renderIf(els.timeline, overview.timeline, () => timelineCard(overview));
    renderIf(els.sources, overview.sources, () => sourcesCard(overview));
    renderIf(els.latest, overview.latest_run && [overview.latest_run.id, overview.latest_run.status], () => latestCard(ctx, overview.latest_run));
  };
  ctx.subscribe("overview", paint);
  ctx.subscribe("health", paint);
  paint();
  return {};
}

function skeletons(els) {
  for (const key of ["health", "kpis", "funnel", "status", "timeline", "sources"]) {
    if (els[key].dataset.sig) continue;
    els[key].append(h("div", { class: "skel", "data-h": "120", "aria-hidden": "true" }));
  }
}

function healthStrip(overview, health) {
  const db = health?.database?.available;
  const gen = health?.generation;
  const items = [];
  items.push(item(db === undefined ? "info" : db ? "ok" : "bad", "data", "Database", db === undefined ? "Checking…" : db ? `${fmtNum(overview.totals.articles)} articles stored` : "Unreachable"));
  if (!gen) items.push(item("info", "server", "Generation service", "Checking…"));
  else if (!gen.available) items.push(item("bad", "server", "Generation offline", `Start it with “ollama serve” (${gen.model})`));
  else if (!gen.model_installed) items.push(item("warn", "server", "Model missing", `Run “ollama pull ${gen.model}”`));
  else items.push(item("ok", "server", "Generation ready", `Model ${gen.model}`));
  items.push(overview.config.server.api_key_required
    ? item("ok", "lock", "API key required", "Data endpoints are protected")
    : item("warn", "lock", "No API key set", "Open access; fine for local use"));
  const latest = overview.latest_run;
  items.push(overview.active_run ? item("ok", "bolt", "Run in progress", "Live progress on the Pipeline page")
    : item("info", "bolt", "Pipeline idle", latest ? `Last run ${latest.status} ${fmtRel(latest.finished_at || latest.created_at)}` : "No runs since the server started"));
  return h("div", { class: "health" }, items);
}
function item(tone, iconName, title, text) {
  const label = { ok: "OK", warn: "Attention", bad: "Problem", info: "Info" }[tone];
  return h("div", { class: `health-item ${tone}` }, h("span", { class: "dot" }, icon(iconName)),
    h("div", { class: "t" }, h("strong", null, title), h("span", null, text), h("span", { class: "sr-only" }, `Status: ${label}`)));
}

function activeCard(ctx, run) {
  const rows = run.progress.row;
  const done = rows.stage ? rows.index - 1 : rows.index;
  const running = run.progress.stages.find((s) => s.state === "running");
  return h("section", { class: "card", "aria-label": "Active run" },
    h("div", { class: "card-head" },
      h("div", null, h("h2", null, "Run in progress"), h("p", null, `${modeLabel(run.request, run.sources)} · ${limitLabel(run.request.limit)}`)),
      h("a", { class: "btn btn-secondary btn-sm", href: ctx.hashFor("pipeline") }, "Open live view", icon("chevron-right"))),
    h("div", { class: "progress-line" },
      rows.total ? h("progress", { max: rows.total, value: Math.max(0, done), "aria-label": "Articles processed" }) : h("progress", { "aria-label": "Collecting" }),
      h("span", { class: "num nowrap" }, rows.total ? `${done}/${rows.total}` : "…")),
    h("p", { class: "muted" }, running ? `Now: ${running.label}${rows.title ? ` · ${rows.title}` : ""}` : "Starting…"));
}

function kpi(label, value, foot, iconName) {
  return h("div", { class: "card kpi" }, h("span", { class: "kpi-label" }, icon(iconName, "icon-sm"), label), h("span", { class: "kpi-value" }, value), h("span", { class: "kpi-foot" }, foot));
}
function kpiGrid(overview) {
  const t = overview.totals;
  const reviewed = t.processed;
  return h("div", { class: "grid cols-4" },
    kpi("Collected articles", fmtNum(t.articles), t.raw_rows != null ? `${fmtNum(t.raw_rows)} rows in raw CSV` : "In the database", "data"),
    kpi("Ready to process", fmtNum(t.unique_rows), "Unique after deduplication", "pipeline"),
    kpi("Processed", fmtNum(reviewed), reviewed ? `${fmtNum(reviewed - t.approved)} not approved` : "No results yet", "review"),
    kpi("Approval rate", reviewed ? fmtPct(t.approved, reviewed) : "—", `${fmtNum(t.approved)} approved · last scrape ${fmtRel(t.latest_scraped)}`, "check"));
}

function funnelCard(overview) {
  const rows = overview.funnel;
  const total = rows[0].count;
  const head = h("div", { class: "card-head" }, h("div", null, h("h2", null, "Quality funnel"), h("p", null, "How many processed articles survive each stage")));
  if (!total) return [head, emptyState({ iconName: "pipeline", title: "No processed articles yet", text: "Start a run to see how articles move through content checks, fact extraction, generation and verification." })];
  const data = rows.map((r) => ({ name: r.label, value: r.count, note: ` ${fmtPct(r.count, total)}`, tone: STAGE_TONE[r.key] || "" }));
  return [head, hbars(data, { max: total, label: "Articles remaining after each stage" })];
}

function statusCard(overview) {
  const entries = Object.entries(overview.by_status).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, n]) => s + n, 0);
  const head = h("div", { class: "card-head" }, h("div", null, h("h2", null, "Result breakdown"), h("p", null, "Final status of every processed article")));
  if (!total) return [head, emptyState({ iconName: "review", title: "Nothing to break down", text: "Results appear here after the first run." })];
  const tone = (status) => ROW_STATUS[status]?.tone || "";
  return [head,
    stackBar(entries.map(([status, value]) => ({ value, tone: tone(status) })), "Share of each result status"),
    h("ul", { class: "stack-sm", role: "list" }, entries.map(([status, count]) =>
      h("li", { class: "row between" }, h("a", { href: `#/review?status=${encodeURIComponent(status)}`, class: "row" }, rowChip(status)), h("span", { class: "num" }, `${fmtNum(count)} · ${fmtPct(count, total)}`))))];
}

function timelineCard(overview) {
  const series = overview.timeline;
  const total = series.reduce((s, p) => s + p.count, 0);
  const head = h("div", { class: "card-head" }, h("div", null, h("h2", null, "Collection, last 14 days"), h("p", null, `${fmtNum(total)} articles scraped`)));
  if (!total) return [head, emptyState({ iconName: "data", title: "No articles collected in this window", text: "Run the full pipeline to scrape the configured sources." })];
  return [head, columns(series, { label: "Articles scraped per day" })];
}

function sourcesCard(overview) {
  const head = h("div", { class: "card-head" }, h("div", null, h("h2", null, "Articles by source"), h("p", null, "Everything stored in the database")),
    h("a", { class: "btn btn-ghost btn-sm", href: "#/data/sources" }, "Details", icon("chevron-right")));
  const total = overview.sources.reduce((s, r) => s + r.articles, 0);
  if (!total) return [head, emptyState({ iconName: "data", title: "Database is empty", text: "Collected articles are listed here per publisher." })];
  return [head, hbars(overview.sources.map((s) => ({ name: s.name, value: s.articles, note: ` ${fmtPct(s.articles, total)}` })), { label: "Articles per source" })];
}

function latestCard(ctx, run) {
  if (!run) return null;
  const s = run.summary;
  return h("section", { class: "card", "aria-label": "Latest run" },
    h("div", { class: "card-head" }, h("div", null, h("h2", null, "Latest run"), h("p", null, `${modeLabel(run.request, run.sources)} · ${limitLabel(run.request.limit)} · started ${fmtDate(run.started_at || run.created_at)}`)),
      h("div", { class: "row" }, runChip(run.status), h("a", { class: "btn btn-secondary btn-sm", href: ctx.hashFor("runs", [run.id]) }, "Details", icon("chevron-right")))),
    run.error && banner(run.status === "failed" ? "bad" : "warn", "alert", run.error),
    s && h("p", { class: "muted" }, `${fmtNum(s.processed)} processed · ${fmtNum(s.approved)} approved · ${fmtNum(s.rejected)} rejected · ${fmtNum(s.failed)} failed · took ${fmtDur(run.duration_seconds)}`));
}
