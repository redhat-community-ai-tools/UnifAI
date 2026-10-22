import { Clock } from "lucide-react";
import { formatRetryDelay, type RateLimitNotice as Notice } from "./helpers/rateLimit";

/**
 * Non-fatal notice shown when the model endpoint rejected a call with HTTP 429
 * (rate limit or quota). The run did not crash; the user can retry later.
 */
export function RateLimitNotice({ notice }: { notice: Notice }) {
  return (
    <div
      role="status"
      data-testid="rate-limit-notice"
      className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-100"
    >
      <Clock className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" aria-hidden />
      <div>
        <div className="font-medium">Rate limit reached</div>
        <div className="text-amber-100/80">{notice.message.replace(/^Rate limit reached:\s*/, "")}</div>
        {notice.retryAfterSeconds !== null && (
          <div className="mt-1 text-xs text-amber-200">
            You can retry in {formatRetryDelay(notice.retryAfterSeconds)}.
          </div>
        )}
      </div>
    </div>
  );
}
