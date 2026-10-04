import { describe, expect, it } from "vitest";

import {
  excerpt,
  formatDate,
  paragraphs,
  relativeTime,
  resolveImage,
  resolveSourceLink,
} from "./utils.js";

describe("resolveImage", () => {
  it("resolves publisher-relative paths against the article URL", () => {
    expect(resolveImage("/sites/x.jpg", "https://www.thedailystar.net/news/a")).toBe(
      "https://www.thedailystar.net/sites/x.jpg"
    );
  });

  it("keeps absolute http(s) URLs", () => {
    expect(resolveImage("https://cdn.example/a.jpg", "https://example.com/x")).toBe(
      "https://cdn.example/a.jpg"
    );
  });

  it("rejects empty and non-http values", () => {
    expect(resolveImage("", "https://example.com")).toBeNull();
    expect(resolveImage("javascript:alert(1)", "https://example.com")).toBeNull();
    expect(resolveImage(null, "https://example.com")).toBeNull();
  });
});

describe("resolveSourceLink", () => {
  it("accepts http(s) URLs with a hostname", () => {
    expect(resolveSourceLink("https://example.com/a")).toBe("https://example.com/a");
  });

  it("rejects dangerous, protocol-relative, or malformed URLs", () => {
    for (const value of ["javascript:alert(1)", "data:text/html,x", "//example.com/x", "nope", "", null]) {
      expect(resolveSourceLink(value)).toBeNull();
    }
  });
});

describe("formatting helpers", () => {
  it("formats an ISO date", () => {
    expect(formatDate("2026-10-04T12:00:00Z")).toMatch(/\d{1,2} October 2026/);
  });

  it("returns empty for missing dates", () => {
    expect(formatDate("")).toBe("");
  });

  it("describes recent times relatively", () => {
    expect(relativeTime(new Date(Date.now() - 2 * 3600 * 1000).toISOString())).toBe("2 HOURS");
    expect(relativeTime(new Date().toISOString())).toBe("just now");
  });

  it("splits paragraphs and truncates excerpts", () => {
    expect(paragraphs("one\n\ntwo\n\n\nthree")).toEqual(["one", "two", "three"]);
    expect(paragraphs("")).toEqual([]);
    const long = Array.from({ length: 40 }, (_, i) => `w${i}`).join(" ");
    expect(excerpt(long, 10).endsWith("…")).toBe(true);
    expect(excerpt("short text", 10)).toBe("short text");
  });
});
