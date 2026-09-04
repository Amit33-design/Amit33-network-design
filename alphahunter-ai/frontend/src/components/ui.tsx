import type { ReactNode } from "react";

// Shared primitives. Every surface in the app is built from these, so spacing,
// borders and type hierarchy stay identical across pages — the thing that makes
// an app read as one product rather than a set of screens.

export function Panel({
  title, eyebrow, actions, children, className = "", padded = true,
}: {
  title?: ReactNode; eyebrow?: ReactNode; actions?: ReactNode;
  children: ReactNode; className?: string; padded?: boolean;
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 px-4 pt-3.5 pb-3 border-b border-line">
          <div className="min-w-0">
            {eyebrow && <div className="label-eyebrow mb-0.5">{eyebrow}</div>}
            {title && <h2 className="text-sm font-semibold text-ink leading-tight">{title}</h2>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </header>
      )}
      <div className={padded ? "p-4" : ""}>{children}</div>
    </section>
  );
}

/** A single KPI. Value is the hero; the label sits above it, quiet and small. */
export function StatTile({
  label, value, sub, tone = "neutral",
}: {
  label: string; value: ReactNode; sub?: ReactNode;
  tone?: "neutral" | "gain" | "loss" | "warn" | "info";
}) {
  const toneClass = {
    neutral: "text-ink", gain: "text-gain", loss: "text-loss",
    warn: "text-warn", info: "text-info",
  }[tone];
  return (
    <div className="panel px-4 py-3">
      <div className="label-eyebrow">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tracking-tight num ${toneClass}`}>
        {value}
      </div>
      {sub && <div className="mt-0.5 text-xs text-ink-muted num">{sub}</div>}
    </div>
  );
}

export function Badge({
  children, tone = "neutral", title,
}: {
  children: ReactNode;
  tone?: "neutral" | "gain" | "loss" | "warn" | "info" | "brand";
  title?: string;
}) {
  const map = {
    neutral: "bg-surface-sunken text-ink-secondary border-line",
    gain: "bg-gain-soft text-gain border-gain/20",
    loss: "bg-loss-soft text-loss border-loss/20",
    warn: "bg-warn-soft text-warn border-warn/20",
    info: "bg-info-soft text-info border-info/20",
    brand: "bg-brand-soft text-brand border-brand/20",
  }[tone];
  return (
    <span title={title}
          className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5
                      text-2xs font-medium whitespace-nowrap ${map}`}>
      {children}
    </span>
  );
}

/** Signed value with an arrow, so direction never depends on colour alone. */
export function Delta({ value, suffix = "%", digits = 2 }: {
  value?: number | null; suffix?: string; digits?: number;
}) {
  if (value == null) return <span className="text-ink-muted">—</span>;
  const up = value >= 0;
  return (
    <span className={`num font-medium ${up ? "text-gain" : "text-loss"}`}>
      {up ? "▲" : "▼"} {up ? "+" : ""}{value.toFixed(digits)}{suffix}
    </span>
  );
}

/** Content-shaped loading placeholder — steadier than a spinner. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-surface-sunken ${className}`} />;
}

export function SkeletonPanel({ rows = 4 }: { rows?: number }) {
  return (
    <div className="panel p-4 space-y-3">
      <Skeleton className="h-4 w-40" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({
  icon = "—", title, hint,
}: { icon?: ReactNode; title: string; hint?: ReactNode }) {
  return (
    <div className="text-center py-10">
      <div className="text-3xl mb-2 opacity-60">{icon}</div>
      <div className="font-medium text-ink">{title}</div>
      {hint && <div className="mt-1 text-sm text-ink-muted max-w-md mx-auto">{hint}</div>}
    </div>
  );
}

/** Chart series colours — the validated categorical order, fixed, never cycled. */
export const CHART = {
  gain: "#1b7f4b",
  loss: "#c0392b",
  series: ["#1b7f4b", "#c0392b", "#6d28d9", "#1f5fa6"],
  grid: "#e6e6e1",
  axis: "#8a938d",
  recessive: "#b9bfba",
};
