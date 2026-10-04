// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api.js", () => ({ fetchTrending: vi.fn() }));

import { fetchTrending } from "../api.js";
import TrendingPage from "./TrendingPage.jsx";

function article(id, title, views) {
  return {
    id,
    title,
    category: "business",
    source: "Fixture",
    url: `https://example.com/${id}`,
    image_url: "",
    content: "Some collected source content for the story.",
    scraped_date: new Date().toISOString(),
    views,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <TrendingPage />
    </MemoryRouter>
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("TrendingPage", () => {
  it("renders ranked stories with view counts and article links", async () => {
    fetchTrending.mockResolvedValue([article(1, "First trending story", 5), article(2, "Second trending story", 2)]);
    renderPage();

    expect(await screen.findByText("First trending story")).toBeTruthy();
    expect(screen.getByText("5 views")).toBeTruthy();
    expect(screen.getByText("2 views")).toBeTruthy();
    expect(screen.getByText("1")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();

    const link = screen.getByRole("link", { name: "First trending story" });
    expect(link.getAttribute("href")).toBe("/article/1");
  });

  it("shows an empty state when there are no views", async () => {
    fetchTrending.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText(/No trending stories yet/)).toBeTruthy();
  });

  it("shows an error state when the request fails", async () => {
    fetchTrending.mockRejectedValue(new Error("service offline"));
    renderPage();
    expect(await screen.findByText(/service offline/)).toBeTruthy();
  });
});
