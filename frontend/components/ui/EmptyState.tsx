import React from "react";

export function EmptyState({
  title,
  description,
  action,
  icon,
  className = "",
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`qs-card px-6 py-12 text-center ${className}`}
      role="status"
    >
      {icon ? (
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-stone-100 text-stone-500">
          {icon}
        </div>
      ) : null}
      <h3 className="text-base font-semibold text-stone-900 tracking-tight">
        {title}
      </h3>
      {description ? (
        <p className="mx-auto mt-2 max-w-md text-sm text-stone-500 leading-relaxed">
          {description}
        </p>
      ) : null}
      {action ? <div className="mt-5 flex justify-center">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title,
  description,
  action,
  className = "",
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`qs-card border-[var(--warning-border)] bg-[var(--warning-soft)] px-6 py-6 ${className}`}
      role="alert"
    >
      <h3 className="text-sm font-semibold text-stone-900">{title}</h3>
      {description ? (
        <p className="mt-1 text-sm text-stone-600 leading-relaxed">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
