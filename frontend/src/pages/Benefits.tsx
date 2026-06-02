import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Shield, Plus, AlertCircle, ChevronDown, ChevronRight } from "lucide-react";
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

// ---------------------------------------------------------------------------
// Grouping logic
// ---------------------------------------------------------------------------

type GroupKey = "programme" | "vorsorge" | "fallbezogen" | "selbstbehalt";

const GROUPS: { key: GroupKey; label: string; defaultCollapsed: boolean }[] = [
  { key: "programme",   label: "Programme",                defaultCollapsed: true  },
  { key: "vorsorge",    label: "Vorsorge & Jahresleistungen", defaultCollapsed: true  },
  { key: "fallbezogen", label: "Fallbezogene Leistungen",  defaultCollapsed: true  },
  { key: "selbstbehalt",label: "Selbstbehalt",             defaultCollapsed: true  },
];

function getBenefitGroup(b: BenefitRuleDetail): GroupKey {
  if (b.benefit_kind === "DEDUCTIBLE") return "selbstbehalt";
  if (b.benefit_kind === "PROGRAM") return "programme";
  if (
    b.reset_period === "CALENDAR_YEAR" ||
    b.reset_period === "ONCE_PER_YEAR" ||
    b.reset_period === "INSURANCE_YEAR"
  ) return "vorsorge";
  return "fallbezogen";
}

// ---------------------------------------------------------------------------
// Cross-person deduplication
// Removes benefits that appear under multiple persons when they are
// age-specific (name contains "Kind", age ranges like "1-6 Jahre", etc.).
// Keeps the benefit only under the youngest person (smallest birth_date).
// For non-age-specific duplicates appearing in ALL persons, keeps only the first.
// ---------------------------------------------------------------------------

const _AGE_SPECIFIC_PATTERN = /kind|baby|jugend|\d+[-–]\d+\s*jahr/i;

function deduplicateBenefitsAcrossPersons(
  persons: InsuredPersonRead[]
): InsuredPersonRead[] {
  if (persons.length <= 1) return persons;

  // Build map: benefit_name → list of (personIndex, tariffIndex, benefitIndex)
  type Loc = { pi: number; ti: number; bi: number };
  const nameMap = new Map<string, Loc[]>();

  persons.forEach((person, pi) => {
    person.tariffs.forEach((tariff, ti) => {
      tariff.benefits.forEach((b, bi) => {
        const key = b.benefit_name.trim().toLowerCase();
        if (!nameMap.has(key)) nameMap.set(key, []);
        nameMap.get(key)!.push({ pi, ti, bi });
      });
    });
  });

  // Collect (personIndex, tariffIndex, benefitIndex) to remove
  const toRemove = new Set<string>();

  for (const [, locs] of nameMap) {
    if (locs.length <= 1) continue;

    const benefit = persons[locs[0].pi].tariffs[locs[0].ti].benefits[locs[0].bi];
    const isAgeSpecific = _AGE_SPECIFIC_PATTERN.test(benefit.benefit_name);

    let keepPi: number;
    if (isAgeSpecific) {
      // Keep under the youngest person (most recent birth_date = largest timestamp)
      const withBirth = persons
        .map((p, i) => ({ i, birth: p.birth_date ? new Date(p.birth_date).getTime() : null }))
        .filter((x) => x.birth !== null && locs.some((l) => l.pi === x.i));
      if (withBirth.length > 0) {
        keepPi = withBirth.reduce((a, b) => (b.birth! > a.birth! ? b : a)).i;
      } else {
        keepPi = locs[0].pi;
      }
    } else {
      // Non-age-specific duplicate across ALL persons: keep under the first person
      const uniquePersons = new Set(locs.map((l) => l.pi));
      if (uniquePersons.size < persons.length) continue; // not in all — keep all
      keepPi = locs[0].pi;
    }

    for (const loc of locs) {
      if (loc.pi !== keepPi) {
        toRemove.add(`${loc.pi}-${loc.ti}-${loc.bi}`);
      }
    }
  }

  if (toRemove.size === 0) return persons;

  return persons.map((person, pi) => ({
    ...person,
    tariffs: person.tariffs.map((tariff, ti) => ({
      ...tariff,
      benefits: tariff.benefits.filter(
        (_, bi) => !toRemove.has(`${pi}-${ti}-${bi}`)
      ),
    })),
  }));
}

