import { h, icon, replace, renderIf, $, fmtNum, fmtClock, fmtDur, runChip, modeLabel, limitLabel } from "../dom.js";
import { api, ApiError } from "../api.js";
import { pageHead, button, banner, field, setTitle, toast, confirmDialog, emptyState } from "../ui.js";

const MODES = [
  { id: "process", icon: "review", title: "Process only", help: "Use the existing unique articles CSV." },
  { id: "dedupe", icon: "data", title: "Deduplicate + process", help: "Re-run semantic deduplication on the raw CSV first." },
  { id: "full", icon: "pipeline", title: "Full pipeline", help: "Scrape publishers, deduplicate, then process." },
];
const STAGE_ICON = { active: "check", pending: "circle", running: "spinner", done: "check", failed: "x", cancelled: "minus", skipped: "minus" };
const STATE_TEXT = { active: "Active", pending: "Waiting", running: "Running", done: "Done", failed: "Failed", cancelled: "Cancelled", skipped: "Not in this run" };

export function mount(ctx) {
  setTitle("Pipeline");
  const state = { runId: null, after: 0, log: [], finishedAnnounced: null, seenActive: new Set(), token: 0, ticker: null, runPoll: null, prefill: ctx.route.query };
  const els = { preflight: h("div"), form: h("form", { class: "card", novalidate: true, "aria-label": "Run settings" }), live: h("div", { class: "stack" }) };

  replace(ctx.main,
    pageHead("Pipeline", "Configure a run, watch every stage live, and stop it safely."),
    h("div", { class: "stack" }, els.preflight, h("div", { class: "grid split" }, els.form, els.live)));

  const form = buildForm(ctx, els.form, state, onStart);
  const live = buildLive(ctx, els.live, state);

  function paintPreflight() {
    const { overview, health } = ctx.store;
    renderIf(els.preflight, { g: health?.generation, a: overview?.active_run?.id }, () => {
      const gen = health?.generation;
      const out = [];
      if (overview?.active_run) out.push(banner("info", "info", [h("strong", null, "A run is already in progress. "), "Only one run can be active at a time; you can watch or stop it on the right."]));
      if (gen && !gen.available) out.push(banner("warn", "alert", [h("strong", null, "Generation service is offline. "), `Processing needs Ollama at its configured address. Start it with `, h("code", null, "ollama serve"), ` before running.`]));
      else if (gen && !gen.model_installed) out.push(banner("warn", "alert", [h("strong", null, `Model ${gen.model} is not installed. `), "Install it with ", h("code", null, `ollama pull ${gen.model}`), "."]));
      return h("div", { class: "stack-sm" }, out);
    });
    form.setBusy(!!overview?.active_run);
  }

  async function onStart(body) {
    try {
      const run = await api("/dashboard/api/runs/", { method: "POST", body });
      toast("Run queued", "ok");
      await ctx.refreshOverview();
      follow(run.id, true);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) { toast("A run is already in progress", "warn"); ctx.refreshOverview(); }
      else throw error;
    }
  }

  function follow(id, reset = false) {
    if (state.runId === id && !reset) return;
    if (state.runPoll) state.runPoll.stop();
    const token = ++state.token; // ignore replies from superseded pollers
    state.runId = id; state.after = 0; state.log = [];
    live.reset();
    state.runPoll = ctx.poll(async () => {
      let run;
      try { run = await api(`/dashboard/api/runs/${id}/`, { params: { after: state.after } }); } catch (error) { if (token === state.token) live.error(error); return; }
      if (token !== state.token) return;
      state.after = run.progress.log_next;
      live.update(run);
      if (["queued", "running"].includes(run.status)) state.seenActive.add(id);
      else {
        state.runPoll.stop(); state.runPoll = null;
        if (state.finishedAnnounced !== id && state.seenActive.has(id)) {
          state.finishedAnnounced = id;
          toast(`Run ${run.status}`, run.status === "succeeded" ? "ok" : run.status === "cancelled" ? "warn" : "bad");
          ctx.refreshOverview();
        }
      }
    }, 1200);
  }

  const sync = () => {
    paintPreflight();
    const { overview } = ctx.store;
    if (!overview) return;
    form.setContext(overview);
    const active = overview.active_run;
    if (active && state.runId !== active.id) follow(active.id);
    else if (!active && !state.runId && overview.latest_run) { state.runId = overview.latest_run.id; follow(overview.latest_run.id, true); }
    else if (!active && !state.runId) live.empty();
  };
  ctx.subscribe("overview", sync);
  ctx.subscribe("health", paintPreflight);
  sync();
  state.ticker = setInterval(() => live.tick(), 1000);
  return {
    unmount() { clearInterval(state.ticker); },
    onRoute(route) { form.prefill(route.query); },
  };
}

