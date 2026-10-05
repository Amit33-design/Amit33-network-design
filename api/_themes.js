// Sector & theme map: what kind of business a ticker is, what drives that kind
// of business, and which ETF measures how the market currently feels about it.
//
// The thesis used to be built from the price chart alone, so NVDA, XOM and a
// regional bank got the same sentences with different numbers in them. The
// investment case for a stock starts with what it sells and what moves that
// market; the chart only says whether now is a good moment.
//
// Everything here is STRUCTURAL — the durable drivers and risks of a business
// type — never a claim about this quarter. Current sentiment is not written
// here; it is MEASURED live from the theme's ETF (see _story.js). Resolution
// order: an explicit ticker list, then Yahoo's industry, then its sector.
// Industry matching is FIRST HIT, so narrow themes must come before broad ones:
// REITs before consumer (/retail/ would take "REIT - Retail") and healthcare
// (/health/ would take "REIT - Healthcare Facilities").
//
// `growth` is the kind of growth the business has:
//   secular    — demand grows with a long-running shift, cycles are dips in it
//   cyclical   — demand follows the economy / a commodity price
//   defensive  — steady demand, bond-like, rate-sensitive
//   speculative — early, binary or unprofitable; outcomes are wide

export const THEMES = [
  {
    key: "ai_compute", name: "AI data-center compute & networking", etf: "SMH", growth: "secular",
    tickers: ["NVDA", "AMD", "AVGO", "MRVL", "ARM", "TSM", "MU", "SMCI", "DELL", "ANET", "VRT",
              "CRDO", "ALAB", "COHR", "CIEN", "LITE", "HPE", "WDC", "STX", "SNDK", "NBIS",
              "CRWV", "CLS", "FN", "AMKR", "EQIX", "DLR", "APLD", "IREN"],
    scope: "Sells the chips, servers, memory, networking or capacity that AI models are trained and run on.",
    drivers: ["Hyperscaler and sovereign capex on AI clusters",
              "Inference demand growing as AI moves into everyday products",
              "Each GPU generation pulls through more networking, memory and power gear"],
    risks: ["A pause in hyperscaler capex (\"digestion\") hits orders fast",
            "Few very large customers; export controls on China",
            "Valuations price in years of growth — misses are punished hard"],
  },
  {
    key: "ai_power", name: "Power for AI data centers", etf: "XLU", growth: "secular",
    tickers: ["VST", "CEG", "NRG", "TLN", "GEV", "OKLO", "SMR", "BE", "NNE", "LEU"],
    industries: [/independent power/, /utilities.*renewable/],
    scope: "Generates or builds the electricity supply that data centers are now competing for.",
    drivers: ["Data-center electricity demand after a decade of flat US load",
              "Long-term power deals with tech companies, including for nuclear",
              "Scarce firm generation lets existing plants reprice"],
    risks: ["Power prices and regulation set the upside",
            "A slowdown in AI build-outs removes the premium quickly",
            "New nuclear is years out and capital-intensive"],
  },
  {
    key: "grid", name: "Electrification & grid build-out", etf: "XLI", growth: "secular",
    tickers: ["ETN", "PWR", "HUBB", "EME", "MTZ", "POWL", "NVT", "GNRC", "AYI", "PRIM", "FIX"],
    industries: [/electrical equipment/],
    scope: "Supplies the transformers, switchgear, wiring and contracting behind new power demand.",
    drivers: ["Data centers, reshoring and EVs all need grid upgrades",
              "Multi-year order backlogs give visibility",
              "Utilities are raising transmission spending"],
    risks: ["Tied to industrial and construction cycles",
            "Backlog-driven stocks re-rate sharply if orders slow",
            "Supply-chain and labour constraints cap delivery"],
  },
  {
    key: "hyperscale", name: "Cloud platforms & AI hyperscalers", etf: "QQQ", growth: "secular",
    tickers: ["MSFT", "GOOGL", "GOOG", "AMZN", "META", "ORCL", "AAPL"],
    scope: "Runs the platforms — cloud, search, social, devices — that both fund and sell AI.",
    drivers: ["Cloud revenue re-accelerating on AI workloads",
              "Enormous cash flow funds buybacks and AI capex",
              "Distribution to billions of users"],
    risks: ["AI capex is a cost before it is revenue — margins can compress",
            "Antitrust and regulatory action",
            "Heavy index weight: they move with the market"],
  },
  {
    key: "cyber", name: "Cybersecurity", etf: "CIBR", growth: "secular",
    tickers: ["CRWD", "PANW", "ZS", "FTNT", "NET", "S", "OKTA", "CYBR", "TENB", "QLYS", "RPD", "CHKP"],
    scope: "Protects networks, endpoints, identities and cloud workloads.",
    drivers: ["Security spend is among the last budgets cut",
              "Consolidation onto platforms favours the leaders",
              "AI raises both attack volume and the value of defence"],
    risks: ["Premium valuations", "A single breach or outage can damage trust (and guidance)",
            "Price competition as platforms bundle"],
  },
  {
    key: "quantum", name: "Quantum computing", etf: "QTUM", growth: "speculative",
    tickers: ["IONQ", "RGTI", "QBTS", "QUBT", "ARQQ"],
    scope: "Builds quantum hardware or software that is still pre-commercial.",
    drivers: ["Government and big-tech research funding", "Milestone announcements move the whole group"],
    risks: ["Little revenue; valuation rests on a technology not yet proven at scale",
            "Dilution from equity raises", "Extreme volatility in both directions"],
  },
  {
    key: "space", name: "Space economy", etf: "ITA", growth: "speculative",
    tickers: ["RKLB", "ASTS", "LUNR", "PL", "RDW", "SPCE", "BKSY", "FLY"],
    scope: "Launches, builds or operates spacecraft and satellite services.",
    drivers: ["Falling launch costs open new markets", "Defense and government contracts",
              "Satellite connectivity and Earth-observation demand"],
    risks: ["Launch failures and schedule slips", "Cash burn and dilution",
            "Contract-driven lumpy revenue"],
  },
  {
    key: "crypto", name: "Crypto & digital assets", etf: "IBIT", growth: "speculative",
    tickers: ["COIN", "MSTR", "MARA", "RIOT", "CLSK", "HUT", "BITF", "GLXY", "CRCL", "BMNR"],
    scope: "Earns from crypto prices, trading or mining.",
    drivers: ["Bitcoin price and ETF inflows", "Regulatory clarity widening institutional use"],
    risks: ["Moves with crypto prices, often with leverage", "Regulatory reversal",
            "Miners: halving cuts rewards; power costs"],
  },
  {
    key: "glp1", name: "Obesity & metabolic drugs", etf: "XLV", growth: "secular",
    tickers: ["LLY", "NVO", "VKTX"],
    scope: "Makes GLP-1 and related drugs for obesity and diabetes.",
    drivers: ["One of the largest new drug markets in decades", "Label expansion into heart, kidney and sleep indications"],
    risks: ["Pricing pressure and government negotiation", "Supply and competition from new entrants",
            "High expectations already in the price"],
  },
  {
    key: "semis", name: "Semiconductors", etf: "SMH", growth: "cyclical",
    industries: [/semiconductor/],
    scope: "Designs or makes chips for phones, PCs, cars, industry and data centers.",
    drivers: ["Chip content rising in every device and vehicle", "Inventory restocking after downturns"],
    risks: ["Deeply cyclical: inventory gluts cut orders fast", "China exposure and export rules",
            "Heavy capital spending for manufacturers"],
  },
  {
    key: "hydrogen", name: "Hydrogen & fuel cells", etf: "ICLN", growth: "speculative",
    tickers: ["PLUG", "FCEL", "BLDP"],
    scope: "Makes hydrogen fuel cells, electrolyzers or hydrogen supply for power and transport.",
    drivers: ["Decarbonisation policy and clean-hydrogen subsidies",
              "Demand for backup and off-grid power, including at data centers"],
    risks: ["Mostly unprofitable: cash burn and repeated equity raises",
            "Depends on subsidies and policy that can change",
            "Hydrogen cost still well above fossil alternatives"],
  },
  {
    key: "re_tech", name: "Real-estate tech & brokerage", etf: "ITB", growth: "cyclical",
    tickers: ["OPEN", "COMP", "Z", "ZG", "RDFN", "EXPI", "RMAX", "OPAD", "DOMA"],
    industries: [/real estate services/, /real estate - development/, /real estate - diversified/],
    scope: "Earns fees or trading margins from home sales — brokerage, listings, or buying and reselling homes (iBuying).",
    drivers: ["Home-sale transaction volumes recovering", "Lower mortgage rates unlocking existing-home sales",
              "Taking share with technology platforms"],
    risks: ["Transaction volumes collapse when mortgage rates rise",
            "iBuyers carry home inventory — falling prices hit margins directly",
            "Thin or negative margins; agent-commission rule changes"],
  },
  {
    key: "reits", name: "Real estate (REITs)", etf: "XLRE", growth: "defensive",
    industries: [/reit/],
    scope: "Owns property and pays out most of its rent as dividends.",
    drivers: ["Rent growth", "Falling interest rates lift property values"],
    risks: ["Rate-sensitive", "Refinancing costs", "Office and retail vacancy"],
  },
  {
    key: "it_services", name: "IT services & digital infrastructure", etf: "XLK", growth: "cyclical",
    industries: [/information technology services/],
    scope: "Sells technology services — consulting, outsourcing, hosting or infrastructure — rather than its own software products.",
    drivers: ["Corporate IT and AI-adoption budgets", "Multi-year contracts give revenue visibility"],
    risks: ["Spending is cut quickly in downturns", "Low switching costs and price competition",
            "AI automation can shrink billable work"],
  },
  {
    key: "casinos", name: "Casinos & gaming", etf: "BJK", growth: "cyclical",
    industries: [/casino/, /gambling/],
    scope: "Runs casinos, resorts or betting — revenue follows visitor numbers and how much they wager.",
    drivers: ["Consumer leisure spending", "Las Vegas and Macau visitation", "Online sports betting growth"],
    risks: ["Discretionary spending falls first in a slowdown", "Heavy debt at many operators",
            "Regulation and licensing, especially in Macau"],
  },
  {
    key: "software", name: "Enterprise software", etf: "IGV", growth: "secular",
    industries: [/software/],
    scope: "Sells software or IT services to businesses, mostly by subscription.",
    drivers: ["Recurring subscription revenue", "AI features as a new price tier",
              "High gross margins once scaled"],
    risks: ["AI agents could shrink per-seat pricing", "IT budgets tighten in slowdowns",
            "Growth decelerating from maturity"],
  },
  {
    key: "internet", name: "Internet & digital media", etf: "XLC", growth: "secular",
    industries: [/internet content/, /interactive media/, /entertainment/, /electronic gaming/, /advertising/],
    scope: "Monetises audiences through ads, subscriptions or content.",
    drivers: ["Digital ad share gains", "Subscription pricing power", "AI-improved ad targeting"],
    risks: ["Ad spend is cyclical", "Regulation and privacy changes", "Competition for attention"],
  },
  {
    key: "ecommerce", name: "E-commerce & online platforms", etf: "XLY", growth: "secular",
    industries: [/internet retail/],
    scope: "Sells goods or services online or runs a marketplace.",
    drivers: ["Online share of retail still rising", "Ads and fintech layered on marketplaces"],
    risks: ["Consumer spending cycles", "Low margins and logistics costs", "Tariffs on imported goods"],
  },
  {
    key: "oil_gas", name: "Oil & gas", etf: "XLE", growth: "cyclical",
    industries: [/oil & gas/, /oil and gas/],
    scope: "Produces, transports or refines oil and natural gas.",
    drivers: ["Oil and gas prices", "Capital discipline funding dividends and buybacks",
              "LNG exports and gas demand from power generation"],
    risks: ["Commodity prices set earnings — and OPEC+ sets supply",
            "Demand slowdown in a recession", "Long-run energy transition"],
  },
  {
    key: "solar", name: "Solar & clean energy", etf: "TAN", growth: "cyclical",
    industries: [/solar/],
    scope: "Makes or installs solar and clean-energy equipment.",
    drivers: ["Cheapest new electricity in many markets", "Power demand from data centers"],
    risks: ["Highly sensitive to interest rates and subsidies", "Policy reversals", "Chinese price competition"],
  },
  {
    key: "uranium", name: "Uranium & nuclear fuel", etf: "URA", growth: "cyclical",
    industries: [/uranium/],
    scope: "Mines or processes uranium for nuclear reactors.",
    drivers: ["Reactor life extensions and new builds", "Tight supply after years of underinvestment"],
    risks: ["Uranium price swings", "Project delays", "Geopolitics of supply"],
  },
  {
    key: "utilities", name: "Regulated utilities", etf: "XLU", growth: "defensive",
    industries: [/utilities/],
    scope: "Delivers electricity, gas or water under regulated returns.",
    drivers: ["Steady regulated earnings and dividends", "Rate-base growth from grid investment"],
    risks: ["Behaves like a bond: rising rates weigh on it", "Regulatory decisions cap returns",
            "Wildfire and storm liabilities"],
  },
  {
    key: "biotech", name: "Biotechnology", etf: "XBI", growth: "speculative",
    industries: [/biotechnology/],
    scope: "Develops drugs whose value depends on clinical trials and approvals.",
    drivers: ["Trial readouts and FDA approvals", "Takeover interest from big pharma"],
    risks: ["Binary events: one trial can halve the stock", "Cash burn and dilution",
            "Drug-pricing policy"],
  },
  {
    key: "healthcare", name: "Pharma & healthcare", etf: "XLV", growth: "defensive",
    industries: [/drug manufacturers/, /medical/, /health/, /diagnostics/, /pharmaceutical/],
    scope: "Makes drugs or devices, or provides and pays for care.",
    drivers: ["Aging populations", "Pipeline launches", "Defensive demand in slowdowns"],
    risks: ["Patent cliffs", "Drug-pricing and reimbursement policy", "Litigation"],
  },
  {
    key: "banks", name: "Banks", etf: "KRE", growth: "cyclical",
    industries: [/banks/],
    scope: "Takes deposits and lends; earns the spread between them.",
    drivers: ["Net interest margin (a steeper yield curve helps)", "Loan growth", "Capital returned via buybacks"],
    risks: ["Credit losses in a downturn", "Deposit flight and funding costs", "Commercial real-estate exposure"],
  },
  {
    key: "financials", name: "Financial services", etf: "XLF", growth: "cyclical",
    industries: [/insurance/, /capital markets/, /credit services/, /asset management/, /financial/, /mortgage/],
    scope: "Insures, invests, lends or runs markets and payments.",
    drivers: ["Market activity and asset levels", "Pricing cycles in insurance", "Payment volumes"],
    risks: ["Market downturns cut fees", "Credit and catastrophe losses", "Regulation"],
  },
  {
    key: "defense", name: "Aerospace & defense", etf: "ITA", growth: "secular",
    industries: [/aerospace/, /defense/],
    scope: "Builds aircraft, engines, weapons or defense systems.",
    drivers: ["Rising defense budgets", "Commercial air-travel recovery and aircraft backlogs"],
    risks: ["Program delays and fixed-price contract losses", "Budget politics", "Supply-chain bottlenecks"],
  },
  {
    key: "autos", name: "Autos & EVs", etf: "XLY", growth: "cyclical",
    industries: [/auto manufacturers/, /auto parts/, /auto & truck/],
    scope: "Makes vehicles or vehicle parts.",
    drivers: ["Vehicle demand and pricing", "EV and autonomy adoption"],
    risks: ["Consumer credit and rates", "Tariffs and trade policy", "Price wars in EVs"],
  },
  {
    key: "housing", name: "Homebuilding & housing", etf: "ITB", growth: "cyclical",
    industries: [/residential construction/, /building products/, /home improvement/],
    scope: "Builds homes or supplies the products that go into them.",
    drivers: ["Chronic US housing shortage", "Mortgage-rate declines unlock demand"],
    risks: ["Mortgage rates", "Affordability", "Materials and labour costs"],
  },
  {
    key: "airlines", name: "Airlines & travel", etf: "JETS", growth: "cyclical",
    industries: [/airlines/, /travel/, /lodging/, /resorts/],
    scope: "Sells air travel, trips or accommodation.",
    drivers: ["Travel demand", "Capacity discipline", "Premium and loyalty revenue"],
    risks: ["Fuel prices", "Recessions hit travel first", "Labour costs"],
  },
  {
    key: "consumer", name: "Consumer discretionary", etf: "XLY", growth: "cyclical",
    industries: [/retail/, /restaurants/, /apparel/, /footwear/, /leisure/, /gambling/, /luxury/,
                 /recreational/, /furnishings/, /personal services/],
    scope: "Sells things people buy when they have money to spare.",
    drivers: ["Consumer spending and wage growth", "Brand pricing power"],
    risks: ["Spending slows first in a downturn", "Tariffs on imported goods", "Shifts in taste"],
  },
  {
    key: "staples", name: "Consumer staples", etf: "XLP", growth: "defensive",
    industries: [/beverages/, /packaged foods/, /household/, /tobacco/, /grocery/, /discount stores/,
                 /farm products/, /food distribution/, /confectioners/],
    scope: "Sells everyday necessities people buy in any economy.",
    drivers: ["Steady demand", "Pricing power of big brands", "Dividends"],
    risks: ["Slow growth", "Volume loss when prices rise", "Input-cost inflation"],
  },
  {
    key: "gold", name: "Gold & precious metals", etf: "GDX", growth: "cyclical",
    industries: [/gold/, /silver/, /precious metals/],
    scope: "Mines gold or silver.",
    drivers: ["Gold price — helped by falling real rates, central-bank buying and fear"],
    risks: ["Metal price reversals", "Mining costs and operational problems", "Jurisdiction risk"],
  },
  {
    key: "materials", name: "Materials & mining", etf: "XLB", growth: "cyclical",
    industries: [/chemicals/, /steel/, /aluminum/, /copper/, /metals/, /mining/, /building materials/,
                 /paper/, /packaging/, /lumber/, /coking coal/, /thermal coal/],
    scope: "Produces raw and processed materials.",
    drivers: ["Industrial and construction demand", "Commodity prices", "China's economy"],
    risks: ["Commodity cycles", "Global slowdown", "Energy costs"],
  },
  {
    key: "industrials", name: "Industrials", etf: "XLI", growth: "cyclical",
    industries: [/machinery/, /industrial/, /engineering/, /construction/, /trucking/, /railroads/,
                 /freight/, /logistics/, /conglomerates/, /waste/, /security & protection/,
                 /staffing/, /consulting/, /rental/, /marine shipping/, /tools/, /farm & heavy/],
    scope: "Makes equipment or provides services that the rest of the economy runs on.",
    drivers: ["Capital spending and infrastructure", "Reshoring", "Pricing on backlogs"],
    risks: ["Economic cycles", "Freight and input costs", "Tariffs"],
  },
  {
    key: "telecom", name: "Telecom", etf: "XLC", growth: "defensive",
    industries: [/telecom/],
    scope: "Sells mobile, broadband or network connectivity.",
    drivers: ["Recurring subscription revenue", "Fibre and 5G upgrades", "Dividends"],
    risks: ["Heavy debt and capex", "Price competition", "Slow growth"],
  },
];

