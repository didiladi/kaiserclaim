import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getInvoice, submitToMerkur, Invoice, InvoiceStatus } from "../api";

const STEPS: InvoiceStatus[] = [
  "RECEIVED",
  "OCR_PROCESSING",
  "READY_FOR_MERKUR",
  "MERKUR_SUBMITTED",
  "COMPLETED",
];

const STEP_LABEL: Partial<Record<InvoiceStatus, string>> = {
  RECEIVED: "Received",
  OCR_PROCESSING: "OCR Processing",
  READY_FOR_MERKUR: "Ready for Merkur",
  MERKUR_SUBMITTED: "Merkur Submitted",
  COMPLETED: "Completed",
};

export default function InvoiceDetail() {
  const { id } = useParams<{ id: string }>();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) return;
    let active = true;

    async function load() {
      try {
        const data = await getInvoice(id!);
        if (active) setInvoice(data);
        const inProgress = data.status === "RECEIVED" || data.status === "OCR_PROCESSING";
        if (active && inProgress) setTimeout(load, 3000);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load");
      }
    }

    load();
    return () => { active = false; };
  }, [id]);

  async function handleSubmitMerkur() {
    if (!id) return;
    setSubmitting(true);
    try {
      const updated = await submitToMerkur(id);
      setInvoice(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (error) return <p className="mt-6 text-red-600">{error}</p>;
  if (!invoice) return <p className="mt-6 text-gray-400">Loading…</p>;

  const currentStep = STEPS.indexOf(invoice.status);

  return (
    <div className="mt-6 space-y-4">
      <Link to="/invoices" className="text-sm text-blue-600 hover:underline">← Back</Link>

      <h1 className="text-xl font-bold">Invoice Detail</h1>

      <div className="bg-white rounded-xl shadow-sm p-4 space-y-2">
        <Row label="Status" value={invoice.status} />
        <Row label="Amount" value={invoice.amount != null ? `€${invoice.amount.toFixed(2)}` : "—"} />
        <Row label="Date" value={invoice.date ? new Date(invoice.date).toLocaleDateString("de-AT") : "—"} />
        <Row label="Provider" value={invoice.provider_name ?? "—"} />
        <Row label="Patient" value={invoice.patient_name ?? "—"} />
        <Row label="Uploaded" value={new Date(invoice.created_at).toLocaleString("de-AT")} />
      </div>

      <div className="bg-white rounded-xl shadow-sm p-4">
        <p className="text-sm font-semibold text-gray-600 mb-3">Pipeline</p>
        <ol className="space-y-2">
          {STEPS.map((step, i) => (
            <li key={step} className="flex items-center gap-3 text-sm">
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0
                ${i < currentStep ? "bg-green-500 text-white" :
                  i === currentStep ? "bg-blue-500 text-white" :
                  "bg-gray-200 text-gray-400"}`}>
                {i < currentStep ? "✓" : i + 1}
              </span>
              <span className={i <= currentStep ? "text-gray-900" : "text-gray-400"}>
                {STEP_LABEL[step]}
              </span>
            </li>
          ))}
        </ol>
      </div>

      {invoice.status === "READY_FOR_MERKUR" && (
        <button
          onClick={handleSubmitMerkur}
          disabled={submitting}
          className="w-full py-3 rounded-xl bg-orange-500 text-white font-semibold disabled:opacity-40 hover:bg-orange-600 transition-colors"
        >
          {submitting ? "Submitting…" : "Submit to Merkur"}
        </button>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-900">{value}</span>
    </div>
  );
}
