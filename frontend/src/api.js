// Thin client for the Django JSON API.
//
// Successful responses use {"data": ...}; list responses carry
// {"data": {"items": [...], "meta": {...}}}. Errors use
// {"error": {"code", "message"}} with a matching HTTP status.

const BASE = "/api/v1";

async function request(path) {
  let response;
  try {
    response = await fetch(`${BASE}${path}`, { headers: { Accept: "application/json" } });
  } catch (error) {
    throw new Error("Could not reach the news API. Is the Django server running?");
  }
  let payload = null;
  try {
    payload = await response.json();
  } catch (error) {
    payload = null;
  }
  if (!response.ok) {
    const message = payload?.error?.message || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return payload?.data;
}

function toQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    if (Array.isArray(value)) {
      value.filter(Boolean).forEach((item) => query.append(key, item));
    } else {
      query.set(key, value);
    }
  });
  const text = query.toString();
  return text ? `?${text}` : "";
}

export async function fetchArticles(params = {}) {
  const data = await request(`/articles/${toQuery(params)}`);
  return { items: data.items || [], meta: data.meta || {} };
}

export async function fetchArticle(id) {
  return request(`/articles/${id}/`);
}

export async function fetchRelated(id) {
  const data = await request(`/articles/${id}/related/`);
  return data.items || [];
}

export async function fetchCategories() {
  const data = await request("/categories/");
  return data.items || [];
}

export async function fetchSources() {
  const data = await request("/sources/");
  return data.items || [];
}

export async function fetchTrending() {
  const data = await request("/trending/");
  return data.items || [];
}

// Fire-and-forget view beacon; failures never affect the page.
export async function recordView(id) {
  try {
    await fetch(`${BASE}/articles/${id}/view/`, { method: "POST" });
  } catch (error) {
    /* telemetry only */
  }
}

export async function fetchStats() {
  return request("/stats/");
}

// Sections carry more than one category label ("sports" and "sport",
// "latest" and "latest-news"); the API accepts repeated category params and
// matches any of them.
export async function fetchSection(categories, pageSize) {
  const params = { page_size: pageSize };
  if (categories.length) params.category = categories;
  const { items } = await fetchArticles(params);
  return items;
}
