import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchArticle, fetchArticles } from "./api.js";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function jsonResponse(body, { ok = true, status = 200 } = {}) {
  return { ok, status, json: async () => body };
}

describe("fetchArticles", () => {
  it("sends repeated category params and unwraps the data envelope", async () => {
    const mock = vi.fn().mockResolvedValue(
      jsonResponse({ data: { items: [{ id: 1 }], meta: { total: 1 } } })
    );
    globalThis.fetch = mock;

    const result = await fetchArticles({ category: ["sports", "sport"], page_size: 5, empty: "" });
    const url = mock.mock.calls[0][0];

    expect(url).toContain("/api/v1/articles/?");
    expect(url).toContain("category=sports");
    expect(url).toContain("category=sport");
    expect(url).not.toContain("empty=");
    expect(result.items).toEqual([{ id: 1 }]);
    expect(result.meta.total).toBe(1);
  });
});

describe("error handling", () => {
  it("surfaces the API error message", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(jsonResponse({ error: { code: "invalid", message: "bad request" } }, { ok: false, status: 400 }));

    await expect(fetchArticle(5)).rejects.toThrow("bad request");
  });

  it("reports an unreachable API", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("network down"));

    await expect(fetchArticles()).rejects.toThrow(/Could not reach the news API/);
  });
});
