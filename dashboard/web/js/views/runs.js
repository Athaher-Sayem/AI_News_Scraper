import { h, icon, replace, renderIf, $, fmtNum, fmtDate, fmtRel, fmtClock, fmtDur, runChip, rowChip, modeLabel, limitLabel } from "../dom.js";
import { api } from "../api.js";
import { pageHead, banner, emptyState, errorState, hbars, setTitle, openDrawer, closeDrawer, isDrawerOpen, drawerBody, toast, confirmDialog, button } from "../ui.js";

export function mount(ctx) {
  setTitle("Runs");
  const state = { items: null, error: null, open: null, drawerPoll: null, drawerAfter: 0 };
  const listEl = h("div");
  const noteEl = banner("info", "info", ["Run history lives in server memory: the newest 20 runs are kept and the list resets when the server restarts. Results CSV files are not affected."]);
  replace(ctx.main, pageHead("Runs", "Every pipeline run started from this console, the API, or the web app.", button({ label: "Refresh", iconName: "refresh", onclick: () => load() })), h("div", { class: "stack" }, noteEl, listEl));

  async function load() {
    try { state.items = (await api("/dashboard/api/runs/")).items; state.error = null; } catch (error) { state.error = error; }
    paint();
  }
  function paint() {
    renderIf(listEl, state.error ? `e:${state.error.message}` : state.items && state.items.map((r) => [r.id, r.status, r.progress.row.index, r.finished_at]), () => {
      if (state.error) return errorState(state.error, load);
      if (!state.items) return h("div", { class: "skel", "data-h": "120" });
      if (!state.items.length) return h("div", { class: "card" }, emptyState({ iconName: "runs", title: "No runs yet", text: "Start one from the Pipeline page and it will be listed here.", action: h("a", { class: "btn btn-primary", href: ctx.hashFor("pipeline") }, icon("play"), "Start a run") }));
      return table(ctx, state.items);
    });
  }
  const poll = ctx.poll(load, 4000);
  sync(ctx.route);

  function sync(route) {
    const id = route.segs[0];
    if (!id) { if (isDrawerOpen()) closeDrawer({ silent: true }); stopDrawerPoll(); state.open = null; return; }
    if (state.open === id && isDrawerOpen()) return;
    state.open = id;
    showRun(id);
  }
  function stopDrawerPoll() { if (state.drawerPoll) { state.drawerPoll.stop(); state.drawerPoll = null; } }

  async function showRun(id) {
    stopDrawerPoll();
    state.drawerAfter = 0;
    const logBox = h("div", { class: "log", role: "log", "aria-live": "off", "aria-label": "Run log", tabindex: "0" });
    const top = h("div", { class: "stack" });
    openDrawer({ title: `Run ${id.slice(0, 8)}`, subtitle: "Loading…", body: [top, h("h3", null, "Log"), logBox], onClose: () => { stopDrawerPoll(); state.open = null; ctx.go(ctx.hashFor("runs")); } });
    const refresh = async () => {
      let run;
      try { run = await api(`/dashboard/api/runs/${id}/`, { params: { after: state.drawerAfter } }); }
      catch (error) { replace(top, errorState(error)); stopDrawerPoll(); return; }
      state.drawerAfter = run.progress.log_next;
      $("#drawer-sub").textContent = `${modeLabel(run.request, run.sources)} · ${limitLabel(run.request.limit)}`;
      renderIf(top, [run.status, run.summary, run.error, run.progress.stages, run.progress.cancel_requested], () => detail(ctx, run));
      for (const line of run.progress.log) logBox.append(h("div", { class: `log-line ${line.level}` }, h("time", { datetime: line.t }, fmtClock(line.t)), h("span", { class: "lvl" }, line.level.toUpperCase()), h("span", { class: "msg" }, line.msg)));
      if (run.progress.log.length) logBox.scrollTop = logBox.scrollHeight;
      if (!["queued", "running"].includes(run.status)) stopDrawerPoll();
    };
    await refresh();
    if ($("#drawer").open && !top.querySelector(".banner.bad[role=alert]")) state.drawerPoll = ctx.poll(refresh, 1500, { immediate: false });
  }
  return { unmount() { stopDrawerPoll(); poll.stop(); if (isDrawerOpen()) closeDrawer({ silent: true }); }, onRoute: sync, reload: load };
}

