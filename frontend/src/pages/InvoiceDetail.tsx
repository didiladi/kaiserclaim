import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Send, CheckCircle, XCircle } from "lucide-react";
import { getInvoice, submitToMerkur } from "../api";
import type { Invoice } from "../api";
import { useAppContext } from "../state/AppContext";
import { StatusPill } from "../components/StatusPill";
import { Stepper } from "../components/Stepper";
import { Button } from "../components/Button";
import { KCCard } from "../components/KCCard";
import { Avatar } from "../components/Avatar";
import { formatEUR, formatDate } from "../lib/format";
import { getPipelineSteps, getCurrentStepIndex } from "../lib/pipeline";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-3 px-4 border-b border-kc-borderLight last:border-0">
      <span className="text-[13px] text-kc-textSec">{label}</span>
      <span className="text-[14px] font-medium text-kc-text text-right max-w-[60%] truncate">{value}</span>
    </div>
  );
}

export function InvoiceDetail() {
  const { id } = useParams<{ id: string }>();
  const { familyMembers } = useAppContext();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    let active = true;
    const load = async () => {
      try {
        const data = await getInvoice(id!);
        if (active) setInvoice(data);
        const polling = data.status === "RECEIVED" || data.status === "OCR_PROCESSING";
        if (active && polling) {
          setTimeout(load, 3000);
        }
      } catch {
        if (active) setError("Beleg konnte nicht geladen werden");
      }
    };
    load();
    return () => { active = false; };
  }, [id]);

  if (error) return <p className="p-6 text-kc-danger">{error}</p>;
  if (!invoice) return <p className="p-6 text-kc-textTri">Wird geladen…</p>;

  const member = familyMembers.find((m) => m.id === invoice.family_member_id);
  const variant = invoice.pipeline ?? "standard";
  const steps = getPipelineSteps(variant);
  const currentIdx = getCurrentStepIndex(invoice.status, variant);

  const handleMerkur = async () => {
    if (!id) return;
    setSubmitting(true);
    try {
      const updated = await submitToMerkur(id);
      setInvoice(updated);
    } catch {
      setError("Übermittlung fehlgeschlagen");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="px-5 py-6 flex flex-col gap-4">
      {/* Summary card */}
      <KCCard>
        <div className="flex items-center justify-between px-4 py-3 bg-kc-surfaceAlt rounded-t-lg border-b border-kc-borderLight">
          <span className="text-[13px] font-semibold text-kc-textSec">Belegdetails</span>
          <StatusPill status={invoice.status} size="md" />
        </div>
        <div>
          {member && (
            <div className="flex items-center gap-3 px-4 py-3 border-b border-kc-borderLight">
              <Avatar initials={member.initials} color={member.color} size={32} />
              <span className="text-[14px] font-medium text-kc-text">{member.name}</span>
            </div>
          )}
          <Row label="Betrag" value={invoice.amount != null ? formatEUR(invoice.amount) : "—"} />
          <Row label="Datum" value={formatDate(invoice.date)} />
          <Row label="Anbieter" value={invoice.provider_name ?? "—"} />
          <Row label="Patient" value={invoice.patient_name ?? "—"} />
          <Row label="Kategorie" value={invoice.category ?? "—"} />
          <Row label="Hochgeladen am" value={formatDate(invoice.created_at)} />
        </div>
      </KCCard>

      {/* Merkur result card */}
      {(invoice.status === "MERKUR_REIMBURSED" || invoice.status === "MERKUR_REJECTED") && (
        <KCCard>
          <div className={`flex items-center gap-3 px-4 py-3 rounded-t-lg border-b border-kc-borderLight ${
            invoice.status === "MERKUR_REIMBURSED" ? "bg-green-50" : "bg-red-50"
          }`}>
            {invoice.status === "MERKUR_REIMBURSED" ? (
              <CheckCircle size={20} className="text-green-600 shrink-0" />
            ) : (
              <XCircle size={20} className="text-red-600 shrink-0" />
            )}
            <span className={`text-[14px] font-semibold ${
              invoice.status === "MERKUR_REIMBURSED" ? "text-green-700" : "text-red-700"
            }`}>
              {invoice.status === "MERKUR_REIMBURSED" ? "Merkur hat erstattet" : "Merkur hat abgelehnt"}
            </span>
          </div>
          {invoice.status === "MERKUR_REIMBURSED" && invoice.reimbursed_amount != null && (
            <div className="flex items-center justify-between px-4 py-3">
              <span className="text-[13px] text-kc-textSec">Erstattungsbetrag</span>
              <span className="text-[18px] font-bold text-green-700">
                {formatEUR(invoice.reimbursed_amount)}
              </span>
            </div>
          )}
          {invoice.amount != null && invoice.reimbursed_amount != null && (
            <div className="flex items-center justify-between px-4 py-2 border-t border-kc-borderLight">
              <span className="text-[13px] text-kc-textSec">Eigenanteil</span>
              <span className="text-[14px] font-medium text-kc-textSec">
                {formatEUR(invoice.amount - invoice.reimbursed_amount)}
              </span>
            </div>
          )}
        </KCCard>
      )}

      {/* Merkur submit CTA */}
      {(invoice.status === "OEGK_REFUNDED" || invoice.status === "READY_FOR_MERKUR") && (
        <Button fullWidth size="lg" onClick={handleMerkur} loading={submitting}>
          <Send size={18} /> An Merkur übermitteln
        </Button>
      )}

      {/* Pipeline card */}
      <KCCard className="p-4">
        <div className="flex items-center justify-between mb-4">
          <span className="text-[17px] font-bold text-kc-text">Erstattungs-Pipeline</span>
          <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-kc-surfaceAlt text-kc-textSec">
            {variant === "pharmacy" ? "Apotheke" : "Standardweg"}
          </span>
        </div>
        <Stepper steps={steps} currentIdx={currentIdx} />
      </KCCard>
    </div>
  );
}
