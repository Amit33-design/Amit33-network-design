import { AgGridReact } from "ag-grid-react";
import { Link } from "react-router-dom";
import type { ColDef } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";
import { useEffect, useState } from "react";
import type { Recommendation } from "../lib/types";
import { chartColors, getTheme, onThemeChange } from "../lib/theme";

function TickerCell({ value }: { value?: string }) {
  if (!value) return null;
  return (
    <Link
      to={`/analysis?ticker=${value}`}
      className="font-bold text-brand hover:underline"
      title={`Open the Analysis chart for ${value}`}
    >
      {value}
    </Link>
  );
}

const C = () => chartColors();

const num = (p: any) => (p.value == null ? "—" : Number(p.value).toFixed(2));
const pct = (p: any) => (p.value == null ? "—" : `${Number(p.value).toFixed(1)}%`);

const columns: ColDef<Recommendation>[] = [
  // Ticker links to the full Analysis chart for that symbol (client-side nav).
  { field: "ticker", pinned: "left", width: 95, cellRenderer: TickerCell },
  { field: "company", width: 170 },
  { field: "score", headerName: "AI Score", width: 105, sort: "desc",
    cellClassRules: { "font-bold": () => true },
    cellStyle: (p) => ({ color: p.value >= 70 ? C().gain : p.value >= 50 ? "#d9a441" : C().loss }) },
  { field: "quality_grade", headerName: "Quality", width: 95,
    cellStyle: (p) => ({
      fontWeight: 700,
      color: ["A", "B"].includes(p.value) ? C().gain : p.value === "C" ? "#d9a441" : C().loss,
    }) },
  { headerName: "Exp. Gain", field: "expected_gain_%", width: 110,
    valueFormatter: pct,
    cellStyle: () => ({ fontWeight: 700, color: C().gain }) },
  { headerName: "Analyst Upside", field: "analyst_upside_%", width: 130, valueFormatter: pct },
  { headerName: "Hist. Win%", width: 110,
    valueGetter: (p) => (p.data?.hist_trades ? p.data.hist_win_rate : null),
    valueFormatter: (p: any) => (p.value == null ? "—" : `${(p.value * 100).toFixed(0)}%`),
    cellStyle: (p) => ({ color: (p.value ?? 0) >= 0.6 ? C().gain : (p.value ?? 1) < 0.4 ? C().loss : C().ink }) },
  { field: "action", width: 115 },
  { headerName: "Setup", width: 110,
    valueGetter: (p) => ((p.data?.metrics as any)?.profile === "opportunity" ? "Pullback" : "Crash dip"),
    cellStyle: (p) => ({
      color: (p.data?.metrics as any)?.profile === "opportunity" ? "#d9a441" : C().loss,
      fontWeight: 600,
    }),
    tooltipValueGetter: (p) => ((p.data?.metrics as any)?.profile === "opportunity"
      ? "Broad pullback screen: >$1B name down on the week/month or oversold — lower conviction tier"
      : "Strict crash screen: down ≥5% day and ≥20% month — highest conviction tier") },
  { field: "confidence", width: 110 },
  { headerName: "RSI", width: 85, valueGetter: (p) => p.data?.metrics?.rsi, valueFormatter: num },
  { headerName: "Day %", width: 95, valueGetter: (p) => p.data?.metrics?.["day_%"], valueFormatter: pct },
  { headerName: "Month %", width: 100, valueGetter: (p) => p.data?.metrics?.["month_%"], valueFormatter: pct },
  { headerName: "Rev $B", width: 100, valueGetter: (p) => p.data?.metrics?.["revenue_$B"], valueFormatter: num },
  { headerName: "Entry", field: "entry", width: 90, valueFormatter: num },
  { headerName: "Stop", field: "stop_loss", width: 90, valueFormatter: num },
  { headerName: "Target", field: "target1", width: 95, valueFormatter: num },
  { headerName: "R:R", field: "risk_reward", width: 80, valueFormatter: num,
    cellStyle: (p) => ({ color: p.data?.rr_pass === false ? C().loss : C().ink,
                         fontWeight: p.data?.rr_pass === false ? 700 : 400 }) },
  { headerName: "Size", width: 130, sortable: false,
    valueGetter: (p) => p.data?.position
      ? `${p.data.position.shares} sh (~$${Math.round(p.data.position.value).toLocaleString()})`
      : "—",
    tooltipValueGetter: (p) => p.data?.position?.basis ?? "" },
  { headerName: "RS vs SPY", width: 110,
    valueGetter: (p) => p.data?.rel_strength?.vs_spy ?? null,
    valueFormatter: (p: any) => (p.value == null ? "—" : `${p.value >= 0 ? "+" : ""}${p.value}pp`),
    cellStyle: (p) => ({ color: (p.value ?? 0) > 0 ? C().gain : (p.value ?? 0) < 0 ? C().loss : C().ink }) },
  { headerName: "Sector", width: 150, valueGetter: (p) => p.data?.rel_strength?.sector ?? "—" },
  { headerName: "CSP Signal", width: 150, sortable: false,
    valueGetter: (p) => {
      const s = p.data?.csp_signal;
      if (!s?.active) return "—";
      return `💰 ${s.strength}${s.suggested_strike != null ? ` @$${s.suggested_strike}` : ""}`;
    },
    tooltipValueGetter: (p) => p.data?.csp_signal?.reason ?? "",
    cellStyle: (p) => ({
      color: p.data?.csp_signal?.active ? C().gain : C().axis,
      fontWeight: p.data?.csp_signal?.active ? 700 : 400,
    }) },
  { headerName: "Risk / Catalyst", width: 260, sortable: false,
    valueGetter: (p) => (p.data?.risk_flags || []).map((f: any) => f.text).join(" · "),
    cellStyle: (p) => {
      const flags = p.data?.risk_flags || [];
      const hasWarn = flags.some((f: any) => f.level === "warn");
      return { color: hasWarn ? C().loss : flags.length ? C().gain : C().axis, fontSize: "12px" };
    } },
  { headerName: "Covered Call", field: "covered_call", width: 230 },
  { headerName: "CSP", field: "cash_secured_put", width: 230 },
  { headerName: "Why", field: "reasoning", width: 520, wrapText: true, autoHeight: true },
];