// ---- form ----------------------------------------------------------------------------
function buildForm(ctx, root, state, onStart) {
  const ids = { limit: "run-limit", input: "run-input", output: "run-output" };
  const modeInputs = MODES.map((m) => h("label", { class: "choice" },
    h("input", { type: "radio", name: "mode", value: m.id, checked: m.id === "process" }),
    h("span", { class: "choice-body" }, icon(m.icon), h("span", null, h("strong", null, m.title), h("span", { class: "help" }, m.help)))));
  const limit = h("input", { id: ids.limit, class: "input num", type: "number", min: "1", step: "1", value: "5", inputmode: "numeric", "aria-describedby": "limit-help limit-error" });
  const allBox = h("input", { type: "checkbox", id: "run-all" });
  const limitError = h("p", { id: "limit-error", class: "field-error", role: "alert", hidden: true });
  const sourceBox = h("fieldset", { class: "stack-sm", hidden: true }, h("legend", null, "Sources to scrape"));
  const sourceHelp = h("p", { class: "help" }, "Leave all checked to scrape every configured publisher.");
  const input = h("select", { id: ids.input, class: "select" });
  const output = h("input", { id: ids.output, class: "input mono", type: "text", value: "data/processed_news.csv", spellcheck: "false", autocomplete: "off", "aria-describedby": "output-help output-error" });
  const outputError = h("p", { id: "output-error", class: "field-error", role: "alert", hidden: true });
  const submit = h("button", { class: "btn btn-primary btn-block", type: "submit" }, icon("play"), "Start run");
  const advanced = h("details", { class: "stack" },
    h("summary", { class: "label", tabindex: "0" }, "Advanced: files"),
    h("div", { class: "stack" },
      field("Input CSV", input, { id: ids.input, help: "Unique articles to process. Must be inside data/." }),
      h("div", null, field("Output CSV", output, { id: ids.output, help: "Replaced with this run’s results. Never the raw scrape file." }), outputError)));

  replace(root,
    h("div", { class: "card-head" }, h("div", null, h("h2", null, "Run settings"))),
    h("fieldset", { class: "stack" }, h("legend", null, "What to run"), h("div", { class: "choice-grid" }, modeInputs)),
    h("hr", { class: "divider" }),
    h("div", null,
      h("label", { class: "label", for: ids.limit }, "Articles to process", h("span", { class: "req", "aria-hidden": "true" }, " *")),
      h("div", { class: "stepper-input" }, limit, h("label", { class: "check" }, allBox, h("span", null, "All"))),
      h("p", { id: "limit-help", class: "help" }, "Generation is the slow step; start small to check output quality."),
      limitError),
    sourceBox, sourceHelp,
    h("hr", { class: "divider" }),
    advanced,
    h("div", { class: "stack-sm" }, submit));

  const mode = () => root.querySelector('input[name="mode"]:checked').value;
  const sourceInputs = () => [...sourceBox.querySelectorAll("input[type=checkbox]")];
  let busy = false;

  const refreshDisclosure = () => {
    const full = mode() === "full";
    sourceBox.hidden = !full; sourceHelp.hidden = !full;
    for (const option of input.options) option.disabled = option.dataset.role === "raw" && mode() !== "process";
    if (input.selectedOptions[0]?.disabled) input.value = "data/unique_news.csv";
    limit.disabled = allBox.checked;
  };
  root.addEventListener("change", refreshDisclosure);
  allBox.addEventListener("change", () => { if (allBox.checked) { limitError.hidden = true; limit.removeAttribute("aria-invalid"); } });

  function validate() {
    let ok = true;
    limit.removeAttribute("aria-invalid"); limitError.hidden = true; outputError.hidden = true; output.removeAttribute("aria-invalid");
    if (!allBox.checked) {
      const n = Number(limit.value);
      if (!Number.isInteger(n) || n < 1) {
        limitError.textContent = "Enter a whole number of 1 or more, or tick All."; limitError.hidden = false; limit.setAttribute("aria-invalid", "true"); limit.focus(); ok = false;
      }
    }
    const path = output.value.trim().replaceAll("\\", "/");
    if (!/^(\.\/)?data\/.+\.csv$/i.test(path) && !/^[A-Za-z]:\//.test(path) && !path.startsWith("/")) {
      outputError.textContent = "Use a .csv path inside data/, for example data/processed_news.csv."; outputError.hidden = false; output.setAttribute("aria-invalid", "true");
      if (ok) output.focus();
      advanced.open = true; ok = false;
    }
    return ok;
  }

  root.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || !validate()) return;
    const body = { scrape: mode() === "full", deduplicate: mode() === "dedupe", limit: allBox.checked ? "all" : Number(limit.value), input: input.value, output: output.value.trim() };
    if (mode() === "full") {
      const picked = sourceInputs().filter((c) => c.checked).map((c) => c.value);
      if (!picked.length) { toast("Pick at least one source to scrape", "warn"); return; }
      if (picked.length < sourceInputs().length) body.sources = picked;
    }
    const heavy = mode() === "full" || allBox.checked;
    if (heavy) {
      const ok = await confirmDialog({
        title: "Start this run?",
        body: [h("p", null, `${modeLabel(body, body.sources)} · ${limitLabel(body.limit === "all" ? null : body.limit)}.`),
          mode() === "full" && h("p", null, "This contacts live publisher sites, then runs the language model on every selected article. It can take a long time."),
          h("p", null, `Results replace ${body.output}.`)],
        confirmLabel: "Start run",
      });
      if (!ok) return;
    }
    submit.disabled = true; submit.replaceChildren(icon("spinner", "spin"), "Starting…");
    try { await onStart(body); } catch (error) { toast(error.message, "bad", 7000); }
    finally { submit.replaceChildren(icon("play"), "Start run"); submit.disabled = busy; }
  });

  const api_ = {
    setBusy(value) { busy = value; submit.disabled = value; submit.title = value ? "A run is already in progress" : ""; },
    setContext(overview) {
      const files = overview.files.filter((f) => f.name.endsWith(".csv"));
      const sig = JSON.stringify([files.map((f) => f.name), overview.config.sources]);
      if (sourceBox.dataset.sig === sig) return;
      sourceBox.dataset.sig = sig;
      const selected = input.value || "data/unique_news.csv";
      replace(input, files.map((f) => h("option", { value: `data/${f.name}`, "data-role": f.role }, `${f.name}${f.role === "raw" ? " (raw, not deduplicated)" : f.role === "processed" ? " (previous results)" : ""}${f.rows != null ? ` · ${fmtNum(f.rows)} rows` : ""}`)));
      input.value = files.some((f) => `data/${f.name}` === selected) ? selected : "data/unique_news.csv";
      const wanted = new Set(state.prefill.get("sources") ? state.prefill.get("sources").split("|") : overview.config.sources);
      replace(sourceBox, h("legend", null, "Sources to scrape"), overview.config.sources.map((name) =>
        h("label", { class: "check" }, h("input", { type: "checkbox", value: name, checked: wanted.has(name) }), h("span", null, name))));
      this.prefill(state.prefill);
    },
    prefill(query) {
      state.prefill = query;
      const requested = query.get("mode");
      if (requested && MODES.some((m) => m.id === requested)) root.querySelector(`input[name="mode"][value="${requested}"]`).checked = true;
      if (query.get("limit")) { if (query.get("limit") === "all") allBox.checked = true; else { allBox.checked = false; limit.value = query.get("limit"); } }
      if (query.get("sources")) { const wanted = new Set(query.get("sources").split("|")); sourceInputs().forEach((c) => { c.checked = wanted.has(c.value); }); }
      refreshDisclosure();
    },
  };
  refreshDisclosure();
  api_.prefill(state.prefill);
  return api_;
}

