const EUR_FMT = new Intl.NumberFormat("de-AT", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatEUR(amount: number): string {
  return `€ ${EUR_FMT.format(amount)}`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}

export function relativeTime(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffMs = now - then;
  const diffDays = Math.floor(diffMs / 86_400_000);
  if (diffDays === 0) return "heute";
  if (diffDays === 1) return "gestern";
  if (diffDays < 7) return `vor ${diffDays} Tagen`;
  const diffWeeks = Math.floor(diffDays / 7);
  if (diffWeeks < 5) return `vor ${diffWeeks} Woche${diffWeeks > 1 ? "n" : ""}`;
  const diffMonths = Math.floor(diffDays / 30);
  if (diffMonths < 12) return `vor ${diffMonths} Monat${diffMonths > 1 ? "en" : ""}`;
  return `vor ${Math.floor(diffMonths / 12)} Jahr${Math.floor(diffMonths / 12) > 1 ? "en" : ""}`;
}
