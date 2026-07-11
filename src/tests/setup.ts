import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach } from "vitest";
import { cleanup } from "@testing-library/react";

class MatchMediaMock implements MediaQueryList {
  matches = false;
  media: string;
  onchange = null;
  addListener = () => undefined;
  removeListener = () => undefined;
  addEventListener = () => undefined;
  removeEventListener = () => undefined;
  dispatchEvent = () => true;

  constructor(media: string) {
    this.media = media;
  }
}

beforeEach(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => new MatchMediaMock(query),
  });
  window.localStorage.clear();
  window.location.hash = "#/";
});

afterEach(() => cleanup());
