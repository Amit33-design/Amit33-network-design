// What the company actually does, and which segment it sits in.
//
// A verdict on a ticker is far less useful when the reader does not know what
// the business sells. Profiles are generated in CI (Yahoo's profile endpoint
// needs a crumb the serverless functions cannot get) and served as a static
// file, so this costs one cached fetch for the whole app.
import { useEffect, useState } from "react";
import { Badge } from "./ui";

export type Profile = {
  name?: string; sector?: string | null; industry?: string | null;
  summary?: string | null; employees?: number | null; country?: string | null;
  website?: string | null; market_cap?: number | null;
};

let cache: Record<string, Profile> | null = null;
let inflight: Promise<Record<string, Profile>> | null = null;

function loadAll(): Promise<Record<string, Profile>> {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = fetch("/profiles.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { cache = j?.profiles || {}; return cache!; })
      .catch(() => { cache = {}; return cache!; });
  }
  return inflight;
}

/** The company profile, from the CI-generated file or live from /api/profile.
 *
 *  Two sources on purpose. profiles.json has the long business summary, which
 *  needs a crumb only yfinance-in-Actions can get — but relying on it ALONE
 *  meant the panel showed nothing until a cron had run, and nothing ever for a
 *  ticker outside the generated set. The live endpoint always supplies name,
 *  sector and industry, so the panel works immediately for any symbol and the
 *  summary fills in when it exists.
 */
export function useProfile(ticker?: string): Profile | null {
  const [p, setP] = useState<Profile | null>(null);
  useEffect(() => {
    if (!ticker) { setP(null); return; }
    const sym = ticker.toUpperCase();
    let cancelled = false;

    loadAll().then(async (all) => {
      const stat = all[sym] ?? null;
      if (!cancelled && stat) setP(stat);          // show what we have at once

      // Fill the gaps live. Skipped entirely when the static entry is already
      // complete, so the common case costs no request.
      if (stat?.summary && stat?.sector) return;
      try {
        const r = await fetch(`/api/profile?ticker=${encodeURIComponent(sym)}`);
        if (!r.ok || cancelled) return;
        const live = await r.json();
        if (cancelled) return;
        setP({
          name: stat?.name || live.name,
          // Static wins where present: its classification comes from the
          // fuller profile endpoint rather than from search.
          sector: stat?.sector ?? live.sector,
          industry: stat?.industry ?? live.industry,
          summary: stat?.summary ?? null,
          employees: stat?.employees ?? null,
          country: stat?.country ?? null,
          website: stat?.website ?? null,
          market_cap: stat?.market_cap ?? null,
        });
      } catch { /* the static entry, if any, still stands */ }
    });
    return () => { cancelled = true; };
  }, [ticker]);
  return p;
}

const cap = (v?: number | null) => {
  if (!v) return null;
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  return `$${(v / 1e6).toFixed(0)}M`;
};

export default function CompanyProfile({ profile }: { profile: Profile }) {
  const [open, setOpen] = useState(false);
  if (!profile.summary && !profile.sector && !profile.industry) return null;

  const short = profile.summary && profile.summary.length > 240
    ? profile.summary.slice(0, 240).replace(/\s+\S*$/, "") + "…"
    : profile.summary;

  return (
    <div className="panel p-3">
      <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
        <span className="label-eyebrow">What this company does</span>
        {profile.sector && <Badge tone="info">{profile.sector}</Badge>}
        {profile.industry && profile.industry !== profile.sector && (
          <Badge>{profile.industry}</Badge>
        )}
        {cap(profile.market_cap) && <Badge>{cap(profile.market_cap)} cap</Badge>}
        {profile.employees ? (
          <Badge>{profile.employees.toLocaleString()} staff</Badge>
        ) : null}
        {profile.country && <Badge>{profile.country}</Badge>}
      </div>
      {!profile.summary && (profile.sector || profile.industry) && (
        <div className="text-xs text-ink-muted">
          {profile.name}
          {profile.industry ? ` — ${profile.industry}` : ""}. A fuller business
          description appears once the daily profile refresh has covered this
          ticker.
        </div>
      )}
      {profile.summary && (
        <div className="text-xs text-ink-secondary leading-relaxed">
          {open ? profile.summary : short}
          {profile.summary.length > 240 && (
            <button onClick={() => setOpen(!open)}
                    className="ml-1 text-brand hover:underline">
              {open ? "less" : "more"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
