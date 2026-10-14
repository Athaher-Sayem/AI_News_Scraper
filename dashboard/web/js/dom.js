// Tiny DOM helpers. All dynamic text goes through text nodes, never innerHTML,
// because scraped titles and article bodies are untrusted.

const SVG_NS = "http://www.w3.org/2000/svg";
const PROPS = new Set(["value", "checked", "selected", "disabled", "indeterminate"]);

export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value == null || value === false) continue;
      if (key === "class") el.className = value;
      else if (key === "dataset") Object.assign(el.dataset, value);
      else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2).toLowerCase(), value);
      else if (PROPS.has(key)) el[key] = value;
      else el.setAttribute(key, value === true ? "" : String(value));
    }
  }
  append(el, children);
  return el;
}

export function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function svg(tag, attrs, ...children) {
  const el = document.createElementNS(SVG_NS, tag);
  if (attrs) for (const [key, value] of Object.entries(attrs)) if (value != null) el.setAttribute(key, String(value));
  for (const child of children.flat()) if (child) el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return el;
}

export function icon(name, cls = "") {
  const el = svg("svg", { class: `icon ${cls}`.trim(), "aria-hidden": "true", focusable: "false" });
  el.append(svg("use", { href: `#i-${name}` }));
  return el;
}

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

export function replace(el, ...children) {
  el.replaceChildren();
  append(el, children);
  return el;
}

/** Re-render `el` only when `signature` changed, keeping focus/scroll stable while polling. */
export function renderIf(el, signature, render) {
  const next = typeof signature === "string" ? signature : JSON.stringify(signature);
  if (el.dataset.sig === next) return false;
  el.dataset.sig = next;
  replace(el, render());
  return true;
}

export function debounce(fn, ms = 250) {
  let timer;
  const wrapped = (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
  wrapped.cancel = () => clearTimeout(timer);
  return wrapped;
}

// ---- formatting -----------------------------------------------------------
const numberFormat = new Intl.NumberFormat();
const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const dayFormat = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const timeFormat = new Intl.DateTimeFormat(undefined, { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
const relative = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

export const fmtNum = (value) => (value == null || Number.isNaN(value) ? "—" : numberFormat.format(value));
export const fmtPct = (part, whole) => (!whole ? "—" : `${Math.round((part / whole) * 100)}%`);
export function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? String(iso) : dateFormat.format(d);
}
export const fmtDay = (iso) => dayFormat.format(new Date(`${iso}T00:00:00`));
export const fmtClock = (iso) => timeFormat.format(new Date(iso));
export function fmtRel(iso) {
  if (!iso) return "never";
  const seconds = Math.round((new Date(iso).getTime() - Date.now()) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 45) return "just now";
  for (const [limit, unit, size] of [[3600, "minute", 60], [86400, "hour", 3600], [2592000, "day", 86400], [31536000, "month", 2592000]]) {
    if (abs < limit) return relative.format(Math.round(seconds / size), unit);
  }
  return relative.format(Math.round(seconds / 31536000), "year");
}
export function fmtDur(seconds) {
  if (seconds == null) return "—";
  const total = Math.max(0, Math.round(seconds));
  const hrs = Math.floor(total / 3600), mins = Math.floor((total % 3600) / 60), secs = total % 60;
  if (hrs) return `${hrs}h ${String(mins).padStart(2, "0")}m`;
  if (mins) return `${mins}m ${String(secs).padStart(2, "0")}s`;
  return `${secs}s`;
}
export function fmtBytes(bytes) {
  if (bytes == null) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes, i = 0;
  while (value >= 1024 && i < units.length - 1) { value /= 1024; i += 1; }
  return `${value >= 10 || i === 0 ? Math.round(value) : value.toFixed(1)} ${units[i]}`;
}

// ---- status vocabulary ------------------------------------------------------
export const ROW_STATUS = {
  APPROVED: { label: "Approved", tone: "ok", icon: "check" },
  ARTICLE_REJECTED: { label: "Rejected by verifier", tone: "warn", icon: "alert" },
  CONTENT_REJECTED: { label: "Content rejected", tone: "warn", icon: "alert" },
  FACT_EXTRACTION_FAILED: { label: "Fact extraction failed", tone: "bad", icon: "x" },
  ARTICLE_GENERATION_FAILED: { label: "Generation failed", tone: "bad", icon: "x" },
  ARTICLE_VERIFICATION_FAILED: { label: "Verification failed", tone: "bad", icon: "x" },
};
export const RUN_STATUS = {
  queued: { label: "Queued", tone: "info", icon: "circle" },
  running: { label: "Running", tone: "accent", icon: "spinner" },
  succeeded: { label: "Succeeded", tone: "ok", icon: "check" },
  failed: { label: "Failed", tone: "bad", icon: "x" },
  cancelled: { label: "Cancelled", tone: "warn", icon: "minus" },
};

/** Chip with icon + text, so state never depends on color alone. */
export function chip(meta, fallback = "Unknown") {
  const m = meta || { label: fallback, tone: "plain", icon: "circle" };
  const spinning = m.icon === "spinner";
  return h("span", { class: `chip ${m.tone}` }, icon(m.icon, spinning ? "spin" : ""), m.label);
}
export const rowChip = (status) => chip(ROW_STATUS[status], status || "Unknown");
export const runChip = (status) => chip(RUN_STATUS[status], status || "Unknown");

export function modeLabel(request, sources) {
  if (request?.scrape) {
    const picked = sources && sources.length ? ` · ${sources.length} source${sources.length > 1 ? "s" : ""}` : "";
    return `Full pipeline${picked}`;
  }
  return request?.deduplicate ? "Deduplicate + process" : "Process only";
}
export const limitLabel = (limit) => (limit == null ? "All articles" : `${fmtNum(limit)} article${limit === 1 ? "" : "s"}`);
