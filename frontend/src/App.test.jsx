// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("./api.js", () => ({
  fetchArticles: vi.fn(async () => ({ items: [], meta: {} })),
  fetchArticle: vi.fn(async () => ({
    id: 1, title: "A story", category: "business", source: "Fixture",
    content: "Collected source content.", url: "https://example.com/1", image_url: "",
  })),
  fetchRelated: vi.fn(async () => []),
  fetchSection: vi.fn(async () => []),
  fetchCategories: vi.fn(async () => []),
  fetchSources: vi.fn(async () => []),
  fetchTrending: vi.fn(async () => []),
  fetchStats: vi.fn(async () => ({})),
  recordView: vi.fn(),
}));

import App from "./App.jsx";

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>
  );
}

afterEach(cleanup);

describe("App routing", () => {
  it("renders the About page", () => {
    renderAt("/about");
    expect(screen.getByRole("heading", { level: 1, name: "About" })).toBeTruthy();
  });

  it("renders the Contact page", () => {
    renderAt("/contact");
    expect(screen.getByRole("heading", { level: 1, name: "Contact" })).toBeTruthy();
  });

  it("renders the not-found page for unknown routes", () => {
    renderAt("/definitely-not-a-route");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeTruthy();
  });

  it("renders Trending through its route", async () => {
    renderAt("/trending");
    expect(await screen.findByText(/No trending stories yet/)).toBeTruthy();
  });
});
