/**
 * Day-of-week constants shared by recurrence/scheduling UI and cron parsing.
 */

/** Single-letter weekday labels for compact day-picker UI, Sunday-first. */
export const DAY_NAMES = ["S", "M", "T", "W", "T", "F", "S"];

/** Three-letter cron-style weekday names, Sunday-first (index 0 = Sunday). */
export const DAY_CRON_NAMES = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

/** Reverse lookup from a cron day-of-week name to its numeric index. */
export const CRON_TO_DAY: Record<string, number> = {
  SUN: 0, MON: 1, TUE: 2, WED: 3, THU: 4, FRI: 5, SAT: 6,
};
