import { useEffect, useState } from "react";
import { getTheme, toggleTheme, onThemeChange, type Theme } from "../lib/theme";

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(getTheme);
  useEffect(() => onThemeChange(() => setTheme(getTheme())), []);
  return (
    <button
      onClick={() => setTheme(toggleTheme())}
      title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      aria-label="Toggle colour theme"
      className="rounded-md border border-white/10 bg-white/5 px-2 py-1.5 text-sm
                 text-ink-inverse/70 hover:text-ink-inverse hover:bg-white/10 transition-colors"
    >
      {theme === "dark" ? "☾" : "☀"}
    </button>
  );
}
