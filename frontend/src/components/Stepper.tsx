import { Check } from "lucide-react";
import { STATUS_CONFIG } from "../lib/tokens";
import type { PipelineStep } from "../lib/pipeline";

interface Props {
  steps: PipelineStep[];
  currentIdx: number;
}

export function Stepper({ steps, currentIdx }: Props) {
  return (
    <div className="flex flex-col gap-0">
      {steps.map((step, idx) => {
        const completed = idx < currentIdx;
        const active = idx === currentIdx;
        const upcoming = idx > currentIdx;
        const cfg = STATUS_CONFIG[step.statusKey] ?? { color: "#9CA3AF", bg: "#F3F4F6" };
        const isLast = idx === steps.length - 1;

        return (
          <div key={step.statusKey} className="flex gap-3.5">
            {/* Left: dot + connector */}
            <div className="flex flex-col items-center" style={{ width: 28 }}>
              <div
                className="flex-shrink-0 flex items-center justify-center rounded-full"
                style={{
                  width: 28,
                  height: 28,
                  backgroundColor: completed ? cfg.color : active ? cfg.bg : "#F2F1EE",
                  border: active ? `2px solid ${cfg.color}` : "none",
                  boxShadow: active ? `0 0 0 4px ${cfg.color}22` : "none",
                  color: completed ? "#fff" : upcoming ? "#9CA3AF" : cfg.color,
                  fontSize: 12,
                  fontWeight: 600,
                }}
              >
                {completed ? <Check size={14} strokeWidth={2.5} /> : idx + 1}
              </div>
              {!isLast && (
                <div
                  className="w-0.5 flex-1 my-1"
                  style={{
                    minHeight: 20,
                    backgroundColor: completed ? cfg.color : "#E5E3DE",
                  }}
                />
              )}
            </div>

            {/* Right: label */}
            <div className={`pb-4 flex-1 flex items-start gap-2 ${isLast ? "pb-0" : ""}`}>
              <div className="flex-1">
                <p
                  className="text-[14px]"
                  style={{
                    fontWeight: active ? 600 : completed ? 500 : 400,
                    color: upcoming ? "#9CA3AF" : "#1A1F36",
                  }}
                >
                  {step.label}
                </p>
              </div>
              {active && (
                <span className="flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full animate-kcPulse"
                  style={{ backgroundColor: cfg.bg, color: cfg.color }}>
                  Aktiv
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
