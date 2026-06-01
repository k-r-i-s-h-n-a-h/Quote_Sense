"use client";

const STEPS = [
  "Reading vendor PDFs with AI…",
  "Extracting line items and pricing…",
  "Saving quotes to the database…",
  "Building comparison matrix…",
  "Calculating baseline averages…",
  "Generating expert recommendation…",
  "Almost there — finalizing your dashboard…",
];

type Props = {
  messageIndex: number;
};

export default function CompareLoadingPanel({ messageIndex }: Props) {
  const message = STEPS[messageIndex % STEPS.length];

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
          <p className="text-xs text-blue-700/80">
            Comparing multiple quotes can take couple of minutes — please keep this tab open.
          </p>
        </div>

        <div className="flex w-full max-w-xs gap-1.5 pt-1">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full transition-colors duration-300 ${
                i === messageIndex % STEPS.length ? "bg-blue-600" : "bg-blue-200"
              }`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
