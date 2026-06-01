import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle, CreditCard, User } from "lucide-react";
import { DropZone } from "../components/DropZone";
import { Input } from "../components/Input";
import { Button } from "../components/Button";
import { KCCard } from "../components/KCCard";
import { createContract, parseContractPdf } from "../api";
import type { ContractCoverage, BenefitRuleDetail } from "../api";
import { formatEUR } from "../lib/format";
import clsx from "clsx";

const PROVIDERS = ["Merkur", "UNIQA", "Generali", "Wiener Städtische", "Allianz"];

const RESET_PERIOD_LABEL: Record<string, string> = {
  CALENDAR_YEAR: "jährlich (Kj.)",
  INSURANCE_YEAR: "jährlich (Vj.)",
  ONCE_PER_YEAR: "1× pro Jahr",
  PER_EVENT: "pro Fall",
};

const BENEFIT_KIND_BADGE: Record<string, { label: string; bg: string; text: string }> = {
  BUDGET: { label: "Budget", bg: "#DBEAFE", text: "#1D4ED8" },
  PROGRAM: { label: "Programm", bg: "#DCFCE7", text: "#15803D" },
  DEDUCTIBLE: { label: "Selbstbehalt", bg: "#FEF9C3", text: "#A16207" },
};

function StepIndicator({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {[1, 2, 3].map((n) => (
        <div key={n} className="flex items-center gap-2">
          <div
            className={clsx(
              "w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-bold",
              n <= current ? "bg-kc-accent text-white" : "bg-kc-surfaceAlt text-kc-textSec"
            )}
          >
            {n}
          </div>
          {n < 3 && <div className={clsx("h-0.5 w-8 rounded", n < current ? "bg-kc-accent" : "bg-kc-border")} />}
        </div>
      ))}
    </div>
  );
}

function BenefitRow({ benefit }: { benefit: BenefitRuleDetail }) {
  const badge = benefit.benefit_kind ? BENEFIT_KIND_BADGE[benefit.benefit_kind] : null;
  const periodLabel = benefit.reset_period ? (RESET_PERIOD_LABEL[benefit.reset_period] ?? benefit.reset_period) : null;

  return (
    <div className="flex items-start justify-between px-4 py-3 border-b border-kc-borderLight last:border-0">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[14px] font-medium text-kc-text">{benefit.benefit_name}</span>
          {badge && (
            <span
              className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full"
              style={{ background: badge.bg, color: badge.text }}
            >
              {badge.label}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
          {periodLabel && (
            <span className="text-[11px] text-kc-textSec">{periodLabel}</span>
          )}
          {benefit.reimbursement_pct != null && (
            <span className="text-[11px] text-kc-textSec">{benefit.reimbursement_pct}% Erstattung</span>
          )}
          {benefit.notes && (
            <span className="text-[11px] text-kc-textSec italic">{benefit.notes}</span>
          )}
        </div>
      </div>
      <div className="text-right ml-3 flex-shrink-0">
        {benefit.limit_amount != null ? (
          <span className="text-[14px] font-bold text-kc-accent tabular-nums">{formatEUR(benefit.limit_amount)}</span>
        ) : (
          <span className="text-[13px] font-semibold text-green-600">inklusive</span>
        )}
      </div>
    </div>
  );
}

const PARSE_STAGES = [
  { label: "Dokument wird eingelesen…",          until: 15 },
  { label: "Text wird extrahiert…",              until: 30 },
  { label: "KI analysiert versicherte Personen…", until: 60 },
  { label: "KI analysiert Leistungen…",          until: 100 },
  { label: "Ergebnisse werden gespeichert…",     until: Infinity },
];

function useParseStage(parsing: boolean) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!parsing) { setElapsed(0); return; }
    const t = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(t);
  }, [parsing]);
  const stage = PARSE_STAGES.find((s) => elapsed < s.until) ?? PARSE_STAGES[PARSE_STAGES.length - 1];
  return { label: stage.label, elapsed };
}

