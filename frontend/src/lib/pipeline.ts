export type PipelineVariant = "standard" | "pharmacy";

export interface PipelineStep {
  statusKey: string;
  label: string;
}

const STANDARD_STEPS: PipelineStep[] = [
  { statusKey: "RECEIVED",           label: "Empfangen" },
  { statusKey: "OCR_PROCESSING",     label: "OCR-Verarbeitung" },
  { statusKey: "READY_FOR_OEGK",     label: "Bereit für ÖGK" },
  { statusKey: "OEGK_SUBMITTED",     label: "Bei ÖGK eingereicht" },
  { statusKey: "OEGK_REFUNDED",      label: "Von ÖGK erstattet" },
  { statusKey: "READY_FOR_MERKUR",   label: "Bereit für Merkur" },
  { statusKey: "MERKUR_SUBMITTED",   label: "Bei Merkur eingereicht" },
  { statusKey: "MERKUR_REIMBURSED",  label: "Merkur Entscheidung" },
  { statusKey: "COMPLETED",          label: "Abgeschlossen" },
];

const PHARMACY_STEPS: PipelineStep[] = [
  { statusKey: "RECEIVED",           label: "Empfangen" },
  { statusKey: "OCR_PROCESSING",     label: "OCR-Verarbeitung" },
  { statusKey: "READY_FOR_MERKUR",   label: "Bereit für Merkur" },
  { statusKey: "MERKUR_SUBMITTED",   label: "Bei Merkur eingereicht" },
  { statusKey: "MERKUR_REIMBURSED",  label: "Merkur Entscheidung" },
  { statusKey: "COMPLETED",          label: "Abgeschlossen" },
];

export function getPipelineSteps(variant: PipelineVariant): PipelineStep[] {
  return variant === "pharmacy" ? PHARMACY_STEPS : STANDARD_STEPS;
}

export function getCurrentStepIndex(statusKey: string, variant: PipelineVariant): number {
  const steps = getPipelineSteps(variant);
  // MERKUR_REJECTED maps to the same step as MERKUR_REIMBURSED ("Merkur Entscheidung")
  const resolvedKey = statusKey === "MERKUR_REJECTED" ? "MERKUR_REIMBURSED" : statusKey;
  const idx = steps.findIndex((s) => s.statusKey === resolvedKey);
  return idx >= 0 ? idx : 0;
}

export function isCompleted(stepIdx: number, currentIdx: number): boolean {
  return stepIdx < currentIdx;
}

export function isActive(stepIdx: number, currentIdx: number): boolean {
  return stepIdx === currentIdx;
}
