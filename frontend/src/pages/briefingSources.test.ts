import { describe, it, expect } from "vitest";
import { groupSourcesByHost } from "./briefingSources";

describe("groupSourcesByHost", () => {
  it("groups sources under each host in found_by", () => {
    const sources = [
      { title: "A", url: "http://a", found_by: ["Alex"] },
      { title: "B", url: "http://b", found_by: ["Alex", "Sam"] },
      { title: "C", url: "http://c" }, // editor source, no host
    ];
    const groups = groupSourcesByHost(sources);
    expect(groups["Alex"].map((s) => s.title)).toEqual(["A", "B"]);
    expect(groups["Sam"].map((s) => s.title)).toEqual(["B"]);
    expect(groups["Alex"]).toHaveLength(2);
  });

  it("returns empty object when no host attribution present", () => {
    expect(groupSourcesByHost([{ title: "C", url: "http://c" }])).toEqual({});
  });
});
