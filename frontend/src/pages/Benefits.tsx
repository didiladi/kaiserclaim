import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Shield, Plus } from "lucide-react";
import { listContracts, getBenefits } from "../api";
import type { Contract, BenefitRule } from "../api";
import { useAppContext } from "../state/AppContext";
import { FamilyFilterPills } from "../components/FamilyFilterPills";
import { KCCard } from "../components/KCCard";
import { Avatar } from "../components/Avatar";
import { ProgressBar } from "../components/ProgressBar";

export function Benefits() {
  const { activeMember, familyMembers } = useAppContext();
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [benefits, setBenefits] = useState<Record<string, BenefitRule[]>>({});
  const navigate = useNavigate();

  const activeMemberObj = familyMembers.find((m) => m.member_key === activeMember);

  useEffect(() => {
    listContracts().then(async (cs) => {
      setContracts(cs);
      const entries = await Promise.all(cs.map(async (c) => [c.id, await getBenefits(c.id)] as const));
      setBenefits(Object.fromEntries(entries));
    }).catch(() => {});
  }, []);

  const PERIOD_LABEL: Record<string, string> = { YEARLY: "jährlich", BIANNUAL: "2-jährlich" };

  return (
    <div className="pb-4">
      <FamilyFilterPills />

      <div className="px-5 mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-bold text-kc-text">Leistungen</h1>
          <p className="text-[14px] text-kc-textSec mt-0.5">
            {activeMemberObj ? activeMemberObj.name : "Alle Familienmitglieder"}
          </p>
        </div>
        <button
          onClick={() => navigate("/onboarding")}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-kc-surfaceAlt text-kc-text text-[13px] font-semibold border border-kc-border"
        >
          <Plus size={15} /> Vertrag hinzufügen
        </button>
      </div>

      {contracts.length === 0 && (
        <p className="px-5 text-[14px] text-kc-textSec">Noch keine Verträge vorhanden.</p>
      )}

      <div className="px-5 flex flex-col gap-4">
        {contracts.map((contract) => {
          const rules = benefits[contract.id] ?? [];
          const displayMembers = activeMember === "all"
            ? familyMembers
            : familyMembers.filter((m) => m.member_key === activeMember);

          return (
            <KCCard key={contract.id} className="overflow-hidden">
              {/* Contract header */}
              <div className="flex items-center gap-3 px-4 py-4 bg-kc-surfaceAlt border-b border-kc-borderLight">
                <div className="w-10 h-10 rounded-lg bg-kc-accentMid flex items-center justify-center flex-shrink-0">
                  <Shield size={20} className="text-kc-accent" />
                </div>
                <div>
                  <p className="text-[15px] font-semibold text-kc-text">{contract.provider_name}</p>
                  {contract.policy_number && (
                    <p className="text-[12px] text-kc-textSec">{contract.policy_number}</p>
                  )}
                </div>
              </div>

              {/* Per member */}
              {displayMembers.map((member) => (
                <div key={member.member_key}>
                  {/* Member row */}
                  <div className="flex items-center gap-3 px-4 py-3 bg-kc-surfaceAlt border-b border-kc-borderLight">
                    <Avatar initials={member.initials} color={member.color} size={32} />
                    <span className="text-[14px] font-semibold text-kc-text">{member.name}</span>
                  </div>

                  {/* Benefits */}
                  {rules.length === 0 && (
                    <p className="px-4 py-3 text-[13px] text-kc-textSec">Keine Leistungen</p>
                  )}
                  {rules.map((rule) => (
                    <div key={rule.id} className="px-4 py-3 border-b border-kc-borderLight last:border-0">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[14px] font-medium text-kc-text">{rule.benefit_name}</span>
                        <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-kc-surfaceAlt text-kc-textSec">
                          {PERIOD_LABEL[rule.limit_type] ?? rule.limit_type}
                        </span>
                      </div>
                      <ProgressBar used={rule.amount_used} limit={rule.limit_amount} />
                    </div>
                  ))}
                </div>
              ))}
            </KCCard>
          );
        })}
      </div>
    </div>
  );
}
