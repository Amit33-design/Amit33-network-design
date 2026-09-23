import { Badge } from "./ui";
import { statusFor, type ScreenRecord, type Status } from "../lib/evidence";

/** A screen's measured track record, in one chip. Hover for the numbers.
 *  `status` overrides the computed one for lists that are not a scan screen
 *  and so have no trade record of their own. */
export default function EvidenceBadge(
  { rec, status }: { rec?: ScreenRecord | null; status?: Status },
) {
  const s = status ?? statusFor(rec);
  return (
    <span title={s.detail} className="cursor-help">
      <Badge tone={s.tone}>
        {s.label}{!status && rec?.trades ? ` · ${rec.trades}` : ""}
      </Badge>
    </span>
  );
}
