import React from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
  className = "",
}: {
  eyebrow?: string;
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  meta?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col gap-5 md:flex-row md:items-end md:justify-between ${className}`}
    >
      <div className="min-w-0">
        {eyebrow ? <p className="qs-eyebrow">{eyebrow}</p> : null}
        <h1 className="mt-1 text-2xl md:text-[1.75rem] font-semibold tracking-tight text-stone-900">
          {title}
        </h1>
        {description ? (
          <div className="mt-2 max-w-2xl text-sm text-stone-500 leading-relaxed">
            {description}
          </div>
        ) : null}
        {meta ? <div className="mt-3 flex flex-wrap items-center gap-2">{meta}</div> : null}
      </div>
      {actions ? (
        <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>
      ) : null}
    </div>
  );
}
