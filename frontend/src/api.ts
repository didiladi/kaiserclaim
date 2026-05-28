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
  category: string | null;
  family_member_id: string | null;
  status: InvoiceStatus;
  pipeline: "standard" | "pharmacy";
  current_step: number;
  created_at: string;
  updated_at: string;
  reimbursed_amount: number | null;
  result_state: "REIMBURSED" | "REJECTED" | "UNKNOWN" | null;
}

export interface MerkurDocument {
  id: string;
  user_id: string;
  geschaeftsfall_nr: string;
  title: string;
  document_date: string | null;
  file_path: string;
  patient_name: string | null;
  invoice_amount: number | null;
  reimbursed_amount: number | null;
  result_state: "REIMBURSED" | "REJECTED" | "UNKNOWN";
  invoice_id: string | null;
  created_at: string;
}

export type InvoiceStatus =
  | "RECEIVED"
  | "OCR_PROCESSING"
  | "READY_FOR_OEGK"
  | "OEGK_SUBMITTED"
  | "OEGK_REFUNDED"
  | "READY_FOR_MERKUR"
  | "MERKUR_SUBMITTED"
  | "MERKUR_REIMBURSED"
  | "MERKUR_REJECTED"
  | "COMPLETED";

export interface FamilyMember {
  id: string;
  user_id: string;
  member_key: string;
  name: string;
  color: string;
  initials: string;
  created_at: string;
}

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
  limit_amount: number | null;
  limit_type: "YEARLY" | "BIANNUAL" | null;
  reset_date: string | null;
  amount_used: number;
  amount_remaining: number | null;
}

export type BenefitKind = "BUDGET" | "PROGRAM" | "DEDUCTIBLE";
export type ResetPeriod = "CALENDAR_YEAR" | "INSURANCE_YEAR" | "PER_EVENT" | "ONCE_PER_YEAR";

export interface BenefitRuleDetail {
  id: string;
  contract_id: string;
  tariff_id: string | null;
  benefit_name: string;
  benefit_kind: BenefitKind | null;
  limit_amount: number | null;
  reimbursement_pct: number | null;
  reset_period: ResetPeriod | null;
  category: string | null;
  notes: string | null;
  amount_used: number;
  amount_remaining: number | null;
}

export interface TariffRead {
  id: string;
  insured_person_id: string;
  code: string;
  name: string | null;
  description_raw: string | null;
  program_info: string | null;
  benefits: BenefitRuleDetail[];
}

export interface InsuredPersonRead {
  id: string;
  contract_id: string;
  family_member_id: string | null;
  full_name: string;
  kd_nr: string | null;
  birth_date: string | null;
  tariffs: TariffRead[];
}

export interface ContractCoverage {
  contract_id: string;
  insured_persons: InsuredPersonRead[];
}

export interface UnusedAlert {
  benefit_name: string;
  person_name: string | null;
  pct_unused: number;
  limit: number | null;
  days_until_reset: number;
  reset_date: string;
}

export interface DashboardSummary {
  year: number;
  total_paid: number;
  total_reimbursed: number;
  in_progress_count: number;
  eigenanteil: number;
  benefit_alerts: { benefit_name: string; percent_used: number; used: number; limit: number }[];
  unused_alerts: UnusedAlert[];
}

export interface MonthlyStats {
  month: string;
  total: number;
  by_member: Record<string, number>;
}

export interface YearlyStats {
  year: number;
  total_paid: number;
  total_reimbursed: number;
  eigenanteil: number;
}

export interface MemberStats {
  member_key: string;
  name: string;
  color: string;
  initials: string;
  invoice_count: number;
  total_paid: number;
  total_reimbursed: number;
  eigenanteil: number;
  share_pct: number;
  categories: { name: string; amount: number }[];
}

