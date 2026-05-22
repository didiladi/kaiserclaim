import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle, CreditCard } from "lucide-react";
import { DropZone } from "../components/DropZone";
import { Input } from "../components/Input";
import { Button } from "../components/Button";
import { KCCard } from "../components/KCCard";
import { createContract, parseContractPdf } from "../api";
import type { BenefitRule } from "../api";
import { formatEUR } from "../lib/format";
import clsx from "clsx";

const PROVIDERS = ["Merkur", "UNIQA", "Generali", "Wiener Städtische", "Allianz"];

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

export function Onboarding() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [provider, setProvider] = useState("");
  const [policyNumber, setPolicyNumber] = useState("");
  const [contractId, setContractId] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [parsing, setParsing] = useState(false);
  const [parseProgress, setParseProgress] = useState(0);
  const [parsedRules, setParsedRules] = useState<BenefitRule[]>([]);
  const [saving, setSaving] = useState(false);

  const handleStep1 = async () => {
    const contract = await createContract({ provider_name: provider, policy_number: policyNumber || undefined });
    setContractId(contract.id);
    setStep(2);
  };

  const handleParse = async () => {
    if (!pdfFile || !contractId) return;
    setParsing(true);
    setParseProgress(0);
    const interval = setInterval(() => setParseProgress((p) => Math.min(p + 5, 95)), 130);
    try {
      const rules = await parseContractPdf(contractId, pdfFile);
      clearInterval(interval);
      setParseProgress(100);
      setParsedRules(rules);
      setTimeout(() => setStep(3), 300);
    } catch {
      clearInterval(interval);
      setParsing(false);
    }
  };

  const handleSave = () => {
    setSaving(true);
    setTimeout(() => navigate("/benefits"), 500);
  };

  const PERIOD_LABEL: Record<string, string> = { YEARLY: "jährlich", BIANNUAL: "2-jährlich" };

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
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-[13px] text-kc-textSec">
                <div className="w-4 h-4 border-2 border-kc-accent border-t-transparent rounded-full animate-kcSpin" />
                Vertrag wird analysiert…
              </div>
              <div className="h-1.5 rounded-full bg-kc-surfaceAlt overflow-hidden">
                <div className="h-full bg-kc-accent rounded-full transition-all duration-300" style={{ width: `${parseProgress}%` }} />
              </div>
            </div>
          )}
          <Button fullWidth size="lg" disabled={!pdfFile || parsing} loading={parsing} onClick={handleParse}>
            Vertrag analysieren
          </Button>
        </div>
      )}

      {step === 3 && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col items-center gap-3 py-4">
            <div className="w-14 h-14 rounded-full bg-green-50 flex items-center justify-center">
              <CheckCircle size={32} className="text-green-600" />
            </div>
            <h2 className="text-[20px] font-bold text-kc-text">Vertrag analysiert</h2>
          </div>
          <KCCard className="divide-y divide-kc-borderLight">
            {parsedRules.map((rule) => (
              <div key={rule.id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-[14px] font-medium text-kc-text">{rule.benefit_name}</p>
                  <p className="text-[12px] text-kc-textSec">{PERIOD_LABEL[rule.limit_type] ?? rule.limit_type}</p>
                </div>
                <span className="text-[14px] font-bold text-kc-accent tabular-nums">{formatEUR(rule.limit_amount)}</span>
              </div>
            ))}
            {parsedRules.length === 0 && (
              <p className="px-4 py-3 text-[13px] text-kc-textSec">Keine Leistungen erkannt.</p>
            )}
          </KCCard>
          <Button fullWidth size="lg" loading={saving} onClick={handleSave}>
            Vertrag speichern
          </Button>
        </div>
      )}
    </div>
  );
}
