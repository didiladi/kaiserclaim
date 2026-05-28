import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Shield, Plus, AlertCircle } from "lucide-react";
import { listContracts, getCoverage } from "../api";
import type { Contract, ContractCoverage, BenefitRuleDetail, InsuredPersonRead } from "../api";
import { useAppContext } from "../state/AppContext";
import { FamilyFilterPills } from "../components/FamilyFilterPills";
import { KCCard } from "../components/KCCard";
import { Avatar } from "../components/Avatar";
import { ProgressBar } from "../components/ProgressBar";
import { formatEUR } from "../lib/format";

const RESET_PERIOD_LABEL: Record<string, string> = {
  CALENDAR_YEAR: "jährlich (Kj.)",
  INSURANCE_YEAR: "jährlich (Vj.)",
  ONCE_PER_YEAR: "1× pro Jahr",
  PER_EVENT: "pro Fall",
  YEARLY: "jährlich",
  BIANNUAL: "2-jährlich",
};

function BenefitItem({ benefit }: { benefit: BenefitRuleDetail }) {
  const isProgram = benefit.benefit_kind === "PROGRAM";
  const periodLabel = benefit.reset_period
    ? (RESET_PERIOD_LABEL[benefit.reset_period] ?? benefit.reset_period)
    : benefit.benefit_kind
    ? RESET_PERIOD_LABEL[benefit.benefit_kind] ?? null
    : null;

  return (
    <div className="px-4 py-3 border-b border-kc-borderLight last:border-0">
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[14px] font-medium text-kc-text">{benefit.benefit_name}</span>
            {isProgram && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-green-100 text-green-700">
                Programm
              </span>
            )}
            {benefit.benefit_kind === "DEDUCTIBLE" && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700">
                Selbstbehalt
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
            {periodLabel && <span className="text-[11px] text-kc-textSec">{periodLabel}</span>}
            {benefit.reimbursement_pct != null && (
              <span className="text-[11px] text-kc-textSec">{benefit.reimbursement_pct}% Erstattung</span>
            )}
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          {benefit.limit_amount != null ? (
            <span className="text-[14px] font-bold text-kc-accent tabular-nums">{formatEUR(benefit.limit_amount)}</span>
          ) : (
            <span className="text-[13px] font-semibold text-green-600">inkl.</span>
          )}
        </div>
      </div>

      {/* Usage bar (only for BUDGET with a limit) */}
      {benefit.limit_amount != null && !isProgram && (
        <ProgressBar used={benefit.amount_used} limit={benefit.limit_amount} />
      )}

      {/* PROGRAM: show used/not-used indicator */}
      {isProgram && (
        <div className="flex items-center gap-1.5 mt-1">
          {benefit.amount_used > 0 ? (
            <span className="text-[11px] text-green-600 font-medium">✓ genutzt</span>
          ) : (
            <span className="text-[11px] text-amber-600 font-medium">○ noch nicht genutzt</span>
          )}
        </div>
      )}
    </div>
  );
}

function PersonSection({
  person,
  familyMembers,
  activeMember,
}: {
  person: InsuredPersonRead;
  familyMembers: ReturnType<typeof useAppContext>["familyMembers"];
  activeMember: string;
}) {
  // Determine avatar info from matched family member
  const matched = person.family_member_id
    ? familyMembers.find((m) => m.id === person.family_member_id)
    : null;

  // Filter: only show if activeMember matches this person's linked family member
  if (activeMember !== "all" && (!matched || matched.member_key !== activeMember)) {
    return null;
  }

  const allBenefits = person.tariffs.flatMap((t) => t.benefits);

  return (
    <div>
      {/* Person row */}
      <div className="flex items-center gap-3 px-4 py-3 bg-kc-surfaceAlt border-b border-kc-borderLight">
        {matched ? (
          <Avatar initials={matched.initials} color={matched.color} size={32} />
        ) : (
          <div className="w-8 h-8 rounded-full bg-kc-border flex items-center justify-center text-[12px] font-bold text-kc-textSec flex-shrink-0">
            {person.full_name.charAt(0)}
          </div>
        )}
        <div>
          <span className="text-[14px] font-semibold text-kc-text">{person.full_name}</span>
          <div className="flex gap-1.5 mt-0.5 flex-wrap">
            {person.tariffs.map((t) => (
              <span key={t.id} className="text-[10px] font-mono text-kc-textSec bg-kc-border px-1.5 py-0.5 rounded">
                {t.code}
              </span>
            ))}
          </div>
        </div>
      </div>

      {allBenefits.length === 0 && (
        <p className="px-4 py-3 text-[13px] text-kc-textSec">Keine Leistungen</p>
      )}
      {allBenefits.map((benefit) => (
        <BenefitItem key={benefit.id} benefit={benefit} />
      ))}
    </div>
  );
}

export function Benefits() {
  const { activeMember, familyMembers } = useAppContext();
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [coverages, setCoverages] = useState<Record<string, ContractCoverage>>({});
  const navigate = useNavigate();

  const activeMemberObj = familyMembers.find((m) => m.member_key === activeMember);

  useEffect(() => {
    listContracts().then(async (cs) => {
      setContracts(cs);
      const entries = await Promise.all(
        cs.map(async (c) => {
          try {
            return [c.id, await getCoverage(c.id)] as const;
          } catch {
            return [c.id, { contract_id: c.id, insured_persons: [] }] as const;
          }
        })
      );
      setCoverages(Object.fromEntries(entries));
    }).catch(() => {});
  }, []);

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
          const coverage = coverages[contract.id];
          const persons = coverage?.insured_persons ?? [];

          // Check if there's a legacy contract with no insured persons yet
          const hasPersons = persons.length > 0;

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

              {/* No persons yet */}
              {!hasPersons && (
                <div className="flex items-center gap-2 px-4 py-3 text-[13px] text-kc-textSec">
                  <AlertCircle size={15} className="flex-shrink-0" />
                  Polizze noch nicht analysiert. Bitte PDF erneut hochladen.
                </div>
              )}

              {/* Per person */}
              {persons.map((person) => (
                <PersonSection
                  key={person.id}
                  person={person}
                  familyMembers={familyMembers}
                  activeMember={activeMember}
                />
              ))}
            </KCCard>
          );
        })}
      </div>
    </div>
  );
}
