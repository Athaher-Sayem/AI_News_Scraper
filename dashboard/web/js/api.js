const KEY_STORE = "console.apiKey";
const authListeners = new Set();

function readKey() {
  try { return sessionStorage.getItem(KEY_STORE) || localStorage.getItem(KEY_STORE) || ""; } catch { return ""; }
}
let apiKey = readKey();

export const getKey = () => apiKey;
export function setKey(value, remember = false) {
  apiKey = (value || "").trim();
  try {
    sessionStorage.removeItem(KEY_STORE);
    localStorage.removeItem(KEY_STORE);
    if (apiKey) (remember ? localStorage : sessionStorage).setItem(KEY_STORE, apiKey);
  } catch { /* storage unavailable: key lives for this page load only */ }
}
export const isKeyRemembered = () => { try { return !!localStorage.getItem(KEY_STORE); } catch { return false; } };
export const onAuthRequired = (fn) => { authListeners.add(fn); return () => authListeners.delete(fn); };

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.status = status; this.code = code; this.details = details;
  }
}

function buildUrl(path, params) {
  if (!params) return path;
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === "" || value == null) continue;
    for (const item of Array.isArray(value) ? value : [value]) query.append(key, item);
  }
  const text = query.toString();
  return text ? `${path}?${text}` : path;
}

export async function api(path, { method = "GET", body, params, signal, allow = [] } = {}) {
  const headers = { Accept: "application/json" };
  if (apiKey) headers["X-API-Key"] = apiKey;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch(buildUrl(path, params), { method, headers, signal, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(0, "network", "Cannot reach the server. Is it running?");
  }
  let payload = null;
  try { payload = await response.json(); } catch { /* non-JSON body */ }
  if (response.ok || allow.includes(response.status)) return payload ? payload.data : null;
  const err = payload && payload.error;
  if (response.status === 401) authListeners.forEach((fn) => fn());
  throw new ApiError(response.status, err?.code || "http_error", err?.message || `Request failed (${response.status})`, err?.details);
}

export async function download(path, filename) {
  const headers = apiKey ? { "X-API-Key": apiKey } : {};
  let response;
  try { response = await fetch(path, { headers }); } catch { throw new ApiError(0, "network", "Cannot reach the server."); }
  if (!response.ok) {
    if (response.status === 401) authListeners.forEach((fn) => fn());
    throw new ApiError(response.status, "download_failed", `Download failed (${response.status})`);
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url; link.download = filename;
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
