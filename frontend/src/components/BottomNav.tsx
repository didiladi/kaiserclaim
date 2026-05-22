import { Home, Receipt, BarChart2, TrendingUp, Plus } from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";
import clsx from "clsx";

const TABS = [
  { to: "/",          icon: Home,      label: "Übersicht" },
  { to: "/invoices",  icon: Receipt,   label: "Belege" },
  { to: "/benefits",  icon: BarChart2, label: "Leistungen" },
  { to: "/stats",     icon: TrendingUp,label: "Statistik" },
];

export function BottomNav() {
  const navigate = useNavigate();

  return (
    <nav className="h-16 bg-kc-surface border-t border-kc-borderLight flex items-center px-2 sticky bottom-0 z-10">
      {/* First two tabs */}
      {TABS.slice(0, 2).map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          className={({ isActive }) =>
            clsx(
              "flex-1 flex flex-col items-center gap-0.5 text-[11px] font-semibold py-2 transition-colors",
              isActive ? "text-kc-accent" : "text-[#9CA3AF]"
            )
          }
        >
          {({ isActive }) => (
            <>
              <Icon size={22} strokeWidth={isActive ? 2 : 1.8} />
              {label}
            </>
          )}
        </NavLink>
      ))}

      {/* FAB */}
      <div className="flex-1 flex justify-center">
        <button
          onClick={() => navigate("/upload")}
          className="w-12 h-12 rounded-xl bg-kc-accent flex items-center justify-center text-white -mt-3 shadow-lg shadow-kc-accent/30 hover:bg-kc-accentHover transition-colors"
        >
          <Plus size={24} strokeWidth={2} />
        </button>
      </div>

      {/* Last two tabs */}
      {TABS.slice(2).map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            clsx(
              "flex-1 flex flex-col items-center gap-0.5 text-[11px] font-semibold py-2 transition-colors",
              isActive ? "text-kc-accent" : "text-[#9CA3AF]"
            )
          }
        >
          {({ isActive }) => (
            <>
              <Icon size={22} strokeWidth={isActive ? 2 : 1.8} />
              {label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
