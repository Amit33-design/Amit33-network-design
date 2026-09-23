// Plotly, loaded only when a chart actually renders.
//
// Plotly was in the main bundle, so every page — including ones that draw no
// chart at all — shipped ~4 MB of charting code before painting anything. On
// a phone over cellular that is seconds of blank screen. Importing it lazily
// moves it into its own chunk, fetched the first time a chart mounts.
import { lazy, Suspense, type ComponentProps } from "react";

const Plot = lazy(() => import("react-plotly.js"));

export default function LazyPlot(props: ComponentProps<typeof Plot>) {
  const h = (props.layout as any)?.height ?? 240;
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center rounded bg-surface-sunken text-2xs text-ink-muted"
           style={{ height: h }}>
        Loading chart…
      </div>
    }>
      <Plot {...props} />
    </Suspense>
  );
}
