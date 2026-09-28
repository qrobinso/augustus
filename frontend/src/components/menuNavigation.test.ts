import { describe, it, expect } from "vitest";
import { nextMenuIndex } from "./menuNavigation";

describe("nextMenuIndex", () => {
  const none = [false, false, false];

  it("moves down and wraps to the top", () => {
    expect(nextMenuIndex(none, 0, "ArrowDown")).toBe(1);
    expect(nextMenuIndex(none, 2, "ArrowDown")).toBe(0);
  });

  it("moves up and wraps to the bottom", () => {
    expect(nextMenuIndex(none, 1, "ArrowUp")).toBe(0);
    expect(nextMenuIndex(none, 0, "ArrowUp")).toBe(2);
  });

  it("starts from the ends when nothing is focused", () => {
    expect(nextMenuIndex(none, -1, "ArrowDown")).toBe(0);
    expect(nextMenuIndex(none, -1, "ArrowUp")).toBe(2);
  });

  it("skips disabled items, including for Home/End", () => {
    const disabled = [true, false, true, false, true];
    expect(nextMenuIndex(disabled, 1, "ArrowDown")).toBe(3);
    expect(nextMenuIndex(disabled, 3, "ArrowDown")).toBe(1);
    expect(nextMenuIndex(disabled, 1, "ArrowUp")).toBe(3);
    expect(nextMenuIndex(disabled, -1, "Home")).toBe(1);
    expect(nextMenuIndex(disabled, -1, "End")).toBe(3);
  });

  it("returns -1 when nothing is focusable", () => {
    expect(nextMenuIndex([], -1, "ArrowDown")).toBe(-1);
    expect(nextMenuIndex([true, true], 0, "Home")).toBe(-1);
  });
});