function RecCard({ r }: { r: Recommendation }) {
  const m = r.metrics || {};
  const scoreColor = r.score >= 70 ? C().gain : r.score >= 50 ? "#d9a441" : C().loss;
  const warn = (r.risk_flags || []).some((f) => f.level === "warn");
  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between">
        <div>
          <Link to={`/analysis?ticker=${r.ticker}`} className="font-bold text-brand text-lg hover:underline">
            {r.ticker}
          </Link>
          <span className="ml-2 text-sm text-ink-secondary">{r.company}</span>
        </div>
        <div className="text-right">
          <div className="text-xl font-bold" style={{ color: scoreColor }}>{r.score}</div>
          <div className="text-xs text-ink-muted">
            {r.action} · {(m as any)?.profile === "opportunity" ? "pullback" : "crash dip"}
          </div>
        </div>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-sm">
        <Cell k="Quality" v={r.quality_grade ?? "—"} />
        <Cell k="Exp. Gain" v={r["expected_gain_%"] != null ? `${r["expected_gain_%"]}%` : "—"} accent={C().gain} />
        <Cell k="Conf." v={r.confidence} />
        <Cell k="Day" v={m["day_%"] != null ? `${m["day_%"]}%` : "—"} />
        <Cell k="Month" v={m["month_%"] != null ? `${m["month_%"]}%` : "—"} />
        <Cell k="RSI" v={m.rsi != null ? Number(m.rsi).toFixed(0) : "—"} />
      </div>
      {r.position && (
        <div className="mt-1 text-xs text-ink-secondary">
          Size: {r.position.shares} sh (~${Math.round(r.position.value).toLocaleString()},
          risking ${Math.round(r.position["risk_$"])})
          {r.rr_pass === false && <span className="text-loss font-semibold"> · R:R below floor</span>}
        </div>
      )}
      {r.csp_signal?.active && (
        <div className="mt-2 text-xs font-semibold text-gain bg-gain-soft rounded px-2 py-1">
          💰 CSP {r.csp_signal.strength}
          {r.csp_signal.suggested_strike != null ? ` · strike ≈ $${r.csp_signal.suggested_strike}` : ""}
        </div>
      )}
      {r.rel_strength?.vs_spy != null && (
        <div className={`mt-1 text-xs ${r.rel_strength.vs_spy >= 0 ? "text-brand" : "text-loss"}`}>
          {r.rel_strength.vs_spy >= 0 ? "▲" : "▼"} {Math.abs(r.rel_strength.vs_spy)}pp vs SPY (3mo)
          {r.rel_strength.sector ? ` · ${r.rel_strength.sector}` : ""}
        </div>
      )}
      {(r.risk_flags || []).length > 0 && (
        <div className={`mt-2 text-xs ${warn ? "text-loss" : "text-brand"}`}>
          {(r.risk_flags || []).map((f) => f.text).join(" · ")}
        </div>
      )}
      <div className="mt-2 text-xs text-ink-secondary">{r.reasoning}</div>
    </div>
  );
}

function Cell({ k, v, accent }: { k: string; v: any; accent?: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-ink-muted">{k}</div>
      <div className="font-semibold" style={accent ? { color: accent } : undefined}>{v}</div>
    </div>
  );
}

export default function RecGrid({ rows }: { rows: Recommendation[] }) {
  const [theme, setTheme] = useState(getTheme);
  useEffect(() => onThemeChange(() => setTheme(getTheme())), []);
  return (
    <>
      {/* Desktop / tablet: full AG Grid */}
      <div
        className={`${theme === "dark" ? "ag-theme-quartz-dark" : "ag-theme-quartz"} hidden md:block`}
        style={{ width: "100%", height: "70vh", minHeight: 420 }}
      >
        <AgGridReact<Recommendation>
          rowData={rows}
          columnDefs={columns}
          defaultColDef={{ sortable: true, filter: true, resizable: true }}
          pagination
          paginationPageSize={25}
        />
      </div>
      {/* Mobile: scrollable card list (the wide grid is unusable on phones) */}
      <div className="md:hidden space-y-3">
        {rows.length === 0 && <div className="text-ink-secondary">No matches.</div>}
        {rows.map((r) => <RecCard key={r.ticker} r={r} />)}
      </div>
    </>
  );
}
