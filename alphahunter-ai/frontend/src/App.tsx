import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import RunScanButton from "./components/RunScanButton";
import TickerSearch from "./components/TickerSearch";
import ThemeToggle from "./components/ThemeToggle";
import Dashboard from "./pages/Dashboard";
import Opportunities from "./pages/Opportunities";
import Analysis from "./pages/Analysis";
import Options from "./pages/Options";
import Portfolio from "./pages/Portfolio";

const tabs = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/opportunities", label: "Opportunities" },
  { to: "/analysis", label: "Analysis" },
  { to: "/options", label: "Options" },
  { to: "/portfolio", label: "Portfolio" },
];

export default function App() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-surface-page">
      {/* App chrome: sticky so the nav and search stay reachable while a long
          analysis page scrolls — standard for a console people work in. */}
      <header className="sticky top-0 z-30 bg-surface-inverse text-ink-inverse shadow-header">
        <div className="max-w-[1400px] mx-auto px-3 sm:px-5">
          <div className="flex items-center gap-4 h-14">
            <div className="font-semibold text-[15px] tracking-tight whitespace-nowrap">
              AlphaHunter <span className="text-brand">AI</span>
            </div>

            {/* Primary nav — desktop. Active state is an underline rail, not a
                filled pill, so the bar stays quiet and scannable. */}
            <nav className="hidden md:flex items-stretch gap-1 h-full">
              {tabs.map((t) => (
                <NavLink
                  key={t.to}
                  to={t.to}
                  className={({ isActive }) =>
                    `relative flex items-center px-3 text-sm font-medium transition-colors
                     ${isActive
                       ? "text-ink-inverse after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:bg-brand after:rounded-full"
                       : "text-ink-inverse/60 hover:text-ink-inverse"}`
                  }
                >
                  {t.label}
                </NavLink>
              ))}
            </nav>

            <div className="ml-auto flex items-center gap-2">
              <TickerSearch />
              <ThemeToggle />
              <RunScanButton />
            </div>
          </div>

          {/* Mobile nav rail */}
          <nav className="md:hidden flex gap-1 pb-2 overflow-x-auto no-scrollbar">
            {tabs.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap transition-colors
                   ${isActive ? "bg-brand text-white" : "text-ink-inverse/70 hover:bg-white/10"}`
                }
              >
                {t.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-3 sm:px-5 py-5 sm:py-6">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/opportunities" element={<Opportunities />} />
          <Route path="/analysis" element={<Analysis />} />
          <Route path="/options" element={<Options />} />
          <Route path="/portfolio" element={<Portfolio />} />
          {/* Retired tabs redirect to the dashboard */}
          <Route path="/gainers" element={<Navigate to="/dashboard" replace />} />
          <Route path="/backtest" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>

      <footer className="max-w-[1400px] mx-auto px-3 sm:px-5 pb-8 pt-2">
        <p className="text-2xs text-ink-muted">
          AlphaHunter AI — research tooling, not financial advice. Signals are
          generated from public market data and measured against SPY.
        </p>
      </footer>
    </div>
  );
}
