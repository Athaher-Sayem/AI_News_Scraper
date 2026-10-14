import { $, $$, h, icon, replace, fmtNum } from "./dom.js";
import { api, getKey, setKey, isKeyRemembered, onAuthRequired, ApiError } from "./api.js";
import { initDrawer, closeDrawer, setTitle, toast } from "./ui.js";

const ROUTES = [
  { name: "overview", label: "Overview", icon: "overview", load: () => import("./views/overview.js") },
  { name: "pipeline", label: "Pipeline", icon: "pipeline", load: () => import("./views/pipeline.js") },
  { name: "runs", label: "Runs", icon: "runs", load: () => import("./views/runs.js") },
  { name: "review", label: "Review", icon: "review", load: () => import("./views/review.js") },
  { name: "data", label: "Data", icon: "data", load: () => import("./views/data.js") },
];

// ---- shared state -----------------------------------------------------------------
const listeners = new Map();
export const store = { overview: null, health: null, error: null, lastOk: null };

function emit(topic) { (listeners.get(topic) || []).forEach((fn) => fn(store[topic], store)); }
function subscribe(topic, fn) {
  if (!listeners.has(topic)) listeners.set(topic, new Set());
  listeners.get(topic).add(fn);
  return () => listeners.get(topic).delete(fn);
}

export async function refreshOverview() {
  try {
    store.overview = await api("/dashboard/api/overview/");
    store.error = null;
    store.lastOk = Date.now();
  } catch (error) {
    if (error.name === "AbortError") return;
    store.error = error;
  }
  emit("overview");
  renderChrome();
}

export async function refreshHealth() {
  try {
    store.health = await api("/api/v1/health/", { allow: [503] });
  } catch {
    store.health = null;
  }
  emit("health");
}

// ---- polling ------------------------------------------------------------------------
export function poller(fn, ms, { immediate = true } = {}) {
  let timer = null, stopped = false, inflight = false;
  const schedule = () => { clearTimeout(timer); if (!stopped) timer = setTimeout(tick, ms); };
  async function tick() {
    if (stopped) return;
    if (document.hidden || inflight) return schedule();
    inflight = true;
    try { await fn(); } catch { /* the caller reports errors */ } finally { inflight = false; schedule(); }
  }
  const onVisible = () => { if (!document.hidden && !stopped) { clearTimeout(timer); tick(); } };
  document.addEventListener("visibilitychange", onVisible);
  if (immediate) tick(); else schedule();
  return {
    now: () => { clearTimeout(timer); return tick(); },
    stop: () => { stopped = true; clearTimeout(timer); document.removeEventListener("visibilitychange", onVisible); },
  };
}

// ---- routing --------------------------------------------------------------------------
export function parseHash(hash = location.hash) {
  const raw = hash.replace(/^#\/?/, "");
  const [path, query = ""] = raw.split("?");
  const [name = "overview", ...segs] = path.split("/").filter(Boolean).map(decodeURIComponent);
  return { name, segs, query: new URLSearchParams(query) };
}
export function hashFor(name, segs = [], query = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) if (value !== "" && value != null) params.set(key, value);
  const text = params.toString();
  return `#/${[name, ...segs].map(encodeURIComponent).join("/")}${text ? `?${text}` : ""}`;
}
export function go(hash, { replace: replaceState = false } = {}) {
  if (location.hash === hash) return;
  if (replaceState) { history.replaceState(null, "", hash); handleRoute(); } else location.hash = hash;
}

let current = null; // { name, view, pollers, unsubs }

const ctxFor = (route, state) => ({
  main: $("#main"),
  route,
  store,
  go,
  hashFor,
  refreshOverview,
  subscribe: (topic, fn) => { const off = subscribe(topic, fn); state.unsubs.push(off); return off; },
  poll: (fn, ms, options) => { const p = poller(fn, ms, options); state.pollers.push(p); return p; },
});

async function handleRoute() {
  const route = parseHash();
  const def = ROUTES.find((r) => r.name === route.name) || ROUTES[0];
  renderNav(def.name);
  if (current && current.name === def.name) {
    // Same view: let it react to the new hash (drawer, filters) instead of remounting.
    // While the module is still loading (view not ready) the initial route is already current.
    if (current.view && current.view.onRoute) current.view.onRoute(route);
    return;
  }
  teardown();
  closeDrawer({ silent: true });
  const main = $("#main");
  replace(main, h("div", { class: "stack", "aria-busy": "true" }, h("div", { class: "skel", "data-h": "24" }), h("div", { class: "skel", "data-h": "120" })));
  setTitle(def.label);
  const state = { name: def.name, view: null, pollers: [], unsubs: [] };
  current = state;
  try {
    const module = await def.load();
    if (current !== state) return; // navigated away while loading
    replace(main);
    state.view = module.mount(ctxFor(route, state)) || {};
    const heading = $("h1", main);
    if (heading) heading.focus({ preventScroll: true }); else main.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  } catch (error) {
    replace(main, h("div", { class: "banner bad", role: "alert" }, icon("alert"), h("div", null, h("strong", null, "This view failed to load"), h("div", { class: "muted" }, error.message))));
  }
}

