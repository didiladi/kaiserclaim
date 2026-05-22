import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { File as FileIcon, X, CheckCircle, AlertCircle } from "lucide-react";
import { DropZone } from "../components/DropZone";
import { Button } from "../components/Button";
import { useAppContext } from "../state/AppContext";
import { listContracts, getBenefits, uploadInvoice } from "../api";
import type { Contract, BenefitRule } from "../api";
import { BENEFIT_CATEGORIES } from "../lib/tokens";

export function Upload() {
  const { familyMembers } = useAppContext();
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [selectedMember, setSelectedMember] = useState("");
  const [selectedContractId, setSelectedContractId] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [benefits, setBenefits] = useState<BenefitRule[]>([]);
  const [uploading, setUploading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { listContracts().then(setContracts).catch(() => {}); }, []);

  useEffect(() => {
    if (selectedContractId) getBenefits(selectedContractId).then(setBenefits).catch(() => setBenefits([]));
    else setBenefits([]);
  }, [selectedContractId]);

  const handleUpload = async () => {
    if (!file) { setError("Bitte zuerst eine Datei wählen."); return; }
    setError("");
    setUploading(true);
    try {
      const member = familyMembers.find((m) => m.member_key === selectedMember);
      await uploadInvoice(file, {
        familyMemberId: member?.id,
        category: selectedCategory || undefined,
      });
      setSuccess(true);
      setTimeout(() => navigate("/invoices"), 1500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload fehlgeschlagen");
      setUploading(false);
    }
  };

  if (success) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 px-6">
        <div className="w-[72px] h-[72px] rounded-full bg-green-50 flex items-center justify-center animate-kcPop">
          <CheckCircle size={36} className="text-green-600" />
        </div>
        <p className="text-[20px] font-bold text-kc-text">Beleg hochgeladen</p>
        <p className="text-[14px] text-kc-textSec text-center">Ihr Beleg wird jetzt verarbeitet.</p>
      </div>
    );
  }

  return (
    <div className="px-5 py-6 flex flex-col gap-5">
      <div>
        <h1 className="text-[22px] font-bold text-kc-text">Beleg hochladen</h1>
        <p className="text-[14px] text-kc-textSec mt-1">Foto oder PDF Ihres Belegs</p>
      </div>

      {!file ? (
        <DropZone onFile={setFile} />
      ) : (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-kc-surfaceAlt border border-kc-border">
          <FileIcon size={22} className="text-kc-accent flex-shrink-0" />
          <span className="flex-1 text-[14px] text-kc-text truncate">{file.name}</span>
          <button onClick={() => setFile(null)} className="text-kc-textTri hover:text-kc-danger">
            <X size={18} />
          </button>
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <label className="text-[13px] font-semibold text-kc-textSec">Familienmitglied</label>
        <select
          className="h-12 bg-kc-surfaceAlt rounded-md px-3.5 text-[15px] text-kc-text border border-transparent focus:outline-none focus:border-kc-accent"
          value={selectedMember}
          onChange={(e) => setSelectedMember(e.target.value)}
        >
          <option value="">— Optional —</option>
          {familyMembers.map((m) => (
            <option key={m.member_key} value={m.member_key}>{m.name}</option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-[13px] font-semibold text-kc-textSec">Vertrag</label>
        <select
          className="h-12 bg-kc-surfaceAlt rounded-md px-3.5 text-[15px] text-kc-text border border-transparent focus:outline-none focus:border-kc-accent"
          value={selectedContractId}
          onChange={(e) => setSelectedContractId(e.target.value)}
        >
          <option value="">— Optional —</option>
          {contracts.map((c) => (
            <option key={c.id} value={c.id}>{c.provider_name}{c.policy_number ? ` — ${c.policy_number}` : ""}</option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-[13px] font-semibold text-kc-textSec">Leistung</label>
        <select
          className="h-12 bg-kc-surfaceAlt rounded-md px-3.5 text-[15px] text-kc-text border border-transparent focus:outline-none focus:border-kc-accent"
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
        >
          <option value="">— Optional —</option>
          {(benefits.length > 0 ? benefits.map((b) => b.benefit_name) : BENEFIT_CATEGORIES).map((cat) => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-kc-dangerBg text-kc-danger text-[13px]">
          <AlertCircle size={16} className="flex-shrink-0" />
          {error}
        </div>
      )}

      <Button fullWidth size="lg" onClick={handleUpload} loading={uploading} disabled={!file}>
        Beleg hochladen
      </Button>
    </div>
  );
}
