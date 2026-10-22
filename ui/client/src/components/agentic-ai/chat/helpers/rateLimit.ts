/** Human-readable retry delay, e.g. "45s" or "2min 5s". */
export function formatRetryDelay(seconds: number): string {
  const s = Math.max(0, Math.ceil(seconds));
  if (s < 60) return `${s}s`;
  const minutes = Math.floor(s / 60);
  const rest = s % 60;
  return rest === 0 ? `${minutes}min` : `${minutes}min ${rest}s`;
}