// ---------------------------------------------------------------------------
// BenefitItem
// ---------------------------------------------------------------------------

function BenefitItem({ benefit }: { benefit: BenefitRuleDetail }) {
  const isProgram = benefit.benefit_kind === "PROGRAM";
  const periodLabel = benefit.reset_period
    ? (RESET_PERIOD_LABEL[benefit.reset_period] ?? benefit.reset_period)
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

      {benefit.limit_amount != null && !isProgram && (
        <ProgressBar used={benefit.amount_used} limit={benefit.limit_amount} />
      )}

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

// ---------------------------------------------------------------------------
// BenefitGroupSection — collapsible group with chevron + count badge
// ---------------------------------------------------------------------------

function BenefitGroupSection({
  label,
  benefits,
  collapsed,
  onToggle,
}: {
  label: string;
  benefits: BenefitRuleDetail[];
  collapsed: boolean;
  onToggle: () => void;
}) {
  if (benefits.length === 0) return null;

  const unusedPrograms = benefits.filter(
    (b) => b.benefit_kind === "PROGRAM" && b.amount_used === 0
  ).length;

  return (
    <div>
      {/* Group header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-kc-surfaceAlt border-b border-kc-borderLight hover:bg-kc-border/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          {collapsed ? (
            <ChevronRight size={14} className="text-kc-textSec flex-shrink-0" />
          ) : (
            <ChevronDown size={14} className="text-kc-textSec flex-shrink-0" />
          )}
          <span className="text-[12px] font-semibold text-kc-textSec uppercase tracking-wider">
            {label}
          </span>
          <span className="text-[11px] text-kc-textSec bg-kc-border px-1.5 py-0.5 rounded-full">
            {benefits.length}
          </span>
          {unusedPrograms > 0 && (
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700">
              {unusedPrograms} ungenutzt
            </span>
          )}
        </div>
      </button>

      {/* Benefit rows */}
      {!collapsed && benefits.map((b) => <BenefitItem key={b.id} benefit={b} />)}
    </div>
  );
}

// ---------------------------------------------------------------------------
// PersonSection — one insured person with grouped benefits
// ---------------------------------------------------------------------------

function PersonSection({
  person,
  familyMembers,
  activeMember,
}: {
  person: InsuredPersonRead;
  familyMembers: ReturnType<typeof useAppContext>["familyMembers"];
  activeMember: string;
}) {
  const [collapsedGroups, setCollapsedGroups] = useState<Record<GroupKey, boolean>>({
    programme: true,
    vorsorge: true,
    fallbezogen: true,
    selbstbehalt: true,
  });

  const matched = person.family_member_id
    ? familyMembers.find((m) => m.id === person.family_member_id)
    : null;

  if (activeMember !== "all" && (!matched || matched.member_key !== activeMember)) {
    return null;
  }

  const allBenefits = person.tariffs.flatMap((t) => t.benefits);

  const grouped: Record<GroupKey, BenefitRuleDetail[]> = {
    programme: [],
    vorsorge: [],
    fallbezogen: [],
    selbstbehalt: [],
  };
  for (const b of allBenefits) {
    grouped[getBenefitGroup(b)].push(b);
  }

  const toggle = (key: GroupKey) =>
    setCollapsedGroups((prev) => ({ ...prev, [key]: !prev[key] }));

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

      {GROUPS.map(({ key, label }) => (
        <BenefitGroupSection
          key={key}
          label={label}
          benefits={grouped[key]}
          collapsed={collapsedGroups[key]}
          onToggle={() => toggle(key)}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Benefits page
// ---------------------------------------------------------------------------

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

              {!hasPersons && (
                <div className="flex items-center gap-2 px-4 py-3 text-[13px] text-kc-textSec">
                  <AlertCircle size={15} className="flex-shrink-0" />
                  Polizze noch nicht analysiert. Bitte PDF erneut hochladen.
                </div>
              )}

              {deduplicateBenefitsAcrossPersons(persons).map((person) => (
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
