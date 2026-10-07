import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { dictionaries, supportedLanguages } from "../i18n";
import { AppPage } from "../pages/AppPage";
import { readFileSync } from "node:fs";

afterEach(cleanup);

describe("App landing page", () => {
  it("includes both actual simulator captures", () => {
    for (const name of ["feed", "digest"]) {
      const png = readFileSync(`public/app/${name}.png`);
      expect(png.subarray(1, 4).toString()).toBe("PNG");
      expect(png.readUInt32BE(16)).toBe(1206);
      expect(png.readUInt32BE(20)).toBe(2622);
    }
  });
  for (const lang of supportedLanguages) {
    it(`shows localized features and unavailable store buttons for ${lang}`, () => {
      render(<MemoryRouter initialEntries={[`/${lang}/app`]}><Routes><Route path="/:lang/app" element={<AppPage />} /></Routes></MemoryRouter>);
      const copy = dictionaries[lang].app;
      expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(copy.title);
      expect(screen.getByText(copy.proNote)).toBeTruthy();
      expect(screen.getByText(copy.languagesBody)).toBeTruthy();
      for (const store of ["App Store", "Google Play"]) {
        const buttons = screen.getAllByRole("button", { name: `Coming soon ${store}` });
        expect(buttons).toHaveLength(2);
        buttons.forEach((button) => expect((button as HTMLButtonElement).disabled).toBe(true));
      }
      expect(screen.queryByRole("link")).toBeNull();
      expect(screen.getByRole("img", { name: copy.feedAlt }).getAttribute("src")).toBe("/app/feed.png");
      expect(screen.getByRole("img", { name: copy.digestAlt }).getAttribute("src")).toBe("/app/digest.png");
      screen.getAllByRole("img").forEach((image) => {
        expect(image.getAttribute("width")).toBe("1206");
        expect(image.getAttribute("height")).toBe("2622");
      });
    });
  }
});
