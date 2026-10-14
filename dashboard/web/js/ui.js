import { $, h, icon, svg, replace, fmtNum, fmtDay } from "./dom.js";

// ---- toasts (polite live region, never steals focus) -----------------------
export function toast(message, tone = "ok", ms = 4500) {
  const iconName = { ok: "check", bad: "alert", warn: "alert", info: "info" }[tone] || "info";
  const el = h("div", { class: `toast ${tone}` }, icon(iconName), h("span", null, message));
  $("#toasts").append(el);
  setTimeout(() => el.remove(), ms);
}

// ---- confirm dialog ----------------------------------------------------------
export function confirmDialog({ title, body, confirmLabel = "Confirm", tone = "primary" }) {
  const dialog = $("#confirm"), ok = $("#confirm-ok"), cancel = $("#confirm-cancel");
  $("#confirm-title").textContent = title;
  replace($("#confirm-body"), body);
  ok.textContent = confirmLabel;
  ok.className = `btn ${tone === "danger" ? "btn-danger-solid" : "btn-primary"}`;
  return new Promise((resolve) => {
    const finish = (value) => {
      ok.onclick = cancel.onclick = dialog.oncancel = null;
      dialog.close();
      resolve(value);
    };
    ok.onclick = () => finish(true);
    cancel.onclick = () => finish(false);
    dialog.oncancel = (event) => { event.preventDefault(); finish(false); };
    dialog.showModal();
    cancel.focus(); // the safe choice gets initial focus
  });
}

// ---- side drawer ---------------------------------------------------------------
let drawerClose = null;
export function openDrawer({ title, subtitle = "", nav = null, body, onClose }) {
  const dialog = $("#drawer");
  $("#drawer-title").textContent = title;
  $("#drawer-sub").textContent = subtitle;
  replace($("#drawer-nav"), nav);
  replace($("#drawer-body"), body);
  $("#drawer-body").scrollTop = 0;
  drawerClose = onClose || null;
  if (!dialog.open) dialog.showModal();
}
export const drawerBody = () => $("#drawer-body");
export const isDrawerOpen = () => $("#drawer").open;
export function closeDrawer({ silent = false } = {}) {
  const dialog = $("#drawer");
  const callback = drawerClose;
  drawerClose = null;
  if (dialog.open) dialog.close();
  if (!silent && callback) callback();
}
export function initDrawer() {
  const dialog = $("#drawer");
  $("#drawer-close").addEventListener("click", () => closeDrawer());
  dialog.addEventListener("cancel", (event) => { event.preventDefault(); closeDrawer(); });
  dialog.addEventListener("click", (event) => { if (event.target === dialog) closeDrawer(); });
}

// ---- page + state scaffolding ----------------------------------------------------
export function pageHead(title, description, actions) {
  return h("div", { class: "page-head" },
    h("div", null, h("h1", { tabindex: "-1" }, title), description && h("p", null, description)),
    actions && h("div", { class: "page-actions" }, actions));
}

export function skeleton(lines = 3, height = 16) {
  return h("div", { class: "stack-sm", "aria-hidden": "true" },
    Array.from({ length: lines }, (_, i) => h("div", { class: "skel", dataset: { w: i === lines - 1 ? "short" : "full" }, "data-h": height })));
}

export function emptyState({ iconName = "info", title, text, action }) {
  return h("div", { class: "empty" }, icon(iconName), h("h3", null, title), text && h("p", null, text), action);
}

export function errorState(error, retry) {
  const unauthorized = error && error.status === 401;
  return h("div", { class: "banner bad", role: "alert" }, icon("alert"),
    h("div", null,
      h("strong", null, unauthorized ? "API key required" : "Could not load this data"),
      h("div", { class: "muted" }, error?.message || "Unexpected error")),
    retry && h("div", { class: "banner-actions" },
      h("button", { class: "btn btn-secondary btn-sm", type: "button", onclick: retry }, icon("refresh"), "Retry")));
}

export function banner(tone, iconName, children, actions) {
  return h("div", { class: `banner ${tone}` }, icon(iconName), h("div", null, children),
    actions && h("div", { class: "banner-actions" }, actions));
}

export function button({ label, iconName, variant = "secondary", small = false, ...attrs }) {
  return h("button", { type: "button", class: `btn btn-${variant}${small ? " btn-sm" : ""}`, ...attrs }, iconName && icon(iconName), label);
}

export function field(label, control, { help, id, required } = {}) {
  return h("label", { class: "field", for: id },
    h("span", { class: "label" }, label, required && h("span", { class: "req", "aria-hidden": "true" }, "*")),
    control, help && h("span", { class: "help" }, help));
}

