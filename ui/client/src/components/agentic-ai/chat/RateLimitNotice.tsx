import { Clock } from "lucide-react";
import { formatRetryDelay, parseRateLimitMessage } from "./helpers/rateLimit";

/**
 * Non-fatal notice shown when the model endpoint rejected a call with HTTP 429
 * (rate limit or quota). The run did not crash; the user can retry later.
 * Shows one clean sentence; raw gateway fields go in a collapsed section.
 */
export function RateLimitNotice({
  message,
  retryAfterSeconds,
}: {
  message: string;
  retryAfterSeconds?: number | null;
}) {
  const { summary, details } = parseRateLimitMessage(message);
  return (
    <div
      role="status"
      data-testid="rate-limit-notice"
      className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-100"
    >
      <Clock className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" aria-hidden />
      <div>
        <div className="font-medium">Rate limit reached</div>
        {summary && <div className="text-amber-100/80">{summary}</div>}
        {retryAfterSeconds != null && (
          <div className="mt-1 text-xs text-amber-200">
            You can retry in {formatRetryDelay(retryAfterSeconds)}
          </div>
        )}
        {details.length > 0 && (
          <details className="mt-1 text-xs text-amber-100/70" data-testid="rate-limit-details">
            <summary className="cursor-pointer select-none">Details</summary>
            <div className="mt-1 space-y-0.5">
              {details.map(([k, v]) => (
                <div key={k}>
                  <span className="text-amber-100/50">{k}: </span>
                  <span>{v}</span>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
