/**
 * Rate-limit / quota notices.
 *
 * The backend reports an HTTP 429 from the model endpoint as plain text of the
 * form `[rate_limited retry_after=<seconds>] <message>` (the `retry_after`
 * attribute is omitted when the endpoint sent no `Retry-After`). This keeps the
 * notice intact through text-only channels such as the final answer.
 */
export interface RateLimitNotice {
  message: string;
  /** Seconds to wait before retrying, when known. */
  retryAfterSeconds: number | null;
}

const RATE_LIMIT_RE = /\[rate_limited(?:\s+retry_after=(\d+(?:\.\d+)?))?\]\s*([\s\S]*)$/;

export function parseRateLimitNotice(text: string | undefined | null): RateLimitNotice | null {
  if (!text) return null;
  const match = RATE_LIMIT_RE.exec(text);
  if (!match) return null;
  return {
    message: match[2].trim(),
    retryAfterSeconds: match[1] !== undefined ? parseFloat(match[1]) : null,
  };
}

export function formatRetryDelay(seconds: number): string {
  const s = Math.max(0, Math.ceil(seconds));
  if (s < 60) return `${s}s`;
  const minutes = Math.floor(s / 60);
  const rest = s % 60;
  return rest === 0 ? `${minutes}min` : `${minutes}min ${rest}s`;
}
