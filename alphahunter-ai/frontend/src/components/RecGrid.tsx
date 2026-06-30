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
  { field: "score", headerName: "AI Score", width: 110, sort: "desc",
    cellClassRules: { "font-bold": () => true },
    cellStyle: (p) => ({ color: p.value >= 70 ? "#1b7f4b" : p.value >= 50 ? "#b7791f" : "#c0392b" }) },
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
