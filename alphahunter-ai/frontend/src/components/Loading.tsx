export function Loading({ label = "Scanning the market…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-ink-secondary py-10">
      <div className="h-4 w-4 rounded-full border-2 border-alpha border-t-transparent animate-spin" />
      {label}
    </div>
  );
}

/** Shows what went wrong in the user's terms.
 *
 *  This used to print "Couldn't reach the backend — start it with uvicorn
 *  backend.main:app" for EVERY failure, including a mistyped ticker. That is
 *  a developer's note leaking into a product, and it pointed users at a
 *  command that has nothing to do with the deployed site.
 */
export function ErrorBox({
  error, onRetry,
}: {
  error: unknown;
  onRetry?: () => void;
}) {
  const api = error as { status?: number; code?: string; message?: string; ticker?: string };
  const status = api?.status;
  const isUserError = status === 404 || status === 422;

  const title = isUserError
    ? (api.code === "invalid_ticker" ? "That isn't a valid symbol"
       : api.code === "insufficient_history" ? "Not enough price history"
       : "Ticker not found")
    : status === 502 || status === 503
      ? "Data service is temporarily down"
      : "Something went wrong";

  const detail = api?.message
    || (isUserError ? "Check the symbol and try again."
        : "Please try again in a moment.");

  const tone = isUserError
    ? "bg-warn-soft border-warn/30 text-warn"
    : "bg-loss-soft border-loss/30 text-loss";

  return (
    <div className={`${tone} border rounded-panel p-4 text-sm`}>
      <div className="font-semibold">{title}</div>
      <div className="mt-1">{detail}</div>
      {!isUserError && onRetry && (
        <button onClick={onRetry}
                className="mt-2 border border-current rounded px-2 py-1 text-xs font-medium hover:opacity-80">
          Retry
        </button>
      )}
    </div>
  );
}
