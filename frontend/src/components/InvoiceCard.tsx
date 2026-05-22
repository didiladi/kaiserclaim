import { Avatar } from "./Avatar";
import { StatusPill } from "./StatusPill";
import { formatEUR, relativeTime } from "../lib/format";
import type { Invoice } from "../api";
import type { FamilyMember } from "../api";

interface Props {
  invoice: Invoice;
  members: FamilyMember[];
  onClick?: () => void;
}

export function InvoiceCard({ invoice, members, onClick }: Props) {
  const member = members.find((m) => m.id === invoice.family_member_id);

  return (
    <div
      onClick={onClick}
      className="flex items-center gap-3 px-4 py-3.5 cursor-pointer hover:-translate-y-px hover:shadow-md transition-all"
    >
      <Avatar
        initials={member?.initials ?? "?"}
        color={member?.color ?? "#9CA3AF"}
        size={38}
      />
      <div className="flex-1 min-w-0">
        <p className="text-[14px] font-semibold text-kc-text truncate">
          {invoice.provider_name ?? "Unbekannter Anbieter"}
        </p>
        <p className="text-[11px] text-kc-textTri mt-0.5">
          {member ? member.name.split(" ")[0] : "—"} · {invoice.date
            ? new Date(invoice.date).toLocaleDateString("de-AT")
            : "—"}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <StatusPill status={invoice.status} size="sm" />
          <span className="text-[11px] text-kc-textTri">
            {relativeTime(invoice.created_at)}
          </span>
        </div>
      </div>
      <span className="text-[15px] font-bold text-kc-text tabular-nums flex-shrink-0">
        {invoice.amount != null ? formatEUR(invoice.amount) : "—"}
      </span>
    </div>
  );
}