// ---------------------------------------------------------------------------
// HTTP helper
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const sep = path.includes("?") ? "&" : "?";
  const res = await fetch(`${BASE}${path}${sep}user_id=${USER_ID}`, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Invoices
// ---------------------------------------------------------------------------

export function listInvoices(params?: { member_key?: string; status_group?: string; search?: string }): Promise<Invoice[]> {
  const qs = new URLSearchParams();
  if (params?.member_key) qs.set("member_key", params.member_key);
  if (params?.status_group) qs.set("status_group", params.status_group);
  if (params?.search) qs.set("search", params.search);
  const q = qs.toString();
  return apiFetch<Invoice[]>(`/invoices/${q ? "?" + q : ""}`);
}

export function getInvoice(id: string): Promise<Invoice> {
  return apiFetch<Invoice>(`/invoices/${id}`);
}

export async function uploadInvoice(
  file: File,
  opts?: { benefitRuleId?: string; familyMemberId?: string; category?: string }
): Promise<Invoice> {
  const form = new FormData();
  form.append("file", file);
  if (opts?.benefitRuleId) form.append("benefit_rule_id", opts.benefitRuleId);
  if (opts?.familyMemberId) form.append("family_member_id", opts.familyMemberId);
  if (opts?.category) form.append("category", opts.category);
  const res = await fetch(`${BASE}/invoices/upload?user_id=${USER_ID}`, {
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

// ---------------------------------------------------------------------------
// Contracts & benefits
// ---------------------------------------------------------------------------

export function listContracts(): Promise<Contract[]> {
  return apiFetch<Contract[]>("/contracts/");
}

export function getBenefits(contractId: string): Promise<BenefitRule[]> {
  return apiFetch<BenefitRule[]>(`/contracts/${contractId}/benefits`);
}

export function getCoverage(contractId: string): Promise<ContractCoverage> {
  return apiFetch<ContractCoverage>(`/contracts/${contractId}/coverage`);
}

export async function createContract(data: { provider_name: string; policy_number?: string }): Promise<Contract> {
  return apiFetch<Contract>("/contracts/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function parseContractPdf(contractId: string, file: File): Promise<ContractCoverage> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/contracts/${contractId}/parse-pdf?user_id=${USER_ID}`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<ContractCoverage>;
}

// ---------------------------------------------------------------------------
// Family
// ---------------------------------------------------------------------------

export function listFamilyMembers(): Promise<FamilyMember[]> {
  return apiFetch<FamilyMember[]>("/family/");
}

export function createFamilyMember(data: { member_key: string; name: string; color: string; initials: string }): Promise<FamilyMember> {
  return apiFetch<FamilyMember>("/family/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Dashboard & stats
// ---------------------------------------------------------------------------

export function getDashboardSummary(year = 2026, member_key?: string): Promise<DashboardSummary> {
  const qs = `year=${year}${member_key ? `&member_key=${member_key}` : ""}`;
  return apiFetch<DashboardSummary>(`/dashboard/summary?${qs}`);
}

export function getMonthlyStats(year = 2026, member_key?: string): Promise<MonthlyStats[]> {
  const qs = `year=${year}${member_key ? `&member_key=${member_key}` : ""}`;
  return apiFetch<MonthlyStats[]>(`/stats/monthly?${qs}`);
}

export function getYearlyStats(): Promise<YearlyStats[]> {
  return apiFetch<YearlyStats[]>("/stats/yearly");
}

export function getMemberStats(year = 2026): Promise<MemberStats[]> {
  return apiFetch<MemberStats[]>(`/stats/members?year=${year}`);
}

// ---------------------------------------------------------------------------
// Merkur Postfach
// ---------------------------------------------------------------------------

export function triggerMerkurSync(fullHistory = false): Promise<{ task_id: string; full_history: boolean }> {
  return apiFetch(`/merkur/sync?full_history=${fullHistory}`, { method: "POST" });
}

export function listMerkurDocuments(): Promise<MerkurDocument[]> {
  return apiFetch<MerkurDocument[]>("/merkur/documents");
}
