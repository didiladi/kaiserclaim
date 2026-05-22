import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, AlertCircle, TrendingUp } from "lucide-react";
import { useAppContext } from "../state/AppContext";
import { FamilyFilterPills } from "../components/FamilyFilterPills";
import { InvoiceCard } from "../components/InvoiceCard";
import { KCCard } from "../components/KCCard";
import { Button } from "../components/Button";
import { getDashboardSummary, listInvoices } from "../api";
import type { Invoice, DashboardSummary } from "../api";
import { formatEUR } from "../lib/format";

function useCountUp(target: number, duration = 1200) {
  const [value, setValue] = useState(0);
  const animRef = useRef<number>();
  useEffect(() => {
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(target * eased);
      if (t < 1) animRef.current = requestAnimationFrame(tick);
    };
    animRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animRef.current!);
  }, [target, duration]);
  return value;
}

export function Home() {
  const { activeMember, familyMembers } = useAppContext();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const navigate = useNavigate();

  const memberKey = activeMember === "all" ? undefined : activeMember;
  const activeMemberObj = familyMembers.find((m) => m.member_key === activeMember);

  useEffect(() => {
    getDashboardSummary(2026, memberKey).then(setSummary).catch(() => {});
    listInvoices({ member_key: memberKey }).then((data) => setInvoices(data.slice(0, 5))).catch(() => {});
  }, [activeMember]);

  const totalPaid = useCountUp(summary?.total_paid ?? 0);
  const totalReimbursed = summary?.total_reimbursed ?? 0;
  const inProgressCount = summary?.in_progress_count ?? 0;
  const eigenanteil = summary?.eigenanteil ?? 0;

  return (
    <div className="pb-4">
      <FamilyFilterPills />

      {/* Hero card */}
      <div className="mx-5 mb-4">
        <div
          className="rounded-xl p-5 overflow-hidden relative"
          style={{ background: "linear-gradient(135deg, #1A1F36 0%, #2D3A5E 100%)" }}
        >
          {/* Decorative circles */}
          <div className="absolute top-0 right-0 w-[120px] h-[120px] rounded-full pointer-events-none" style={{ background: "rgba(255,255,255,0.05)", transform: "translate(30px,-30px)" }} />
          <div className="absolute bottom-0 right-8 w-20 h-20 rounded-full pointer-events-none" style={{ background: "rgba(255,255,255,0.03)", transform: "translateY(20px)" }} />

          <p className="text-[12px] text-white/60 mb-1">
            Gesamtausgaben 2026{activeMemberObj ? ` — ${activeMemberObj.name.split(" ")[0]}` : ""}
          </p>
          <p className="text-[44px] font-bold text-white tabular-nums leading-none mb-4" style={{ letterSpacing: "-0.02em" }}>
            {formatEUR(totalPaid)}
          </p>

          <div className="flex gap-2">
            {[
              { label: "Erstattet", value: formatEUR(totalReimbursed) },
              { label: "In Bearbeitung", value: String(inProgressCount) },
              { label: "Eigenanteil", value: formatEUR(eigenanteil) },
            ].map(({ label, value }) => (
              <div key={label} className="flex-1 rounded-xl p-2 text-center" style={{ background: "rgba(255,255,255,0.1)" }}>
                <p className="text-[10px] text-white/60 mb-0.5">{label}</p>
                <p className="text-[13px] font-semibold text-white tabular-nums">{value}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Upload CTA */}
      <div className="mx-5 mb-5">
        <Button fullWidth size="lg" onClick={() => navigate("/upload")}>
          <Upload size={18} /> Beleg hochladen
        </Button>
      </div>

      {/* Benefit alerts */}
      {(summary?.benefit_alerts ?? []).map((alert) => (
        <div key={alert.benefit_name} className="mx-5 mb-4 flex items-start gap-3 p-3.5 rounded-lg" style={{ background: "#FFF7ED" }}>
          <AlertCircle size={18} className="text-amber-500 flex-shrink-0 mt-0.5" />
          <p className="text-[13px] text-amber-800">
            <span className="font-semibold">{alert.benefit_name}</span> — {alert.percent_used}% ausgeschöpft
          </p>
        </div>
      ))}

      {/* Stats teaser */}
      <div className="mx-5 mb-5">
        <KCCard hover onClick={() => navigate("/stats")} className="p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-kc-accentMid flex items-center justify-center">
            <TrendingUp size={20} className="text-kc-accent" />
          </div>
          <div className="flex-1">
            <p className="text-[14px] font-semibold text-kc-text">Statistiken ansehen</p>
            <p className="text-[12px] text-kc-textSec">Monatliche Ausgaben &amp; Erstattungen</p>
          </div>
        </KCCard>
      </div>

      {/* Recent invoices */}
      <div className="mx-5 mb-2 flex items-center justify-between">
        <span className="text-[17px] font-bold text-kc-text">Letzte Belege</span>
        <button onClick={() => navigate("/invoices")} className="text-[13px] font-semibold text-kc-accent">
          Alle anzeigen
        </button>
      </div>
      {invoices.length > 0 ? (
        <KCCard className="mx-5 divide-y divide-kc-borderLight">
          {invoices.map((inv) => (
            <InvoiceCard
              key={inv.id}
              invoice={inv}
              members={familyMembers}
              onClick={() => navigate(`/invoices/${inv.id}`)}
            />
          ))}
        </KCCard>
      ) : (
        <p className="mx-5 text-[14px] text-kc-textSec text-center py-6">Keine Belege vorhanden</p>
      )}
    </div>
  );
}
