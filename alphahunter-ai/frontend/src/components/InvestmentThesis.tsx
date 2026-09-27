// The investment case for one ticker — the half of the analysis the chart
// cannot give. "Why" explains the technical verdict; this explains what the
// business is, what drives it, how the market currently feels about its group
// (measured, not written), and whether that story agrees with the chart.
import type { Profile } from "./CompanyProfile";
import { Badge } from "./ui";
import { GROWTH_LABEL, typeLabel, type Story } from "../lib/story";

const toneClass = (t: number) => (t > 0 ? "text-gain" : t < 0 ? "text-loss" : "text-ink-secondary");
const dot = (t: number) => (t > 0 ? "▲" : t < 0 ? "▼" : "•");

export default function InvestmentThesis({ story, profile }: { story: Story; profile?: Profile | null }) {
  const th = story.theme;
  return (
    <div className="panel p-4 border-l-4 border-alpha space-y-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-semibold text-ink">📝 Investment thesis</span>
        <Badge tone="info">{typeLabel(story.type.style, profile?.market_cap)}</Badge>
        {th && <Badge tone="brand" title={th.matched === "sector"
          ? "Matched on sector only — no finer theme for this industry"
          : `Matched on ${th.matched}`}>{th.name}</Badge>}
      </div>

      {story.type.traits.length > 0 && (
        <div className="text-2xs text-ink-muted -mt-1.5">{story.type.traits.join(" · ")}</div>
      )}

      {th && (th.scope || th.drivers.length > 0) && (
        <div>
          <div className="label-eyebrow mb-1">Theme & growth scope</div>
          {th.scope && <div className="text-sm text-ink">{th.scope}</div>}
          {story.type.growth && (
            <div className="text-xs text-ink-secondary mt-0.5">{GROWTH_LABEL[story.type.growth]}</div>
          )}
          {(th.drivers.length > 0 || th.risks.length > 0) && (
            <div className="grid sm:grid-cols-2 gap-3 mt-2">
              {th.drivers.length > 0 && (
                <div>
                  <div className="text-2xs font-semibold text-gain uppercase tracking-wide mb-0.5">Tailwinds</div>
                  <ul className="text-xs text-ink-secondary space-y-0.5 list-disc pl-4">
                    {th.drivers.map((d) => <li key={d}>{d}</li>)}
                  </ul>
                </div>
              )}
              {th.risks.length > 0 && (
                <div>
                  <div className="text-2xs font-semibold text-loss uppercase tracking-wide mb-0.5">Risks</div>
                  <ul className="text-xs text-ink-secondary space-y-0.5 list-disc pl-4">
                    {th.risks.map((d) => <li key={d}>{d}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
          <div className="text-2xs text-ink-muted mt-1">
            Structural drivers of this kind of business, not a forecast. What the market
            thinks of it right now is measured below.
          </div>
        </div>
      )}

      {(story.pulse.reads.length > 0 || story.market) && (
        <div>
          <div className="label-eyebrow mb-1">Sentiment right now — measured</div>
          <ul className="space-y-1">
            {story.pulse.reads.map((r) => (
              <li key={r.text} className={`text-xs ${toneClass(r.tone)}`}>
                <span className="mr-1">{dot(r.tone)}</span>
                <span className="text-ink-secondary">{r.text}</span>
              </li>
            ))}
            {story.market && (
              <li className={`text-xs ${story.market.spy_above_200d ? "text-gain" : "text-loss"}`}>
                <span className="mr-1">{dot(story.market.spy_above_200d ? 1 : -1)}</span>
                <span className="text-ink-secondary">{story.market.text}</span>
              </li>
            )}
          </ul>
        </div>
      )}

      <div className="pt-2 border-t border-line text-sm text-ink">
        <span className="font-semibold">Bottom line: </span>{story.bottom_line}
      </div>
    </div>
  );
}
