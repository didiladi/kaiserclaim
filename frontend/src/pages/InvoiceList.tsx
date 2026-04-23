import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listInvoices, Invoice, InvoiceStatus } from "../api";

const TERMINAL: InvoiceStatus[] = ["COMPLETED", "MERKUR_SUBMITTED", "READY_FOR_MERKUR"];

const STATUS_LABEL: Record<InvoiceStatus, string> = {
  RECEIVED: "Received",
  OCR_PROCESSING: "OCR…",
  READY_FOR_OEGK: "Ready for ÖGK",
  OEGK_SUBMITTED: "ÖGK Submitted",
  OEGK_REFUNDED: "ÖGK Refunded",
  READY_FOR_MERKUR: "Ready for Merkur",
  MERKUR_SUBMITTED: "Merkur Submitted",
  COMPLETED: "Completed",
};

const STATUS_COLOR: Record<InvoiceStatus, string> = {
  RECEIVED: "bg-gray-100 text-gray-600",
  OCR_PROCESSING: "bg-yellow-100 text-yellow-700",
  READY_FOR_OEGK: "bg-blue-100 text-blue-700",
  OEGK_SUBMITTED: "bg-blue-100 text-blue-700",
  OEGK_REFUNDED: "bg-indigo-100 text-indigo-700",
  READY_FOR_MERKUR: "bg-orange-100 text-orange-700",
  MERKUR_SUBMITTED: "bg-purple-100 text-purple-700",
  COMPLETED: "bg-green-100 text-green-700",
};

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function InvoiceList() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const data = await listInvoices();
        if (active) setInvoices(data);
        const hasActive = data.some((inv) => !TERMINAL.includes(inv.status));
        if (active && hasActive) setTimeout(load, 3000);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load");
      }
    }

    load();
    return () => { active = false; };
  }, []);

  if (error) return <p className="mt-6 text-red-600">{error}</p>;

  return (
    <div className="mt-6">
      <h1 className="text-xl font-bold mb-4">Invoices</h1>
      {invoices.length === 0 && (
        <p className="text-gray-500 text-sm">No invoices yet. Upload a receipt to get started.</p>
      )}
      <ul className="space-y-2">
        {invoices.map((inv) => (
          <li key={inv.id}>
            <Link
              to={`/invoices/${inv.id}`}
              className="flex items-center justify-between bg-white rounded-xl px-4 py-3 shadow-sm hover:shadow-md transition-shadow"
            >
              <div>
                <p className="font-medium text-gray-900">
                  {inv.date ? new Date(inv.date).toLocaleDateString("de-AT") : "—"}
                  {inv.amount != null && (
                    <span className="ml-2 text-gray-600">€{inv.amount.toFixed(2)}</span>
                  )}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">{timeAgo(inv.created_at)}</p>
              </div>
              <span className={`text-xs font-medium px-2 py-1 rounded-full ${STATUS_COLOR[inv.status]}`}>
                {STATUS_LABEL[inv.status]}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
