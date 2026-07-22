/**
 * Date/time helpers – local-time display & timezone-safe ISO parsing.
 */

/**
 * Parse an ISO-8601 timestamp string ensuring it is treated as **UTC** even if
 * the server omits the trailing "Z" or "+00:00" offset.
 *
 * Without this fix `new Date("2024-07-22T09:00:00")` is interpreted as *local*
 * time, making every displayed time look like "same time" and throwing off the
 * relative "X ago" calculations by the user's UTC offset.
 */
export function parseUtcDate(iso: string): Date {
  if (
    !iso.endsWith("Z") &&
    !iso.includes("+") &&
    !/T\d{2}:\d{2}(:\d{2})?-/.test(iso)
  ) {
    return new Date(iso + "Z");
  }
  return new Date(iso);
}

/**
 * Convert a cron hour:minute expressed in `scheduleTz` (IANA, e.g. "UTC",
 * "America/New_York") to a `"HH:MM"` string in the user's **local** timezone.
 */
export function cronTimeToLocal(
  cronHour: number,
  cronMin: number,
  scheduleTz: string = "UTC",
): string {
  // 1. Create a probe date at cronHour:cronMin UTC
  const probe = new Date();
  probe.setUTCHours(cronHour, cronMin, 0, 0);

  // 2. See what that same instant looks like in scheduleTz
  const inTz = new Intl.DateTimeFormat("en-GB", {
    timeZone: scheduleTz,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(probe);

  const [tzH, tzM] = inTz.split(":").map(Number);

  // 3. Derive offset of scheduleTz from UTC (minutes)
  let offsetMin = (tzH * 60 + tzM) - (cronHour * 60 + cronMin);
  if (offsetMin > 720) offsetMin -= 1440;
  if (offsetMin < -720) offsetMin += 1440;

  // 4. The real UTC instant when it's cronHour:cronMin in scheduleTz
  const actualUtc = new Date(probe.getTime() - offsetMin * 60_000);

  // 5. Display in the user's local timezone
  return actualUtc.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}