export function Onboarding() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [provider, setProvider] = useState("");
  const [policyNumber, setPolicyNumber] = useState("");
  const [contractId, setContractId] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [parsing, setParsing] = useState(false);
  const [parseProgress, setParseProgress] = useState(0);
  const [parseError, setParseError] = useState<string | null>(null);
  const [coverage, setCoverage] = useState<ContractCoverage | null>(null);
  const [saving, setSaving] = useState(false);
  const { label: parseStageLabel, elapsed: parseElapsed } = useParseStage(parsing);

  const handleStep1 = async () => {
    const contract = await createContract({ provider_name: provider, policy_number: policyNumber || undefined });
    setContractId(contract.id);
    setStep(2);
  };

  const handleParse = async () => {
    if (!pdfFile || !contractId) return;
    setParsing(true);
    setParseProgress(0);
    setParseError(null);
    // Slow crawl to 90% over ~110s so the bar keeps moving for the full Gemini extraction
    const interval = setInterval(() => setParseProgress((p) => Math.min(p + 90 / 110, 90)), 1000);
    try {
      const result = await parseContractPdf(contractId, pdfFile);
      clearInterval(interval);
      setParseProgress(100);
      setCoverage(result);
      setTimeout(() => setStep(3), 300);
    } catch (err) {
      clearInterval(interval);
      setParseError(err instanceof Error ? err.message : "Analyse fehlgeschlagen. Bitte erneut versuchen.");
      setParsing(false);
    }
  };

  const handleSave = () => {
    setSaving(true);
    setTimeout(() => navigate("/benefits"), 500);
  };

  const totalBenefits = coverage?.insured_persons.reduce(
    (sum, p) => sum + p.tariffs.reduce((s, t) => s + t.benefits.length, 0),
    0
  ) ?? 0;

  return (
    <div className="px-5 py-6">
      <StepIndicator current={step} />

      {step === 1 && (
        <div className="flex flex-col gap-4">
          <h2 className="text-[20px] font-bold text-kc-text">Versicherungsdetails</h2>
          <div className="flex flex-col gap-1.5">
            <label className="text-[13px] font-semibold text-kc-textSec">Versicherer</label>
            <select
              className="h-12 bg-kc-surfaceAlt rounded-md px-3.5 text-[15px] text-kc-text border border-transparent focus:outline-none focus:border-kc-accent"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            >
              <option value="">— Wählen —</option>
              {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <Input
            label="Polizzennummer"
            placeholder="MS-2024-XXXXX"
            leftIcon={<CreditCard size={18} />}
            value={policyNumber}
            onChange={(e) => setPolicyNumber(e.target.value)}
          />
          <Button fullWidth size="lg" disabled={!provider || !policyNumber} onClick={handleStep1}>
            Weiter
          </Button>
        </div>
      )}

      {step === 2 && (
        <div className="flex flex-col gap-4">
          <h2 className="text-[20px] font-bold text-kc-text">Vertragsdokument</h2>
          <p className="text-[14px] text-kc-textSec">Laden Sie Ihre Versicherungspolizze hoch. KI analysiert die Leistungsgrenzen automatisch.</p>
          {!pdfFile ? (
            <DropZone onFile={setPdfFile} accept=".pdf,application/pdf" />
          ) : (
            <div className="p-4 bg-kc-surfaceAlt rounded-lg text-[14px] text-kc-text">{pdfFile.name}</div>
          )}
          {parsing && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[13px] text-kc-textSec">
                  <div className="w-4 h-4 border-2 border-kc-accent border-t-transparent rounded-full animate-kcSpin flex-shrink-0" />
                  <span>{parseStageLabel}</span>
                </div>
                <span className="text-[12px] text-kc-textSec tabular-nums">{parseElapsed}s</span>
              </div>
              <div className="h-1.5 rounded-full bg-kc-surfaceAlt overflow-hidden">
                <div className="h-full bg-kc-accent rounded-full transition-all duration-1000" style={{ width: `${parseProgress}%` }} />
              </div>
              <p className="text-[11px] text-kc-textSec text-center">KI-Analyse dauert ca. 1–2 Minuten</p>
            </div>
          )}
          <Button fullWidth size="lg" disabled={!pdfFile || parsing} loading={parsing} onClick={handleParse}>
            Vertrag analysieren
          </Button>
          {parseError && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200">
              <p className="text-[13px] text-red-700 font-medium">Analyse fehlgeschlagen</p>
              <p className="text-[12px] text-red-600 mt-0.5">{parseError}</p>
            </div>
          )}
        </div>
      )}

      {step === 3 && coverage && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col items-center gap-3 py-4">
            <div className="w-14 h-14 rounded-full bg-green-50 flex items-center justify-center">
              <CheckCircle size={32} className="text-green-600" />
            </div>
            <h2 className="text-[20px] font-bold text-kc-text">Vertrag analysiert</h2>
            <p className="text-[13px] text-kc-textSec">
              {coverage.insured_persons.length} versicherte Personen · {totalBenefits} Leistungen erkannt
            </p>
          </div>

          {coverage.insured_persons.length === 0 && (
            <p className="text-[13px] text-kc-textSec text-center">Keine Personen erkannt.</p>
          )}

          {coverage.insured_persons.map((person) => (
            <KCCard key={person.id} className="overflow-hidden">
              {/* Person header */}
              <div className="flex items-center gap-3 px-4 py-3 bg-kc-surfaceAlt border-b border-kc-borderLight">
                <div className="w-8 h-8 rounded-full bg-kc-accentMid flex items-center justify-center flex-shrink-0">
                  <User size={16} className="text-kc-accent" />
                </div>
                <div>
                  <p className="text-[14px] font-semibold text-kc-text">{person.full_name}</p>
                  <p className="text-[11px] text-kc-textSec">
                    {person.kd_nr && `Kd.Nr. ${person.kd_nr}`}
                    {person.family_member_id && <span className="ml-1 text-green-600">✓ zugeordnet</span>}
                  </p>
                </div>
              </div>

              {person.tariffs.map((tariff) => (
                <div key={tariff.id}>
                  {/* Tariff sub-header */}
                  <div className="px-4 py-2 bg-kc-surfaceAlt border-b border-kc-borderLight">
                    <span className="text-[12px] font-semibold text-kc-textSec uppercase tracking-wider">
                      {tariff.code}{tariff.name ? ` — ${tariff.name}` : ""}
                    </span>
                  </div>
                  {tariff.benefits.length === 0 ? (
                    <p className="px-4 py-3 text-[12px] text-kc-textSec">Keine Leistungen</p>
                  ) : (
                    tariff.benefits.map((b) => <BenefitRow key={b.id} benefit={b} />)
                  )}
                </div>
              ))}
            </KCCard>
          ))}

          <Button fullWidth size="lg" loading={saving} onClick={handleSave}>
            Vertrag speichern
          </Button>
        </div>
      )}
    </div>
  );
}
