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

export default function RecGrid({ rows }: { rows: Recommendation[] }) {
  return (
    <div className="ag-theme-quartz" style={{ width: "100%", height: 620 }}>
      <AgGridReact<Recommendation>
        rowData={rows}
        columnDefs={columns}
        defaultColDef={{ sortable: true, filter: true, resizable: true }}
        pagination
        paginationPageSize={25}
      />
    </div>
  );
}
