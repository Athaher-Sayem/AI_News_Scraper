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
    if (value !== undefined && value !== null && value !== "") {
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

export async function fetchStats() {
  return request("/stats/");
}

// Fetch several category filters at once and merge them newest-first. Used for
// sections whose collected articles carry more than one category label
// ("sports" and "sport", "latest" and "latest-news").
export async function fetchSection(categories, pageSize) {
  const results = await Promise.all(
    categories.map((category) => fetchArticles({ category, page_size: pageSize }))
  );
  const seen = new Set();
  const items = [];
  for (const result of results) {
    for (const item of result.items) {
      if (!seen.has(item.id)) {
        seen.add(item.id);
        items.push(item);
      }
    }
  }
  items.sort((a, b) => (b.scraped_date || "").localeCompare(a.scraped_date || ""));
  return items;
}
