/** @type {import('tailwindcss').Config} */
// Colours resolve through CSS variables (see src/index.css) so the whole app
// switches theme by flipping one data-theme attribute — no duplicated classes.
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: v("surface"), page: v("surface-page"),
          sunken: v("surface-sunken"), raised: v("surface-raised"),
          inverse: v("surface-inverse"),
        },
        line: { DEFAULT: v("line"), strong: v("line-strong"), inverse: v("line-inverse") },
        ink: {
          DEFAULT: v("ink"), secondary: v("ink-secondary"),
          muted: v("ink-muted"), inverse: v("ink-inverse"),
        },
        brand: { DEFAULT: v("brand"), strong: v("brand-strong"), soft: v("brand-soft") },
        gain: { DEFAULT: v("gain"), soft: v("gain-soft") },
        loss: { DEFAULT: v("loss"), soft: v("loss-soft") },
        warn: { DEFAULT: v("warn"), soft: v("warn-soft") },
        info: { DEFAULT: v("info"), soft: v("info-soft") },
        series: { 1: v("series-1"), 2: v("series-2"), 3: v("series-3"), 4: v("series-4") },
        alpha: v("brand"),   // legacy alias
        dip: v("info"),
      },
      fontFamily: {
        sans: ['"Inter var"', "Inter", "ui-sans-serif", "system-ui",
               "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: { "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.02em" }] },
      boxShadow: {
        panel: "0 1px 2px 0 rgb(0 0 0 / 0.20)",
        raised: "0 4px 16px -4px rgb(0 0 0 / 0.35)",
        header: "0 1px 0 0 rgb(255 255 255 / 0.06)",
      },
      borderRadius: { panel: "0.625rem" },
    },
  },
  plugins: [],
};