// ---- live panel -----------------------------------------------------------------------
function buildLive(ctx, root, state) {
  const head = h("div", { class: "card" });
  const stages = h("div", { class: "card" });
  const logCard = h("div", { class: "card" });
  const result = h("div");
  const logBox = h("div", { class: "log", role: "log", "aria-live": "off", "aria-label": "Run log", tabindex: "0" });
  const logHeader = h("div", { class: "card-head" }, h("div", null, h("h2", null, "Log")));
  logCard.append(logHeader, logBox);
  replace(root, head, result, stages, logCard);
  let current = null, elapsedEl = null;

  const api_ = {
    reset() { head.dataset.sig = stages.dataset.sig = result.dataset.sig = ""; replace(logBox); current = null; replace(head, h("div", { class: "skel", "data-h": "48", "aria-hidden": "true" })); },
    empty() {
      replace(head, emptyState({ iconName: "pipeline", title: "No run yet", text: "Choose what to run and press Start. Progress, stage results and the log appear here live." }));
      stages.hidden = logCard.hidden = true;
    },
    error(error) { replace(head, banner("bad", "alert", [h("strong", null, "Lost contact with the run. "), error.message])); },
    update(run) {
      current = run;
      stages.hidden = logCard.hidden = false;
      renderIf(head, [run.id, run.status, run.progress.cancel_requested, run.progress.row, run.finished_at], () => headCard(run));
      renderIf(stages, run.progress.stages, () => stageGrid(run));
      renderIf(result, [run.id, run.status, run.summary, run.error], () => resultCard(ctx, run));
      appendLog(run.progress.log);
      this.tick();
    },
    tick() {
      if (!current) return;
      elapsedEl = elapsedEl && document.contains(elapsedEl) ? elapsedEl : $("[data-elapsed]", head);
      if (!elapsedEl) return;
      const active = ["queued", "running"].includes(current.status);
      const start = new Date(current.started_at || current.created_at).getTime();
      elapsedEl.textContent = active ? fmtDur((Date.now() - start) / 1000) : fmtDur(current.duration_seconds);
    },
  };

  function appendLog(lines) {
    if (!lines.length) { if (!logBox.childElementCount) logBox.append(h("span", { class: "log-empty" }, "Waiting for output…")); return; }
    if (logBox.querySelector(".log-empty")) replace(logBox);
    const stick = logBox.scrollHeight - logBox.scrollTop - logBox.clientHeight < 40;
    for (const line of lines) {
      logBox.append(h("div", { class: `log-line ${line.level}` }, h("time", { datetime: line.t }, fmtClock(line.t)), h("span", { class: "lvl" }, line.level.toUpperCase()), h("span", { class: "msg" }, line.msg)));
    }
    while (logBox.childElementCount > 500) logBox.firstElementChild.remove();
    if (stick) logBox.scrollTop = logBox.scrollHeight;
  }

  function headCard(run) {
    const active = ["queued", "running"].includes(run.status);
    const rows = run.progress.row;
    const done = rows.stage ? rows.index - 1 : rows.index;
    const running = run.progress.stages.find((s) => s.state === "running");
    const cancel = active && button({
      label: run.progress.cancel_requested ? "Stopping…" : "Stop run", iconName: "stop", variant: "danger", small: true, disabled: run.progress.cancel_requested,
      onclick: async () => {
        const ok = await confirmDialog({ title: "Stop this run?", tone: "danger", confirmLabel: "Stop run",
          body: [h("p", null, "The run stops at the next safe point: after the current publisher or the current article."), h("p", null, "Articles already processed are saved to the output file.")] });
        if (!ok) return;
        try { await api(`/dashboard/api/runs/${run.id}/cancel/`, { method: "POST" }); toast("Stopping after the current step", "warn"); state.runPoll?.now(); } catch (error) { toast(error.message, "bad"); }
      },
    });
    return [
      h("div", { class: "card-head" },
        h("div", null, h("h2", null, active ? "Live run" : "Last run"), h("p", null, `${modeLabel(run.request, run.sources)} · ${limitLabel(run.request.limit)}`)),
        h("div", { class: "row" }, runChip(run.status), cancel)),
      h("div", { class: "stack-sm" },
        h("div", { class: "progress-line" },
          rows.total ? h("progress", { max: rows.total, value: Math.max(0, Math.min(done, rows.total)), "aria-label": "Articles processed" })
            : active ? h("progress", { "aria-label": "Working" }) : h("progress", { max: 1, value: run.status === "succeeded" ? 1 : 0, "aria-label": "Finished" }),
          h("span", { class: "num nowrap" }, rows.total ? `${Math.max(0, done)}/${rows.total}` : "")),
        h("div", { class: "meta-line" },
          h("span", null, "Elapsed ", h("span", { class: "num", "data-elapsed": "" }, "—")),
          active && running && h("span", null, `Now: ${running.label}`),
          active && rows.title && h("span", null, `Article: ${rows.title}`),
          run.progress.cancel_requested && active && h("span", { class: "chip warn" }, icon("alert"), "Cancel requested"))),
    ];
  }

  function stageGrid(run) {
    return [h("div", { class: "card-head" }, h("div", null, h("h2", null, "Stages"), h("p", null, "Counts are articles that passed, were rejected, or failed at each stage"))),
      h("ol", { class: "stages" }, run.progress.stages.map((s, i) => {
        // Row stages stay "running" for the whole run; only the one handling the current article spins.
        const shown = s.state === "running" && i >= 2 && run.progress.row.stage !== s.key ? "active" : s.state;
        return h("li", { class: "stage", dataset: { state: shown } },
          h("div", { class: "stage-top" }, icon(STAGE_ICON[shown], shown === "running" ? "spin" : ""), h("span", null, `${i + 1}. ${s.label}`), h("span", { class: "stage-state" }, STATE_TEXT[shown])),
          h("div", { class: "stage-counts" }, i >= 2 && s.state !== "skipped" && s.state !== "pending"
            ? [h("span", null, `${fmtNum(s.passed)} passed`), s.rejected > 0 && h("span", null, `${fmtNum(s.rejected)} rejected`), s.failed > 0 && h("span", null, `${fmtNum(s.failed)} failed`)]
            : null));
      }))];
  }

  function resultCard(ctx_, run) {
    if (["queued", "running"].includes(run.status)) return null;
    const s = run.summary;
    return h("div", { class: "card" },
      h("div", { class: "card-head" }, h("div", null, h("h2", null, "Result"), h("p", null, `Took ${fmtDur(run.duration_seconds)}`)),
        h("div", { class: "row" },
          h("a", { class: "btn btn-secondary btn-sm", href: ctx_.hashFor("runs", [run.id]) }, "Run details"),
          s && s.processed > 0 && h("a", { class: "btn btn-primary btn-sm", href: ctx_.hashFor("review") }, "Review results", icon("chevron-right")))),
      run.error && banner(run.status === "failed" ? "bad" : "warn", "alert", run.error),
      s ? h("dl", { class: "kv" }, h("dt", null, "Processed"), h("dd", { class: "num" }, fmtNum(s.processed)), h("dt", null, "Approved"), h("dd", { class: "num" }, fmtNum(s.approved)),
        h("dt", null, "Rejected"), h("dd", { class: "num" }, fmtNum(s.rejected)), h("dt", null, "Failed"), h("dd", { class: "num" }, fmtNum(s.failed)))
        : h("p", { class: "muted" }, "No results were written."));
  }
  return api_;
}
