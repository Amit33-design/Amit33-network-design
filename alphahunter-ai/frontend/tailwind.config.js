/** @type {import('tailwindcss').Config} */
// Design tokens for an enterprise financial console. Semantics over raw hues:
// components reference roles (surface/border/ink/gain/loss), never hex, so the
// whole app re-themes from this one file.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surfaces — warm-neutral, not flat grey; each step is a real elevation.
        surface: {
          page: "#f7f7f5",   // app background
          DEFAULT: "#ffffff", // cards / panels
          sunken: "#f2f2ef",  // table headers, wells
          raised: "#ffffff",
          inverse: "#0d1b16", // header / dark chrome
        },
        // Hairline borders do the work heavy shadows used to.
        line: { DEFAULT: "#e6e6e1", strong: "#d3d3cc", inverse: "#1d3329" },
        // Ink hierarchy — three weights is enough, more is noise.
        ink: {
          DEFAULT: "#14201b",  // primary text
          secondary: "#5b6660",
          muted: "#8a938d",
          inverse: "#f4f6f5",
        },
        brand: { DEFAULT: "#1b7f4b", strong: "#0b3d2e", soft: "#e8f3ed" },
        // Directional semantics. Always paired with a sign/arrow in the UI, so
        // colour is never the only channel (red/green is CVD-weak by nature).
        gain: { DEFAULT: "#1b7f4b", soft: "#e8f3ed" },
        loss: { DEFAULT: "#c0392b", soft: "#fbecea" },
        warn: { DEFAULT: "#b7791f", soft: "#fdf4e3" },
        info: { DEFAULT: "#1f5fa6", soft: "#e9f0f8" },
        // Chart categorical order — validated with the dataviz palette checker
        // (lightness band, chroma floor, normal-vision ΔE, contrast all PASS).
        // Assigned in this fixed order, never cycled.
        series: { 1: "#1b7f4b", 2: "#c0392b", 3: "#6d28d9", 4: "#1f5fa6" },
        // Legacy aliases so existing markup keeps working during the migration.
        alpha: "#1b7f4b",
        dip: "#1f5fa6",
      },
      fontFamily: {
        sans: ['"Inter var"', "Inter", "ui-sans-serif", "system-ui",
               "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular",
               "Menlo", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.02em" }],
      },
      boxShadow: {
        // Enterprise UIs use hairlines + a whisper of elevation, not drop shadows.
        panel: "0 1px 2px 0 rgb(20 32 27 / 0.04)",
        raised: "0 2px 8px -2px rgb(20 32 27 / 0.10)",
        header: "0 1px 0 0 rgb(20 32 27 / 0.06)",
      },
      borderRadius: { panel: "0.625rem" },
    },
  },
  plugins: [],
};
