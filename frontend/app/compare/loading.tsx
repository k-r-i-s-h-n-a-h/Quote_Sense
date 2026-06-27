import React from "react";

/** Shown while /compare compiles on first navigation in dev. */
export default function CompareLoading() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3 px-4">
      <div className="w-8 h-8 border-2 border-slate-200 border-t-[#c04a00] rounded-full animate-spin" />
      <p className="text-sm text-slate-500 text-center max-w-sm">
        Loading PDF compare… first open can take a minute in dev.
      </p>
    </div>
  );
}
