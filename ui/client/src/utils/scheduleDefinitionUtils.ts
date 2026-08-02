/**
 * Pure domain logic for the scheduled-prompt recurrence UI: translating between
 * the friendly recurrence picker state (`RecurrenceOption` / `CustomRecurrenceConfig`)
 * and the cron/interval-based `ScheduleDefinitionInput` the backend understands.
 */
import { format } from "date-fns";
import { type ScheduleDefinitionInput } from "@/api/schedules";
import { parseISODuration } from "@/utils/dateTimeUtils";
import { DAY_CRON_NAMES, CRON_TO_DAY } from "@/constants/dateConstants";

export type RecurrenceOption =
  | "does_not_repeat"
  | "every_15m"
  | "every_hour"
  | "every_day"
  | "every_week"
  | "every_month"
  | "custom";

export interface CustomRecurrenceConfig {
  repeatEvery: number;
  unit: "minute" | "hour" | "day" | "week" | "month";
  weekDays: number[];
  ends: "never" | "on_date" | "after_count";
  endDate?: Date;
  endCount?: number;
}

// "Allow All" (unbounded concurrent runs) is intentionally omitted -- disallowed
// server-side until a proper concurrency policy is designed.
export const OVERLAP_OPTIONS = [
  { value: "skip", label: "Skip", description: "If previous run is still executing, skip this tick" },
  { value: "buffer_one", label: "Buffer One", description: "Queue one pending tick, skip further overlaps" },
  { value: "cancel_other", label: "Cancel Other", description: "Cancel the running session, start a new one" },
];

// date-fns' `format` always reads local getters. When `startDate` represents a
// UTC calendar day (timezone === "UTC", always a UTC-midnight instant here),
// formatting with local getters rolls the displayed day back by one for viewers
// west of UTC -- so we format a "fake local" date built from the UTC fields instead.
export function formatInMode(date: Date, timezone: "UTC" | "local", fmtStr: string): string {
  const target =
    timezone === "UTC"
      ? new Date(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), date.getUTCHours(), date.getUTCMinutes())
      : date;
  return format(target, fmtStr);
}

export function getRecurrenceLabels(startDate: Date, timezone: "UTC" | "local"): Record<RecurrenceOption, string> {
  const dayName = formatInMode(startDate, timezone, "EEEE");
  const ordinalDate = formatInMode(startDate, timezone, "do");
  return {
    does_not_repeat: "Does not repeat",
    every_15m: "Every 15 minutes",
    every_hour: "Hourly",
    every_day: "Daily",
    every_week: `Weekly on ${dayName}`,
    every_month: `Monthly on the ${ordinalDate}`,
    custom: "Custom...",
  };
}

export function summarizeCustomRecurrence(config: CustomRecurrenceConfig): string {
  const { repeatEvery, unit, weekDays } = config;
  const n = repeatEvery;
  if (unit === "minute") return n === 1 ? "Every minute" : `Every ${n} minutes`;
  if (unit === "hour") return n === 1 ? "Every hour" : `Every ${n} hours`;
  if (unit === "day") return n === 1 ? "Daily" : `Every ${n} days`;
  if (unit === "month") return n === 1 ? "Monthly" : `Every ${n} months`;
  if (unit === "week") {
    const dayLabels = weekDays.sort().map((d) => DAY_CRON_NAMES[d].slice(0, 3));
    const daysPart = dayLabels.length > 0 ? ` on ${dayLabels.join(", ")}` : "";
    return n === 1 ? `Weekly${daysPart}` : `Every ${n} weeks${daysPart}`;
  }
  return "Custom";
}

