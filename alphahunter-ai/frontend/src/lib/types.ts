// Mirrors the backend StockRecommendation payload (scoring/composite.py).
export interface Recommendation {
  ticker: string;
  company: string;
  score: number;
  action: string;
  quality_grade?: string;
  "expected_gain_%"?: number | null;
  "analyst_upside_%"?: number | null;
  hist_win_rate?: number | null;
  "hist_avg_return_%"?: number | null;
  hist_trades?: number | null;
  risk_flags?: { level: "warn" | "info" | "good"; text: string }[];
  rel_strength?: {
    vs_spy: number | null;
    vs_sector: number | null;
    sector: string | null;
    sector_etf: string | null;
  } | null;
  csp_signal?: {
    active: boolean;
    strength: "strong" | "moderate" | null;
    suggested_strike: number | null;
    idea: string | null;
    reason: string;
  } | null;
  position?: {
    shares: number;
    value: number;
    "risk_$": number;
    basis: string;
  } | null;
  rr_pass?: boolean;
  subscores: Record<string, number>;
  weights: Record<string, number>;
  entry: number | null;
  stop_loss: number | null;
  target1: number | null;
  target2: number | null;
  risk_reward: number | null;
  covered_call: string | null;
  cash_secured_put: string | null;
  confidence: "High" | "Medium" | "Low";
  criteria_passed: string[];
  criteria_failed: string[];
  metrics: Record<string, any>;
  reasoning: string;
}

export interface ScanResponse {
  count: number;
  results: Recommendation[];
}

export interface PortfolioRow {
  ticker: string;
  quantity?: number;
  cost_basis?: number;
  price?: number;
  market_value?: number;
  gain_loss?: number;
  "gain_loss_%"?: number;
  scores?: Record<string, number>;
  overall_score?: number;
  recommendation?: string;
  reason?: string;
  covered_call?: string | null;
  cash_secured_put?: string | null;
  error?: string;
}

export interface PortfolioResponse {
  summary: {
    market_value: number;
    cost_basis: number;
    gain_loss: number;
    "gain_loss_%": number;
    positions: number;
  };
  positions: PortfolioRow[];
}
