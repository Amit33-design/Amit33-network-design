import { AgGridReact } from "ag-grid-react";
import type { ColDef } from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";
import type { Recommendation } from "../lib/types";

const num = (p: any) => (p.value == null ? "—" : Number(p.value).toFixed(2));
const pct = (p: any) => (p.value == null ? "—" : `${Number(p.value).toFixed(1)}%`);

const columns: ColDef<Recommendation>[] = [
  { field: "ticker", pinned: "left", width: 95, cellClass: "font-bold text-alpha" },
  { field: "company", width: 170 },
  { field: "score", headerName: "AI Score", width: 105, sort: "desc",
    cellClassRules: { "font-bold": () => true },
    cellStyle: (p) => ({ color: p.value >= 70 ? "#1b7f4b" : p.value >= 50 ? "#b7791f" : "#c0392b" }) },
  { field: "quality_grade", headerName: "Quality", width: 95,
    cellStyle: (p) => ({
      fontWeight: 700,
      color: ["A", "B"].includes(p.value) ? "#1b7f4b" : p.value === "C" ? "#b7791f" : "#c0392b",
    }) },
  { headerName: "Exp. Gain", field: "expected_gain_%", width: 110,
    valueFormatter: pct,
    cellStyle: { fontWeight: 700, color: "#1b7f4b" } },
  { headerName: "Analyst Upside", field: "analyst_upside_%", width: 130, valueFormatter: pct },
  { headerName: "Hist. Win%", width: 110,
    valueGetter: (p) => (p.data?.hist_trades ? p.data.hist_win_rate : null),
    valueFormatter: (p: any) => (p.value == null ? "—" : `${(p.value * 100).toFixed(0)}%`),
    cellStyle: (p) => ({ color: (p.value ?? 0) >= 0.6 ? "#1b7f4b" : (p.value ?? 1) < 0.4 ? "#c0392b" : "#334155" }) },
  { field: "action", width: 115 },
  { field: "confidence", width: 110 },
  { headerName: "RSI", width: 85, valueGetter: (p) => p.data?.metrics?.rsi, valueFormatter: num },
  { headerName: "Day %", width: 95, valueGetter: (p) => p.data?.metrics?.["day_%"], valueFormatter: pct },
  { headerName: "Month %", width: 100, valueGetter: (p) => p.data?.metrics?.["month_%"], valueFormatter: pct },
  { headerName: "Rev $B", width: 100, valueGetter: (p) => p.data?.metrics?.["revenue_$B"], valueFormatter: num },
  { headerName: "Entry", field: "entry", width: 90, valueFormatter: num },
  { headerName: "Stop", field: "stop_loss", width: 90, valueFormatter: num },
  { headerName: "Target", field: "target1", width: 95, valueFormatter: num },
  { headerName: "R:R", field: "risk_reward", width: 80, valueFormatter: num },
  { headerName: "RS vs SPY", width: 110,
    valueGetter: (p) => p.data?.rel_strength?.vs_spy ?? null,
    valueFormatter: (p: any) => (p.value == null ? "—" : `${p.value >= 0 ? "+" : ""}${p.value}pp`),
    cellStyle: (p) => ({ color: (p.value ?? 0) > 0 ? "#1b7f4b" : (p.value ?? 0) < 0 ? "#c0392b" : "#334155" }) },
  { headerName: "Sector", width: 150, valueGetter: (p) => p.data?.rel_strength?.sector ?? "—" },
  { headerName: "Risk / Catalyst", width: 260, sortable: false,
    valueGetter: (p) => (p.data?.risk_flags || []).map((f: any) => f.text).join(" · "),
    cellStyle: (p) => {
      const flags = p.data?.risk_flags || [];
      const hasWarn = flags.some((f: any) => f.level === "warn");
      return { color: hasWarn ? "#c0392b" : flags.length ? "#1b7f4b" : "#94a3b8", fontSize: "12px" };
    } },
  { headerName: "Covered Call", field: "covered_call", width: 230 },
  { headerName: "CSP", field: "cash_secured_put", width: 230 },
  { headerName: "Why", field: "reasoning", width: 520, wrapText: true, autoHeight: true },
];

function RecCard({ r }: { r: Recommendation }) {
  const m = r.metrics || {};
  const scoreColor = r.score >= 70 ? "#1b7f4b" : r.score >= 50 ? "#b7791f" : "#c0392b";
  const warn = (r.risk_flags || []).some((f) => f.level === "warn");
  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <div className="flex items-center justify-between">
        <div>
          <span className="font-bold text-alpha text-lg">{r.ticker}</span>
          <span className="ml-2 text-sm text-slate-500">{r.company}</span>
        </div>
        <div className="text-right">
          <div className="text-xl font-bold" style={{ color: scoreColor }}>{r.score}</div>
          <div className="text-xs text-slate-400">{r.action}</div>
        </div>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-sm">
        <Cell k="Quality" v={r.quality_grade ?? "—"} />
        <Cell k="Exp. Gain" v={r["expected_gain_%"] != null ? `${r["expected_gain_%"]}%` : "—"} accent="#1b7f4b" />
        <Cell k="Conf." v={r.confidence} />
        <Cell k="Day" v={m["day_%"] != null ? `${m["day_%"]}%` : "—"} />
        <Cell k="Month" v={m["month_%"] != null ? `${m["month_%"]}%` : "—"} />
        <Cell k="RSI" v={m.rsi != null ? Number(m.rsi).toFixed(0) : "—"} />
      </div>
      {r.rel_strength?.vs_spy != null && (
        <div className={`mt-1 text-xs ${r.rel_strength.vs_spy >= 0 ? "text-alpha" : "text-red-600"}`}>
          {r.rel_strength.vs_spy >= 0 ? "▲" : "▼"} {Math.abs(r.rel_strength.vs_spy)}pp vs SPY (3mo)
          {r.rel_strength.sector ? ` · ${r.rel_strength.sector}` : ""}
        </div>
      )}
      {(r.risk_flags || []).length > 0 && (
        <div className={`mt-2 text-xs ${warn ? "text-red-600" : "text-alpha"}`}>
          {(r.risk_flags || []).map((f) => f.text).join(" · ")}
        </div>
      )}
      <div className="mt-2 text-xs text-slate-500">{r.reasoning}</div>
    </div>
  );
}

function Cell({ k, v, accent }: { k: string; v: any; accent?: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-slate-400">{k}</div>
      <div className="font-semibold" style={accent ? { color: accent } : undefined}>{v}</div>
    </div>
  );
}

export default function RecGrid({ rows }: { rows: Recommendation[] }) {
  return (
    <>
      {/* Desktop / tablet: full AG Grid */}
      <div className="ag-theme-quartz hidden md:block" style={{ width: "100%", height: "70vh", minHeight: 420 }}>
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
        {rows.length === 0 && <div className="text-slate-500">No matches.</div>}
        {rows.map((r) => <RecCard key={r.ticker} r={r} />)}
      </div>
    </>
  );
}
