export const USER_ID = "00000000-0000-0000-0000-000000000001";

const BASE = "/api/v1";

export interface Invoice {
  id: string;
  user_id: string;
  file_path: string;
  provider_name: string | null;
  patient_name: string | null;
  amount: number | null;
  date: string | null;
  benefit_rule_id: string | null;
  status: InvoiceStatus;
  created_at: string;
  updated_at: string;
}

export type InvoiceStatus =
  | "RECEIVED"
  | "OCR_PROCESSING"
  | "READY_FOR_OEGK"
  | "OEGK_SUBMITTED"
  | "OEGK_REFUNDED"
  | "READY_FOR_MERKUR"
  | "MERKUR_SUBMITTED"
  | "COMPLETED";

export interface Contract {
  id: string;
  user_id: string;
  provider_name: string;
  policy_number: string | null;
  created_at: string;
}

export interface BenefitRule {
  id: string;
  contract_id: string;
  benefit_name: string;
  limit_amount: number;
  limit_type: "YEARLY" | "BIANNUAL";
  reset_date: string | null;
  amount_used: number;
  amount_remaining: number;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const sep = path.includes("?") ? "&" : "?";
  const res = await fetch(`${BASE}${path}${sep}user_id=${USER_ID}`, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export function listInvoices(): Promise<Invoice[]> {
  return apiFetch<Invoice[]>("/invoices/");
}

export function getInvoice(id: string): Promise<Invoice> {
  return apiFetch<Invoice>(`/invoices/${id}`);
}

export async function uploadInvoice(file: File, benefitRuleId?: string): Promise<Invoice> {
  const form = new FormData();
  form.append("file", file);
  if (benefitRuleId) form.append("benefit_rule_id", benefitRuleId);
  const sep = "?";
  const res = await fetch(`${BASE}/invoices/upload${sep}user_id=${USER_ID}`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<Invoice>;
}

export function submitToMerkur(id: string): Promise<Invoice> {
  return apiFetch<Invoice>(`/invoices/${id}/submit-merkur`, { method: "POST" });
}

export function listContracts(): Promise<Contract[]> {
  return apiFetch<Contract[]>("/contracts/");
}

export function getBenefits(contractId: string): Promise<BenefitRule[]> {
  return apiFetch<BenefitRule[]>(`/contracts/${contractId}/benefits`);
}
