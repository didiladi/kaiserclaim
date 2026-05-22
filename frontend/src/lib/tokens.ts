export const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  RECEIVED:        { label: "Empfangen",              color: "#6B7280", bg: "#F3F4F6" },
  OCR_PROCESSING:  { label: "OCR-Verarbeitung",       color: "#A16207", bg: "#FEF9C3" },
  READY_FOR_OEGK:  { label: "Bereit für ÖGK",        color: "#2563EB", bg: "#DBEAFE" },
  OEGK_SUBMITTED:  { label: "Bei ÖGK eingereicht",   color: "#1D4ED8", bg: "#DBEAFE" },
  OEGK_REFUNDED:   { label: "Von ÖGK erstattet",     color: "#4338CA", bg: "#E0E7FF" },
  READY_FOR_MERKUR:{ label: "Bereit für Merkur",     color: "#C2410C", bg: "#FFEDD5" },
  MERKUR_SUBMITTED:{ label: "Bei Merkur eingereicht",color: "#6D28D9", bg: "#EDE9FE" },
  COMPLETED:       { label: "Abgeschlossen",          color: "#15803D", bg: "#DCFCE7" },
};

export const MEMBER_COLORS: Record<string, string> = {
  maria:  "#E84393",
  thomas: "#3B82F6",
  luisa:  "#F59E0B",
  felix:  "#10B981",
};

export const BENEFIT_CATEGORIES = [
  "Zahnreinigung",
  "Physiotherapie",
  "Allgemeinmedizin",
  "Medikamente",
  "Sehbehelfe",
  "Kinderarzt",
];
