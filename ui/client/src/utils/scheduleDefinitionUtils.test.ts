import { describe, expect, it } from "vitest";
import {
  normalizeCronWeekDay,
  parseScheduleToState,
  summarizeCustomRecurrence,
  type CustomRecurrenceConfig,
} from "./scheduleDefinitionUtils";

describe("normalizeCronWeekDay", () => {
  it("accepts Sunday-first indices 0..6", () => {
    expect([0, 1, 2, 3, 4, 5, 6].map(String).map(normalizeCronWeekDay)).toEqual([
      0, 1, 2, 3, 4, 5, 6,
    ]);
  });

  it("normalizes 7 to Sunday (0)", () => {
    expect(normalizeCronWeekDay("7")).toBe(0);
  });

  it("accepts named cron weekdays", () => {
    expect(normalizeCronWeekDay("SUN")).toBe(0);
    expect(normalizeCronWeekDay("fri")).toBe(5);
  });

  it("returns null for out-of-range numeric values", () => {
    expect(normalizeCronWeekDay("8")).toBeNull();
    expect(normalizeCronWeekDay("-1")).toBeNull();
    expect(normalizeCronWeekDay("99")).toBeNull();
  });

  it("returns null for unknown tokens", () => {
    expect(normalizeCronWeekDay("FOO")).toBeNull();
    expect(normalizeCronWeekDay("")).toBeNull();
  });
});

describe("parseScheduleToState cron weekdays", () => {
  // Local noon keeps getDay() stable across runner timezones.
  const sundayNoon = new Date(2026, 7, 2, 12, 0, 0); // Sunday
  const mondayNoon = new Date(2026, 7, 3, 12, 0, 0); // Monday

  it("parses valid numeric weekday lists into 0..6", () => {
    const state = parseScheduleToState({
      timezone: "local",
      start_at: sundayNoon.toISOString(),
      cron_expression: "0 12 * * 1,3,5",
    });
    expect(state.recurrence).toBe("custom");
    expect(state.customConfig?.weekDays).toEqual([1, 3, 5]);
  });

  it("normalizes 7 to 0 when parsing weekDays", () => {
    const state = parseScheduleToState({
      timezone: "local",
      start_at: mondayNoon.toISOString(),
      cron_expression: "0 12 * * 7,1",
    });
    expect(state.recurrence).toBe("custom");
    expect(state.customConfig?.weekDays).toEqual([0, 1]);
  });

  it("treats a lone 7 as every_week when start day is Sunday", () => {
    expect(sundayNoon.getDay()).toBe(0);
    const state = parseScheduleToState({
      timezone: "local",
      start_at: sundayNoon.toISOString(),
      cron_expression: "0 12 * * 7",
    });
    expect(state.recurrence).toBe("every_week");
    expect(state.customConfig).toBeNull();
  });

  it("ignores invalid weekday tokens", () => {
    const state = parseScheduleToState({
      timezone: "local",
      start_at: sundayNoon.toISOString(),
      cron_expression: "0 12 * * 1,8,FOO,3",
    });
    expect(state.recurrence).toBe("custom");
    expect(state.customConfig?.weekDays).toEqual([1, 3]);
  });
});

describe("summarizeCustomRecurrence weekDays", () => {
  const base: CustomRecurrenceConfig = {
    repeatEvery: 1,
    unit: "week",
    weekDays: [],
    ends: "never",
  };

  it("labels valid weekdays", () => {
    expect(summarizeCustomRecurrence({ ...base, weekDays: [1, 5] })).toBe(
      "Weekly on MON, FRI",
    );
  });

  it("skips invalid weekday indices without throwing", () => {
    expect(summarizeCustomRecurrence({ ...base, weekDays: [1, 8, -1, 99] })).toBe(
      "Weekly on MON",
    );
  });

  it("omits the days suffix when no valid weekdays remain", () => {
    expect(summarizeCustomRecurrence({ ...base, weekDays: [8, 9] })).toBe("Weekly");
  });
});
