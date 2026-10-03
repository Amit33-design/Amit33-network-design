// Walk-forward test of the Analysis verdict: node scripts/verdict-eval.mjs DATA.json
// DATA.json comes from `python -m backend.verdict_data`. Writes
// public/verdict_eval.json, which the Analysis page shows beside the verdict.
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { walk, summarise, WINDOW, HORIZON, STEP } from "../../../api/_verdict_eval.js";

const data = JSON.parse(readFileSync(process.argv[2], "utf8"));
const spy = data.SPY;
if (!spy) throw new Error("SPY missing from the data file");
const rows = [];
for (const [t, s] of Object.entries(data)) {
  if (t === "SPY") continue;
  for (const r of walk(s, spy)) rows.push({ ticker: t, ...r });
}
const out = {
  generated: new Date().toISOString().slice(0, 19) + "Z",
  params: { window_bars: WINDOW, horizon_sessions: HORIZON, step_sessions: STEP },
  tickers: Object.keys(data).length - 1,
  period: rows.length ? { from: rows.map((r) => r.date).sort()[0], to: rows.map((r) => r.date).sort().at(-1) } : null,
  ...summarise(rows),
  caveat: "Today's listed stocks only (delisted names are missing), so absolute returns are flattered; "
    + "the comparison between verdicts is the reliable part.",
};
const path = fileURLToPath(new URL("../public/verdict_eval.json", import.meta.url));
writeFileSync(path, JSON.stringify(out, null, 1) + "\n");
console.log(`verdict eval: ${out.cases} cases over ${out.dates} dates, ${out.tickers} tickers`);
for (const [v, s] of Object.entries(out.by_verdict))
  console.log(`  ${v.padEnd(10)} n=${s.cases} alpha=${s["avg_alpha_%"]}pp t=${s.alpha_t_by_date} beat=${s.beat_spy_rate}`);
console.log(`  score IC ${out.score_ic} (t ${out.score_ic_t}); Buy - Sell ${out.buy_minus_sell_pp}pp`);
