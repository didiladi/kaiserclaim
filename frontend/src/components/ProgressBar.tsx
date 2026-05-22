import { formatEUR } from "../lib/format";

interface Props {
  used: number;
  limit: number;
}

function barColor(pct: number): string {
  if (pct >= 100) return "#DC2626";
  if (pct >= 75) return "#F59E0B";
  return "#16A34A";
}

export function ProgressBar({ used, limit }: Props) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const color = barColor(pct);
  const remaining = Math.max(limit - used, 0);

  return (
    <div>
      <div className="h-1.5 rounded-full bg-kc-surfaceAlt overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-600"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-[12px] font-medium" style={{ color }}>
          {formatEUR(remaining)} übrig
        </span>
        <span className="text-[12px] text-kc-textTri tabular-nums">
          {formatEUR(used)} / {formatEUR(limit)}
        </span>
      </div>
    </div>
  );
}