function table(ctx, items) {
  const head = ["Status", "Started", "Duration", "Mode", "Articles", "Outcome", "Run"];
  return h("div", { class: "table-wrap" }, h("table", { class: "table stack-narrow" },
    h("caption", { class: "sr-only" }, "Pipeline runs, newest first"),
    h("thead", null, h("tr", null, head.map((t) => h("th", { scope: "col" }, t)))),
    h("tbody", null, items.map((run) => {
      const s = run.summary;
      return h("tr", null,
        h("td", { class: "cell-main", "data-label": "Status" }, runChip(run.status)),
        h("td", { "data-label": "Started" }, h("span", { title: fmtDate(run.started_at || run.created_at) }, fmtRel(run.started_at || run.created_at))),
        h("td", { "data-label": "Duration", class: "num" }, fmtDur(run.duration_seconds)),
        h("td", { "data-label": "Mode" }, modeLabel(run.request, run.sources)),
        h("td", { "data-label": "Articles" }, limitLabel(run.request.limit)),
        h("td", { "data-label": "Outcome" }, s ? `${fmtNum(s.approved)} approved · ${fmtNum(s.rejected)} rejected · ${fmtNum(s.failed)} failed` : run.error ? "Error" : "—"),
        h("td", { "data-label": "Run" }, h("a", { class: "btn btn-ghost btn-sm", href: ctx.hashFor("runs", [run.id]), "aria-label": `Open run ${run.id.slice(0, 8)}` }, h("span", { class: "mono" }, run.id.slice(0, 8)), icon("chevron-right"))));
    }))));
}

function detail(ctx, run) {
  const active = ["queued", "running"].includes(run.status);
  const s = run.summary;
  const rerun = ctx.hashFor("pipeline", [], {
    mode: run.request.scrape ? "full" : run.request.deduplicate ? "dedupe" : "process",
    limit: run.request.limit == null ? "all" : run.request.limit,
    sources: run.sources ? run.sources.join("|") : "",
  });
  return [
    h("div", { class: "row between" }, runChip(run.status),
      h("div", { class: "row" },
        active && button({ label: run.progress.cancel_requested ? "Stopping…" : "Stop run", iconName: "stop", variant: "danger", small: true, disabled: run.progress.cancel_requested,
          onclick: async () => { if (!(await confirmDialog({ title: "Stop this run?", tone: "danger", confirmLabel: "Stop run", body: h("p", null, "It stops at the next safe point; finished articles stay saved.") }))) return;
            try { await api(`/dashboard/api/runs/${run.id}/cancel/`, { method: "POST" }); toast("Stopping after the current step", "warn"); } catch (e) { toast(e.message, "bad"); } } }),
        !active && h("a", { class: "btn btn-secondary btn-sm", href: rerun }, icon("refresh"), "Run again"))),
    run.error && banner(run.status === "failed" ? "bad" : "warn", "alert", run.error),
    h("dl", { class: "kv" },
      h("dt", null, "Run ID"), h("dd", { class: "mono" }, run.id),
      h("dt", null, "Mode"), h("dd", null, modeLabel(run.request, run.sources)),
      h("dt", null, "Articles"), h("dd", null, limitLabel(run.request.limit)),
      run.sources && [h("dt", null, "Sources"), h("dd", null, run.sources.join(", "))],
      h("dt", null, "Input"), h("dd", { class: "mono" }, run.request.input),
      h("dt", null, "Output"), h("dd", { class: "mono" }, run.request.output),
      h("dt", null, "Created"), h("dd", null, fmtDate(run.created_at)),
      h("dt", null, "Started"), h("dd", null, fmtDate(run.started_at)),
      h("dt", null, "Finished"), h("dd", null, fmtDate(run.finished_at)),
      h("dt", null, "Duration"), h("dd", { class: "num" }, fmtDur(run.duration_seconds))),
    s && [h("h3", null, "Results by status"), s.by_status && Object.keys(s.by_status).length
      ? hbars(Object.entries(s.by_status).map(([k, v]) => ({ name: k.replaceAll("_", " ").toLowerCase(), value: v, tone: k === "APPROVED" ? "ok" : k.endsWith("_REJECTED") ? "warn" : "bad" })), { label: "Results by status" })
      : h("p", { class: "muted" }, "No rows were processed.")],
    h("h3", null, "Stages"),
    h("ul", { class: "stack-sm", role: "list" }, run.progress.stages.map((st) => h("li", { class: "row between" }, h("span", null, st.label), h("span", { class: "muted num" }, st.state === "skipped" ? "not in this run" : [st.state, st.passed || st.rejected || st.failed ? ` · ${st.passed} passed${st.rejected ? ` · ${st.rejected} rejected` : ""}${st.failed ? ` · ${st.failed} failed` : ""}` : ""].join(""))))),
  ];
}