function teardown() {
  if (!current) return;
  current.pollers.forEach((p) => p.stop());
  current.unsubs.forEach((off) => off());
  if (current.view && current.view.unmount) current.view.unmount();
  current = null;
}

// ---- chrome ------------------------------------------------------------------------------
function renderNav(active) {
  const build = (extraClass) => ROUTES.map((r) => h("a", {
    href: hashFor(r.name), class: extraClass, "aria-current": r.name === active ? "page" : null,
  }, icon(r.icon), h("span", null, r.label), r.name === "pipeline" && h("span", { class: "nav-badge-slot", "data-badge": "" })));
  replace($("#nav-side"), build(""));
  replace($("#nav-tabs"), build(""));
  paintBadges();
}
function paintBadges() {
  const live = !!store.overview?.active_run;
  $$("[data-badge]").forEach((slot) => {
    if (slot.dataset.on === String(live)) return;
    slot.dataset.on = String(live);
    replace(slot, live ? h("span", { class: "chip accent nav-badge" }, icon("spinner", "spin"), "Live") : null);
  });
}

function renderChrome() {
  const run = store.overview?.active_run;
  const indicator = $("#run-indicator");
  if (run) {
    const rows = run.progress.row;
    const pct = rows.total ? Math.round(((rows.index - 1 + (rows.stage ? 0.5 : 1)) / rows.total) * 100) : null;
    replace(indicator, h("a", { class: "chip accent", href: hashFor("pipeline"), "aria-label": "A pipeline run is in progress. Open live view" },
      icon("spinner", "spin"), run.progress.cancel_requested ? "Stopping…" : pct != null && pct >= 0 ? `Running · ${Math.min(pct, 99)}%` : "Running"));
  } else replace(indicator);
  const conn = $("#conn-indicator");
  if (store.error) {
    replace(conn, h("span", { class: "chip bad", role: "status" }, icon("alert"), store.error.status === 401 ? "Key needed" : "Offline"));
  } else if (store.overview) {
    replace(conn, h("span", { class: "chip ok", title: "Connected; data refreshes automatically" }, icon("check"), "Live"));
  }
  paintBadges();
}

function initTheme() {
  const button = $("#btn-theme");
  const effective = () => {
    const attr = document.documentElement.getAttribute("data-theme");
    if (attr === "light" || attr === "dark") return attr;
    return matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  };
  const paint = () => {
    const mode = effective();
    button.setAttribute("aria-label", mode === "dark" ? "Switch to light theme" : "Switch to dark theme");
    button.title = button.getAttribute("aria-label");
    replace(button, icon(mode === "dark" ? "sun" : "moon"));
  };
  button.addEventListener("click", () => {
    const next = effective() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("console.theme", next); } catch { /* ignore */ }
    paint();
  });
  matchMedia("(prefers-color-scheme: light)").addEventListener("change", paint);
  paint();
}

function initKeyDialog() {
  const dialog = $("#keydialog"), input = $("#key-input"), remember = $("#key-remember"), error = $("#key-error");
  const open = (message) => {
    input.value = getKey();
    remember.checked = isKeyRemembered();
    error.hidden = !message;
    error.textContent = message || "";
    if (!dialog.open) dialog.showModal();
    input.focus();
  };
  $("#btn-key").addEventListener("click", () => open());
  $("#key-cancel").addEventListener("click", () => dialog.close());
  $("#key-clear").addEventListener("click", () => { setKey(""); input.value = ""; dialog.close(); toast("API key removed", "info"); refreshOverview(); });
  $("#key-form").addEventListener("submit", (event) => {
    event.preventDefault();
    setKey(input.value, remember.checked);
    dialog.close();
    toast(getKey() ? "API key saved" : "API key cleared", "ok");
    refreshOverview(); refreshHealth();
    if (current?.view?.reload) current.view.reload();
  });
  let prompted = false;
  onAuthRequired(() => {
    if (prompted || dialog.open) return;
    prompted = true;
    open("The server requires an API key. Enter it to continue.");
    dialog.addEventListener("close", () => { prompted = false; }, { once: true });
  });
  $("#btn-key").dataset.active = getKey() ? "true" : "false";
}

function boot() {
  initTheme();
  initDrawer();
  initKeyDialog();
  renderNav(parseHash().name);
  window.addEventListener("hashchange", handleRoute);
  poller(refreshOverview, 8000);
  poller(refreshHealth, 15000);
  handleRoute();
}

boot();
export { ApiError, fmtNum };
