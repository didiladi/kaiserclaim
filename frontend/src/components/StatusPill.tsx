import { STATUS_CONFIG } from "../lib/tokens";

interface Props {
  status: string;
  size?: "sm" | "md";
}

export function StatusPill({ status, size = "sm" }: Props) {
  const cfg = STATUS_CONFIG[status] ?? { label: status, color: "#6B7280", bg: "#F3F4F6" };
  const padding = size === "sm" ? "px-2 py-0.5" : "px-2.5 py-1";
  const text = size === "sm" ? "text-[11px]" : "text-xs";

  return (
    <span
      className={`inline-flex items-center rounded-full font-semibold tracking-wide ${padding} ${text}`}
      style={{ color: cfg.color, backgroundColor: cfg.bg }}
    >
      {cfg.label}
    </span>
  );
}
