import { describe, it, expect } from "vitest";
import { parseSchedulePrefill, scheduleParamsFromBriefing } from "./schedulePrefill";

describe("scheduleParamsFromBriefing", () => {
  it("carries topics, cast and rounded-up duration", () => {
    const params = scheduleParamsFromBriefing({
      title: "Morning",
      duration_seconds: 301,
      cast_id: "cast-1",
      extra_data: { topic_ids: ["t1", "t2"] },
    });
    expect(params.get("topicIds")).toBe("t1,t2");
    expect(params.get("castId")).toBe("cast-1");
    expect(params.get("durationMinutes")).toBe("6");
    expect(params.has("name")).toBe(false);
  });

  it("falls back to the briefing title when there are no topics", () => {
    const params = scheduleParamsFromBriefing({ title: " Deep dive ", extra_data: {} });
    expect(params.get("name")).toBe("Deep dive");
    expect(params.has("topicIds")).toBe(false);
    expect(params.has("durationMinutes")).toBe(false);
    expect(params.has("castId")).toBe(false);
  });

  it("clamps duration to the form's 1-60 range", () => {
    const params = scheduleParamsFromBriefing({ duration_seconds: 4000, extra_data: {} });
    expect(params.get("durationMinutes")).toBe("60");
  });
});

describe("parseSchedulePrefill", () => {
  it("round-trips what the briefing page sends", () => {
    const params = scheduleParamsFromBriefing({
      duration_seconds: 600,
      cast_id: "c",
      extra_data: { topic_ids: ["a", "b"] },
    });
    expect(parseSchedulePrefill(params)).toEqual({
      topicIds: ["a", "b"],
      castId: "c",
      durationMinutes: 10,
      name: undefined,
    });
  });

  it("keeps the dashboard's topicIds/castId params working and ignores bad durations", () => {
    const prefill = parseSchedulePrefill(
      new URLSearchParams("topicIds=x,y&castId=z&durationMinutes=abc"),
    );
    expect(prefill).toEqual({ topicIds: ["x", "y"], castId: "z", durationMinutes: undefined, name: undefined });
  });

  it("returns empty defaults for no params", () => {
    expect(parseSchedulePrefill(new URLSearchParams())).toEqual({
      topicIds: [],
      castId: undefined,
      durationMinutes: undefined,
      name: undefined,
    });
  });
});
