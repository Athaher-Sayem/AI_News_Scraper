// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import Layout from "./Layout.jsx";

function renderLayout() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<p>home content</p>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

afterEach(cleanup);

describe("Layout", () => {
  it("renders section, trending and static navigation links", () => {
    renderLayout();
    const nav = screen.getByRole("navigation", { name: "Sections" });
    for (const label of ["Latest", "Business", "Opinion", "Sports", "Culture", "Lifestyle", "World", "Trending", "About", "Contact"]) {
      expect(within(nav).getByRole("link", { name: label })).toBeTruthy();
    }
  });

  it("exposes a skip link, a main landmark and a search box", () => {
    renderLayout();
    expect(screen.getByRole("link", { name: "Skip to content" }).getAttribute("href")).toBe("#main");
    expect(document.querySelector("main#main")).toBeTruthy();
    const search = screen.getByRole("search");
    expect(within(search).getByRole("textbox")).toBeTruthy();
    expect(screen.getByText("home content")).toBeTruthy();
  });
});
