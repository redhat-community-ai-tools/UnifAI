/** Human-readable retry delay, e.g. "45s" or "2min 5s". */
export function formatRetryDelay(seconds: number): string {
  const s = Math.max(0, Math.ceil(seconds));
  if (s < 60) return `${s}s`;
  const minutes = Math.floor(s / 60);
  const rest = s % 60;
  return rest === 0 ? `${minutes}min` : `${minutes}min ${rest}s`;
}

export interface ParsedRateLimitMessage {
  /** Human sentence, without the title prefix, retry hint or raw gateway fields. */
  summary: string;
  /** Raw `key=value` fields found in the message, kept for a collapsed details section. */
  details: Array<[string, string]>;
}

/**
 * Split a rate-limit message into a clean sentence and its raw `key=value`
 * fields. Drops the "Rate limit reached:" prefix and any trailing
 * "Please retry in Ns." / "You can retry in Ns." hint, since the retry delay is
 * rendered separately from `retry_after`.
 */
export function parseRateLimitMessage(message: string): ParsedRateLimitMessage {
  let text = (message || "").replace(/^\s*Rate limit reached:?\s*/i, "");
  const details: Array<[string, string]> = [];
  text = text.replace(/\b([A-Za-z_][\w.-]*)=([^\s,;)\]]+)/g, (_m, k: string, v: string) => {
    details.push([k, v]);
    return "";
  });
  text = text
    .replace(/\b(?:please|you can)\s+retry\s+(?:again\s+)?in\s+(?:\d+(?:\.\d+)?\s*(?:seconds?|secs?|minutes?|mins?|s|m)\b\s*)+\.?/gi, "")
    .replace(/\(\s*[,;\s]*\)/g, "")
    .replace(/\[\s*[,;\s]*\]/g, "")
    .replace(/[\s,;:]+([.])/g, "$1")
    .replace(/\s{2,}/g, " ")
    .replace(/[\s,;:]+$/, "")
    .trim();
  return { summary: text, details };
}