export function buildScheduleDefinition(
  startDate: Date,
  timezone: "UTC" | "local",
  recurrence: RecurrenceOption,
  customConfig?: CustomRecurrenceConfig | null,
  overlapPolicy?: string,
): ScheduleDefinitionInput {
  const isUTC = timezone === "UTC";
  const tz = isUTC ? "UTC" : Intl.DateTimeFormat().resolvedOptions().timeZone;
  const startAt = startDate.toISOString();
  const M = isUTC ? startDate.getUTCMinutes() : startDate.getMinutes();
  const H = isUTC ? startDate.getUTCHours() : startDate.getHours();
  const dayOfMonth = isUTC ? startDate.getUTCDate() : startDate.getDate();
  const dayOfWeek = isUTC ? startDate.getUTCDay() : startDate.getDay();

  const base: ScheduleDefinitionInput = {
    timezone: tz,
    start_at: startAt,
    // Explicit nulls so partial schedule.update merges can clear prior ends policy.
    end_at: null,
    remaining_actions: null,
  };
  if (overlapPolicy && overlapPolicy !== "skip") {
    base.overlap_policy = overlapPolicy;
  }

  if (recurrence === "custom" && customConfig) {
    const result = { ...base };

    const { repeatEvery: n, unit, weekDays, ends, endDate, endCount } = customConfig;
    switch (unit) {
      case "minute":
        result.interval = `PT${n}M`;
        break;
      case "hour":
        result.interval = `PT${n}H`;
        break;
      case "day":
        if (n === 1) {
          result.cron_expression = `${M} ${H} * * *`;
        } else {
          result.interval = `PT${n * 24}H`;
        }
        break;
      case "week":
        if (n === 1 && weekDays.length > 0) {
          const cronDays = weekDays.sort().map((d) => DAY_CRON_NAMES[d]).join(",");
          result.cron_expression = `${M} ${H} * * ${cronDays}`;
        } else {
          result.interval = `PT${n * 7 * 24}H`;
        }
        break;
      case "month":
        result.cron_expression = `${M} ${H} ${dayOfMonth} * *`;
        break;
    }

    if (ends === "on_date" && endDate) {
      result.end_at = endDate.toISOString();
      result.remaining_actions = null;
    } else if (ends === "after_count" && endCount) {
      result.remaining_actions = endCount;
      result.end_at = null;
    }

    if (!result.interval && !result.cron_expression) {
      result.interval = `PT${n}H`;
    }
    return result;
  }

  switch (recurrence) {
    case "does_not_repeat":
      return { ...base, interval: "PT1H", remaining_actions: 1 };
    case "every_15m":
      return { ...base, interval: "PT15M" };
    case "every_hour":
      return { ...base, interval: "PT1H" };
    case "every_day":
      return { ...base, cron_expression: `${M} ${H} * * *` };
    case "every_week":
      return { ...base, cron_expression: `${M} ${H} * * ${dayOfWeek}` };
    case "every_month":
      return { ...base, cron_expression: `${M} ${H} ${dayOfMonth} * *` };
    default:
      return { ...base, interval: "PT1H", remaining_actions: 1 };
  }
}

/** True when two instants fall in the same clock minute (UI time precision is HH:mm). */
export function isSameMinute(a: Date, b: Date): boolean {
  return Math.floor(a.getTime() / 60_000) === Math.floor(b.getTime() / 60_000);
}

/**
 * Resolve a picker HH:mm start into a concrete instant.
 * If the chosen minute is already slightly in the past, bump by `graceMs`
 * so Save at the current minute still succeeds (seconds stay system-side).
 */
export function resolveStartDateTime(combined: Date, now = new Date(), graceMs = 20_000): Date | null {
  if (combined.getTime() > now.getTime()) {
    return combined;
  }
  if (combined.getTime() > now.getTime() - graceMs) {
    return new Date(now.getTime() + graceMs);
  }
  return null;
}

