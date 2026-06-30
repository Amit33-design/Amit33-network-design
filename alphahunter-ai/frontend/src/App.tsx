import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import RunScanButton from "./components/RunScanButton";
import Dashboard from "./pages/Dashboard";
import Opportunities from "./pages/Opportunities";
import Options from "./pages/Options";
import Portfolio from "./pages/Portfolio";
import Backtest from "./pages/Backtest";

const tabs = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/opportunities", label: "Opportunities" },
  { to: "/options", label: "Options" },
  { to: "/portfolio", label: "Portfolio" },
  { to: "/backtest", label: "Backtest" },
];

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="bg-ink text-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-6">
          <div className="font-bold text-lg tracking-tight">
            AlphaHunter <span className="text-alpha">AI</span>
          </div>
          <nav className="flex gap-1">
            {tabs.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded text-sm font-medium transition ${
                    isActive ? "bg-alpha text-white" : "text-slate-200 hover:bg-white/10"
                  }`
                }
              >
                {t.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <RunScanButton />
            <span className="hidden md:inline text-xs text-slate-300">
              Research tool — not financial advice
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/opportunities" element={<Opportunities />} />
          <Route path="/options" element={<Options />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/backtest" element={<Backtest />} />
        </Routes>
      </main>
    </div>
  );
}
