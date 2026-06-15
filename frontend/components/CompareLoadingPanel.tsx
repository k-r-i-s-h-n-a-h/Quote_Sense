"use client";

type Props = {
  message: string;
  processed: number;
  total: number;
};

export default function CompareLoadingPanel({ message, processed, total }: Props) {
  const hasCount = total > 0;
  const pct = hasCount ? Math.min(100, Math.round((processed / total) * 100)) : 0;

  return (
    <div
      className="mt-5 rounded-xl border border-blue-200 bg-gradient-to-b from-blue-50 to-white p-6 shadow-sm"
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="relative flex h-14 w-14 items-center justify-center">
          <div className="absolute h-14 w-14 animate-spin rounded-full border-[3px] border-blue-200 border-t-blue-600" />
          <div className="absolute h-9 w-9 animate-ping rounded-full bg-blue-400/20" />
          <span className="text-xl" aria-hidden>
            📊
          </span>
        </div>

        <div className="space-y-1">
          <p className="text-sm font-semibold text-blue-900">{message}</p>
          {hasCount && (
            <p className="text-xs font-medium text-blue-700">
              {processed} of {total} quotes processed
            </p>
          )}
          <p className="text-xs text-blue-700/80">
            This can take a minute or two — you can keep this tab open and watch the progress.
          </p>
        </div>

        {hasCount && (
          <div className="w-full max-w-xs pt-1">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-blue-200">
              <div
                className="h-full rounded-full bg-blue-600 transition-all duration-500 ease-out"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
