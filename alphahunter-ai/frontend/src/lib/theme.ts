// Theme state. Dark is the default (trading consoles are read for hours);
// the choice persists per device and is applied via a data-theme attribute so
// every token in index.css switches at once.
const KEY = "alphahunter.theme";
const EVENT = "theme-changed";
export type Theme = "dark" | "light";

export function getTheme(): Theme {
  try {
    return localStorage.getItem(KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function applyTheme(t: Theme) {
  document.documentElement.setAttribute("data-theme", t);
  try { localStorage.setItem(KEY, t); } catch { /* private mode */ }
  window.dispatchEvent(new Event(EVENT));
}

export function toggleTheme(): Theme {
  const next: Theme = getTheme() === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}

export function onThemeChange(fn: () => void): () => void {
  window.addEventListener(EVENT, fn);
  return () => window.removeEventListener(EVENT, fn);
}

/** Chart colours per theme — both sets validated with the palette checker. */
export function chartColors(theme: Theme = getTheme()) {
  return theme === "dark"
    ? {
        gain: "#31a05c", loss: "#e2574c",
        series: ["#31a05c", "#e2574c", "#a06ef0", "#3a86c8"],
        grid: "#232c29", axis: "#6c7a74", ink: "#9aa8a2", recessive: "#3d4a45",
      }
    : {
        gain: "#1b7f4b", loss: "#c0392b",
        series: ["#1b7f4b", "#c0392b", "#6d28d9", "#1f5fa6"],
        grid: "#e6e6e1", axis: "#8a938d", ink: "#5b6660", recessive: "#b9bfba",
      };
}

/** Shared Plotly layout so every chart matches the surface it sits on. */
export function plotTheme(theme: Theme = getTheme()) {
  const c = chartColors(theme);
  return {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { family: "Inter, system-ui, sans-serif", size: 11, color: c.ink },
    xaxis: { gridcolor: c.grid, linecolor: c.grid, zeroline: false },
    yaxis: { gridcolor: c.grid, linecolor: c.grid, zeroline: false },
  };
}