export function parseScheduleToState(schedule: ScheduleDefinitionInput): {
  recurrence: RecurrenceOption;
  startDate: Date;
  timezone: "UTC" | "local";
  customConfig: CustomRecurrenceConfig | null;
  overlapPolicy: string;
} {
  const startDate = schedule.start_at ? new Date(schedule.start_at) : new Date();
  const timezone: "UTC" | "local" = schedule.timezone === "UTC" ? "UTC" : "local";
  const overlapPolicy = schedule.overlap_policy || "skip";

  const endsConfig = {
    ends: "never" as "never" | "on_date" | "after_count",
    endDate: undefined as Date | undefined,
    endCount: undefined as number | undefined,
  };
  if (schedule.end_at) {
    endsConfig.ends = "on_date";
    endsConfig.endDate = new Date(schedule.end_at);
  } else if (schedule.remaining_actions != null && schedule.remaining_actions !== 1) {
    endsConfig.ends = "after_count";
    endsConfig.endCount = schedule.remaining_actions;
  }

  if (schedule.remaining_actions === 1) {
    return { recurrence: "does_not_repeat", startDate, timezone, customConfig: null, overlapPolicy };
  }

  if (schedule.interval) {
    if (schedule.interval === "PT15M" && !schedule.end_at && schedule.remaining_actions == null) {
      return { recurrence: "every_15m", startDate, timezone, customConfig: null, overlapPolicy };
    }
    if (schedule.interval === "PT1H" && !schedule.end_at && schedule.remaining_actions == null) {
      return { recurrence: "every_hour", startDate, timezone, customConfig: null, overlapPolicy };
    }
    const parsed = parseISODuration(schedule.interval);
    if (parsed) {
      let unit = parsed.unit as CustomRecurrenceConfig["unit"];
      let repeatEvery = parsed.value;
      if (unit === "hour" && repeatEvery >= 24 && repeatEvery % 24 === 0) {
        unit = "day";
        repeatEvery = repeatEvery / 24;
      }
      if (unit === "day" && repeatEvery >= 7 && repeatEvery % 7 === 0) {
        unit = "week";
        repeatEvery = repeatEvery / 7;
      }
      return {
        recurrence: "custom",
        startDate,
        timezone,
        customConfig: { repeatEvery, unit, weekDays: [], ...endsConfig },
        overlapPolicy,
      };
    }
  }

  if (schedule.cron_expression) {
    const parts = schedule.cron_expression.split(" ");
    if (parts.length === 5) {
      const hasEnds = schedule.end_at || (schedule.remaining_actions != null && schedule.remaining_actions !== 1);

      if (parts[2] === "*" && parts[3] === "*" && parts[4] === "*" && !hasEnds) {
        return { recurrence: "every_day", startDate, timezone, customConfig: null, overlapPolicy };
      }
      if (parts[2] === "*" && parts[3] === "*" && parts[4] !== "*") {
        const dayParts = parts[4].split(",");
        if (dayParts.length === 1 && !hasEnds) {
          const dayNum = parseInt(dayParts[0], 10);
          if (!isNaN(dayNum) && dayNum === startDate.getDay()) {
            return { recurrence: "every_week", startDate, timezone, customConfig: null, overlapPolicy };
          }
          const cronDay = CRON_TO_DAY[dayParts[0]];
          if (cronDay !== undefined && cronDay === startDate.getDay()) {
            return { recurrence: "every_week", startDate, timezone, customConfig: null, overlapPolicy };
          }
        }
        const weekDays = dayParts.map((d) => {
          const num = parseInt(d, 10);
          if (!isNaN(num)) return num;
          return CRON_TO_DAY[d.toUpperCase()] ?? -1;
        }).filter((d) => d >= 0);
        return {
          recurrence: "custom",
          startDate,
          timezone,
          customConfig: { repeatEvery: 1, unit: "week", weekDays, ...endsConfig },
          overlapPolicy,
        };
      }
      if (parts[2] !== "*" && parts[3] === "*" && parts[4] === "*" && !hasEnds) {
        return { recurrence: "every_month", startDate, timezone, customConfig: null, overlapPolicy };
      }
      if (parts[2] !== "*" && parts[3] === "*" && parts[4] === "*" && hasEnds) {
        return {
          recurrence: "custom",
          startDate,
          timezone,
          customConfig: { repeatEvery: 1, unit: "month", weekDays: [], ...endsConfig },
          overlapPolicy,
        };
      }
      if (parts[2] === "*" && parts[3] === "*" && parts[4] === "*" && hasEnds) {
        return {
          recurrence: "custom",
          startDate,
          timezone,
          customConfig: { repeatEvery: 1, unit: "day", weekDays: [], ...endsConfig },
          overlapPolicy,
        };
      }
    }
  }

  return { recurrence: "does_not_repeat", startDate, timezone, customConfig: null, overlapPolicy };
}
