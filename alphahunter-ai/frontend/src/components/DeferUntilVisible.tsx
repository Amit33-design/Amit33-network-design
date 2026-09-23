// Mounts its children only once they scroll near the viewport.
//
// Used for the Dashboard's score-distribution chart, which sits below every
// section. Mounting it eagerly pulled the ~4.9 MB Plotly chunk on every
// dashboard visit, for a chart most visits never scroll to. The placeholder
// holds the chart's height so nothing jumps when it arrives.
import { useEffect, useRef, useState, type ReactNode } from "react";

export default function DeferUntilVisible(
  { children, height = 240, margin = "300px" }:
  { children: ReactNode; height?: number; margin?: string },
) {
  const ref = useRef<HTMLDivElement>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (show || !ref.current) return;
    // No IntersectionObserver (very old browsers): just render.
    if (typeof IntersectionObserver === "undefined") { setShow(true); return; }
    const io = new IntersectionObserver(
      (entries) => { if (entries.some((e) => e.isIntersecting)) setShow(true); },
      { rootMargin: margin },
    );
    io.observe(ref.current);
    return () => io.disconnect();
  }, [show, margin]);

  return show
    ? <>{children}</>
    : <div ref={ref} style={{ height }} className="rounded bg-surface-sunken" aria-hidden="true" />;
}