export function pager(meta, onPage) {
  const page = meta.page || 1, pages = meta.total_pages || 1;
  const from = meta.total ? (page - 1) * meta.page_size + 1 : 0;
  const to = meta.total ? from + meta.count - 1 : 0;
  return h("nav", { class: "pager", "aria-label": "Pagination" },
    h("span", { class: "muted", "aria-live": "polite" }, `${fmtNum(from)}–${fmtNum(to)} of ${fmtNum(meta.total)}`),
    h("div", { class: "row" },
      h("button", { class: "btn btn-secondary btn-sm", type: "button", disabled: page <= 1, "aria-label": "Previous page", onclick: () => onPage(page - 1) }, icon("chevron-left"), "Prev"),
      h("span", { class: "num" }, `${page} / ${Math.max(pages, 1)}`),
      h("button", { class: "btn btn-secondary btn-sm", type: "button", disabled: page >= pages, "aria-label": "Next page", onclick: () => onPage(page + 1) }, "Next", icon("chevron-right"))));
}

// ---- charts (SVG; presentation attributes only, so the strict CSP holds) --------
/** Horizontal bars with direct value labels. rows: [{name, value, tone?, note?}] */
export function hbars(rows, { max, label = "Chart" } = {}) {
  const top = max || Math.max(1, ...rows.map((r) => r.value));
  return h("div", { class: "hbar", role: "list", "aria-label": label },
    rows.map((row) => {
      const width = Math.max(row.value > 0 ? 1.5 : 0, (row.value / top) * 100);
      return h("div", { class: "hbar-row", role: "listitem" },
        h("span", { class: "name" }, row.name),
        svg("svg", { viewBox: "0 0 100 14", preserveAspectRatio: "none", "aria-hidden": "true" },
          svg("rect", { class: "track", x: 0, y: 0, width: 100, height: 14, rx: 7 }),
          width > 0 && svg("rect", { class: `fill ${row.tone || ""}`, x: 0, y: 0, width, height: 14, rx: 7 })),
        h("span", { class: "val" }, fmtNum(row.value), row.note && h("small", null, row.note)));
    }));
}

/** Column chart for a daily series: [{date, count}] */
export function columns(series, { label = "Daily counts" } = {}) {
  const W = 640, H = 180, padL = 8, padR = 8, padT = 22, padB = 26;
  const max = Math.max(1, ...series.map((p) => p.count));
  const slot = (W - padL - padR) / series.length;
  const bw = Math.min(28, slot * 0.64);
  const el = svg("svg", { class: "columns", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${label}: ${series.map((p) => `${fmtDay(p.date)} ${p.count}`).join(", ")}` });
  el.append(svg("line", { class: "grid-line", x1: padL, x2: W - padR, y1: H - padB, y2: H - padB }));
  series.forEach((point, i) => {
    const bh = point.count ? Math.max(3, (point.count / max) * (H - padT - padB)) : 2;
    const x = padL + slot * i + (slot - bw) / 2;
    el.append(svg("rect", { class: `bar${point.count ? "" : " zero"}`, x, y: H - padB - bh, width: bw, height: bh, rx: 3 }));
    if (point.count) el.append(svg("text", { class: "val", x: x + bw / 2, y: H - padB - bh - 6, "text-anchor": "middle" }, fmtNum(point.count)));
    if (i % 2 === series.length % 2 || series.length < 8) el.append(svg("text", { x: x + bw / 2, y: H - 8, "text-anchor": "middle" }, fmtDay(point.date)));
  });
  return el;
}

/** Stacked proportion bar. parts: [{value, tone}] */
export function stackBar(parts, label) {
  const total = parts.reduce((s, p) => s + p.value, 0) || 1;
  const el = svg("svg", { viewBox: "0 0 100 14", preserveAspectRatio: "none", role: "img", "aria-label": label });
  el.append(svg("rect", { class: "track", x: 0, y: 0, width: 100, height: 14, rx: 7 }));
  let x = 0;
  for (const part of parts) {
    const width = (part.value / total) * 100;
    if (width <= 0) continue;
    el.append(svg("rect", { class: `fill ${part.tone || ""}`, x, y: 0, width: Math.max(width - 0.4, 0.4), height: 14 }));
    x += width;
  }
  return h("div", { class: "status-stack" }, el);
}

// ---- generic value renderer for facts / verification JSON ------------------------
export function tree(value) {
  if (value == null || value === "") return h("span", { class: "muted" }, "—");
  if (Array.isArray(value)) {
    if (!value.length) return h("span", { class: "muted" }, "none");
    return h("ul", { class: "tree" }, value.map((item) => h("li", null, h("div", { class: "v" }, tree(item)))));
  }
  if (typeof value === "object") {
    return h("ul", { class: "tree" }, Object.entries(value).map(([key, item]) =>
      h("li", null, h("span", { class: "k" }, key.replaceAll("_", " ")), h("div", { class: "v" }, tree(item)))));
  }
  return h("span", null, String(value));
}

export function setTitle(text) { document.title = `${text} · Pipeline Console`; }
