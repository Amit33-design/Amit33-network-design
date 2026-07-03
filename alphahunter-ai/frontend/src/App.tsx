import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import RunScanButton from "./components/RunScanButton";
import Dashboard from "./pages/Dashboard";
import Opportunities from "./pages/Opportunities";
import Gainers from "./pages/Gainers";
import Analysis from "./pages/Analysis";
import Options from "./pages/Options";
import Portfolio from "./pages/Portfolio";
import Backtest from "./pages/Backtest";

const tabs = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/gainers", label: "Top Gainers" },
  { to: "/opportunities", label: "Opportunities" },
  { to: "/analysis", label: "Analysis" },
  { to: "/options", label: "Options" },
  { to: "/portfolio", label: "Portfolio" },
  { to: "/backtest", label: "Backtest" },
];

export default function App() {
  return (
    <div className="min-h-screen overflow-x-hidden">
      <header className="bg-ink text-white shadow">
        <div className="max-w-7xl mx-auto px-3 py-2 md:py-3 flex items-center gap-3 flex-wrap">
          <div className="font-bold text-lg tracking-tight">
            AlphaHunter <span className="text-alpha">AI</span>
          </div>
          {/* Run Scan is kept next to the logo so it's always visible/tappable
              on mobile, even when the nav wraps or scrolls. */}
          <div className="ml-auto order-2 md:order-3">
            <RunScanButton />
          </div>
          <nav className="order-3 md:order-2 w-full md:w-auto flex gap-1 overflow-x-auto no-scrollbar">
            {tabs.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded text-sm font-medium transition whitespace-nowrap ${
                    isActive ? "bg-alpha text-white" : "text-slate-200 hover:bg-white/10"
                  }`
                }
              >
                {t.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-6">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/gainers" element={<Gainers />} />
          <Route path="/opportunities" element={<Opportunities />} />
          <Route path="/analysis" element={<Analysis />} />
          <Route path="/options" element={<Options />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/backtest" element={<Backtest />} />
        </Routes>
      </main>
    </div>
  );
}
