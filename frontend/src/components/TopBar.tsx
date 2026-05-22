import { Settings, ArrowLeft, Shield } from "lucide-react";
import { useNavigate } from "react-router-dom";

interface Props {
  title?: string;
  showBack?: boolean;
  showSettings?: boolean;
}

export function TopBar({ title, showBack, showSettings }: Props) {
  const navigate = useNavigate();

  return (
    <header className="h-14 px-5 flex items-center justify-between bg-kc-surface border-b border-kc-borderLight sticky top-0 z-10">
      {/* Left */}
      {showBack ? (
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-kc-accent text-[14px] font-medium"
        >
          <ArrowLeft size={18} />
          Zurück
        </button>
      ) : (
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-kc-accent flex items-center justify-center">
            <Shield size={16} className="text-white" />
          </div>
          <span className="text-[18px] tracking-tight" style={{ letterSpacing: "-0.02em" }}>
            <span className="font-bold text-kc-brand">Kaiser</span>
            <span className="font-medium text-kc-brand">Claim</span>
          </span>
        </div>
      )}

      {/* Center title (sub-screens) */}
      {title && (
        <span className="absolute left-1/2 -translate-x-1/2 text-[15px] font-semibold text-kc-text">
          {title}
        </span>
      )}

      {/* Right */}
      {showSettings ? (
        <button onClick={() => navigate("/settings")} className="text-kc-textSec">
          <Settings size={22} />
        </button>
      ) : (
        <div className="w-5" />
      )}
    </header>
  );
}
