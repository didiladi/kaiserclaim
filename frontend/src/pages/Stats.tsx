import { useEffect, useState } from "react";
import { useAppContext } from "../state/AppContext";
import { FamilyFilterPills } from "../components/FamilyFilterPills";
import { KCCard } from "../components/KCCard";
import { Avatar } from "../components/Avatar";
import { getMonthlyStats, getYearlyStats, getMemberStats } from "../api";
import type { MonthlyStats, YearlyStats, MemberStats } from "../api";
import { formatEUR } from "../lib/format";
import clsx from "clsx";

type View = "monthly" | "yearly" | "members";

const YEAR = 2026;

const MEMBER_COLORS: Record<string, string> = {
  maria: "#E84393", thomas: "#3B82F6", luisa: "#F59E0B", felix: "#10B981",
};

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <KCCard className="p-4 flex flex-col gap-1">
      <p className="text-[12px] font-semibold text-kc-textSec">{label}</p>
      <p className="text-[20px] font-bold tabular-nums" style={{ color: color ?? "#1A1F36" }}>{value}</p>
    </KCCard>
  );
}

export function Stats() {
  const { activeMember, familyMembers } = useAppContext();
  const [view, setView] = useState<View>("monthly");
  const [monthly, setMonthly] = useState<MonthlyStats[]>([]);
  const [yearly, setYearly] = useState<YearlyStats[]>([]);
  const [members, setMembers] = useState<MemberStats[]>([]);

  const memberKey = activeMember === "all" ? undefined : activeMember;

  useEffect(() => { getMonthlyStats(YEAR, memberKey).then(setMonthly).catch(() => {}); }, [activeMember]);
  useEffect(() => { getYearlyStats().then(setYearly).catch(() => {}); }, []);
  useEffect(() => { getMemberStats(YEAR).then(setMembers).catch(() => {}); }, []);

  const currentYear = yearly.find((y) => y.year === YEAR);
  const totalPaid = currentYear?.total_paid ?? 0;
  const totalReimbursed = currentYear?.total_reimbursed ?? 0;
  const eigenanteil = currentYear?.eigenanteil ?? 0;
  const reimbursementRate = totalPaid > 0 ? ((totalReimbursed / totalPaid) * 100).toFixed(1) : "0.0";

  const maxMonthly = Math.max(...monthly.map((m) => m.total), 1);

  return (
    <div className="pb-6">
      <FamilyFilterPills />

      <div className="px-5 mb-4 flex items-center justify-between">
        <h1 className="text-[22px] font-bold text-kc-text">Statistiken</h1>
        <span className="text-[12px] font-semibold px-2.5 py-1 rounded-full bg-kc-surfaceAlt text-kc-textSec">{YEAR}</span>
      </div>

      {/* 2×2 stat grid */}
      <div className="px-5 grid grid-cols-2 gap-3 mb-5">
        <StatCard label="Ausgaben" value={formatEUR(totalPaid)} />
        <StatCard label="Erstattet" value={formatEUR(totalReimbursed)} color="#16A34A" />
        <StatCard label="Eigenanteil" value={formatEUR(eigenanteil)} color="#EA580C" />
        <StatCard label="Erstattungsquote" value={`${reimbursementRate}%`} color="#0D9488" />
      </div>

      {/* View tabs */}
      <div className="flex gap-2 px-5 mb-5">
        {(["monthly", "yearly", "members"] as View[]).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={clsx(
              "px-3.5 py-1.5 rounded-full text-[13px] font-semibold transition-colors",
              view === v ? "bg-kc-brand text-white" : "bg-kc-surfaceAlt text-kc-textSec"
            )}
          >
            {{ monthly: "Monatlich", yearly: "Jährlich", members: "Mitglieder" }[v]}
          </button>
        ))}
      </div>

      {/* Monthly view */}
      {view === "monthly" && (
        <div className="px-5">
          <KCCard className="p-4">
            <p className="text-[15px] font-bold text-kc-text mb-4">Monatliche Ausgaben</p>
            {/* Bar chart */}
            <div className="flex items-end gap-1.5 h-40 mb-4">
              {monthly.slice(0, 5).map((m) => {
                const height = (m.total / maxMonthly) * 100;
                return (
                  <div key={m.month} className="flex-1 flex flex-col items-center gap-1">
                    {activeMember === "all" ? (
                      <div className="w-full relative" style={{ height: height + "%" }}>
                        {familyMembers.map((fm) => {
                          const fmHeight = ((m.by_member[fm.member_key] ?? 0) / maxMonthly) * 100;
                          return (
                            <div key={fm.member_key} className="w-full rounded-sm absolute bottom-0" style={{ height: fmHeight + "%", backgroundColor: fm.color }} />
                          );
                        })}
                      </div>
                    ) : (
                      <div
                        className="w-full rounded-sm"
                        style={{ height: height + "%", backgroundColor: MEMBER_COLORS[activeMember] ?? "#0D9488" }}
                      />
                    )}
                    <span className="text-[10px] text-kc-textSec">{m.month}</span>
                  </div>
                );
              })}
            </div>
            {/* Monthly breakdown */}
            <div className="flex flex-col divide-y divide-kc-borderLight">
              {monthly.slice(0, 5).filter(m => m.total > 0).map((m) => (
                <div key={m.month} className="flex justify-between py-2.5">
                  <span className="text-[14px] text-kc-text">{m.month}</span>
                  <span className="text-[14px] font-semibold tabular-nums text-kc-text">{formatEUR(m.total)}</span>
                </div>
              ))}
            </div>
          </KCCard>
        </div>
      )}

      {/* Yearly view */}
      {view === "yearly" && (
        <div className="px-5 flex flex-col gap-3">
          {yearly.map((y) => (
            <KCCard key={y.year} className="p-4">
              <p className="text-[15px] font-bold text-kc-text mb-3">{y.year}</p>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: "Ausgaben", value: formatEUR(y.total_paid) },
                  { label: "Erstattet", value: formatEUR(y.total_reimbursed), color: "#16A34A" },
                  { label: "Eigenanteil", value: formatEUR(y.eigenanteil), color: "#EA580C" },
                ].map(({ label, value, color }) => (
                  <div key={label} className="text-center">
                    <p className="text-[11px] text-kc-textSec mb-0.5">{label}</p>
                    <p className="text-[13px] font-bold tabular-nums" style={{ color: color ?? "#1A1F36" }}>{value}</p>
                  </div>
                ))}
              </div>
            </KCCard>
          ))}
        </div>
      )}

      {/* Members view */}
      {view === "members" && (
        <div className="px-5 flex flex-col gap-3">
          {members.map((m) => (
            <KCCard key={m.member_key} className="p-4">
              <div className="flex items-center gap-3 mb-3">
                <Avatar initials={m.initials} color={m.color} size={38} />
                <div className="flex-1">
                  <p className="text-[14px] font-semibold text-kc-text">{m.name}</p>
                  <p className="text-[12px] text-kc-textSec">{m.invoice_count} Belege</p>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 mb-3">
                {[
                  { label: "Ausgaben", value: formatEUR(m.total_paid) },
                  { label: "Erstattet", value: formatEUR(m.total_reimbursed), color: "#16A34A" },
                  { label: "Eigenanteil", value: formatEUR(m.eigenanteil), color: "#EA580C" },
                ].map(({ label, value, color }) => (
                  <div key={label} className="text-center">
                    <p className="text-[11px] text-kc-textSec mb-0.5">{label}</p>
                    <p className="text-[12px] font-bold tabular-nums" style={{ color: color ?? "#1A1F36" }}>{value}</p>
                  </div>
                ))}
              </div>
              {/* Share bar */}
              <div className="h-1.5 rounded-full bg-kc-surfaceAlt overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${m.share_pct}%`, backgroundColor: m.color }} />
              </div>
              <p className="text-[11px] text-kc-textSec mt-1">{m.share_pct}% der Familienausgaben</p>
              {/* Categories */}
              {m.categories.length > 0 && (
                <div className="mt-3 flex flex-col gap-1.5">
                  {m.categories.slice(0, 4).map((cat) => (
                    <div key={cat.name} className="flex justify-between text-[13px]">
                      <span className="text-kc-textSec">{cat.name}</span>
                      <span className="font-medium text-kc-text tabular-nums">{formatEUR(cat.amount)}</span>
                    </div>
                  ))}
                </div>
              )}
            </KCCard>
          ))}
        </div>
      )}
    </div>
  );
}