// Broad fallback when neither ticker nor industry matched.
const SECTOR_ETF = {
  "technology": "XLK", "energy": "XLE", "financial services": "XLF", "financial": "XLF",
  "healthcare": "XLV", "industrials": "XLI", "consumer cyclical": "XLY",
  "consumer defensive": "XLP", "utilities": "XLU", "basic materials": "XLB",
  "real estate": "XLRE", "communication services": "XLC",
};
const SECTOR_GROWTH = {
  "technology": "secular", "communication services": "secular", "healthcare": "defensive",
  "utilities": "defensive", "consumer defensive": "defensive", "real estate": "defensive",
};

const norm = (s) => String(s || "").toLowerCase().replace(/[—–]/g, " - ").replace(/\s+/g, " ").trim();

/** The theme for a ticker, or a sector-level fallback, or null. Pure. */
export function resolveTheme(ticker, sector, industry) {
  const t = String(ticker || "").toUpperCase();
  const byTicker = THEMES.find((th) => th.tickers?.includes(t));
  if (byTicker) return { ...byTicker, matched: "ticker" };
  const ind = norm(industry);
  if (ind) {
    const byInd = THEMES.find((th) => th.industries?.some((re) => re.test(ind)));
    if (byInd) return { ...byInd, matched: "industry" };
  }
  const sec = norm(sector);
  if (SECTOR_ETF[sec]) {
    return {
      key: `sector_${sec.replace(/\s+/g, "_")}`, name: sector, etf: SECTOR_ETF[sec],
      growth: SECTOR_GROWTH[sec] || "cyclical", matched: "sector",
      scope: null, drivers: [], risks: [],
    };
  }
  return null;
}

/** Plain-JSON copy of THEMES for the Python basket builder
 *  (backend/theme_pulse.py). Regexes become their source strings; they use
 *  only syntax Python's `re` reads identically. Regenerate the committed copy
 *  with `npm run themes:export` in alphahunter-ai/frontend — a vitest check
 *  fails when it drifts from this file. */
export function themesAsJson() {
  return {
    themes: THEMES.map((t) => ({
      key: t.key, name: t.name, etf: t.etf, growth: t.growth,
      tickers: t.tickers || [], industries: (t.industries || []).map((re) => re.source),
    })),
  };
}
