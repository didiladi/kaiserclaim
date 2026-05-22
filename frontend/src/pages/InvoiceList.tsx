import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Receipt } from "lucide-react";
import { listInvoices } from "../api";
import type { Invoice } from "../api";
import { useAppContext } from "../state/AppContext";
import { FamilyFilterPills } from "../components/FamilyFilterPills";
import { InvoiceCard } from "../components/InvoiceCard";
import { KCCard } from "../components/KCCard";
import clsx from "clsx";

type FilterGroup = "all" | "in_progress" | "completed";

const FILTER_LABELS: Record<FilterGroup, string> = {
  all: "Alle",
  in_progress: "Laufend",
  completed: "Fertig",
};

export function InvoiceList() {
  const { activeMember, familyMembers } = useAppContext();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [filter, setFilter] = useState<FilterGroup>("all");
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  const memberKey = activeMember === "all" ? undefined : activeMember;
  const activeMemberObj = familyMembers.find((m) => m.member_key === activeMember);

  useEffect(() => {
    listInvoices({ member_key: memberKey, status_group: filter === "all" ? undefined : filter, search: search || undefined })
      .then(setInvoices)
      .catch(() => {});
  }, [activeMember, filter, search]);

  return (
    <div className="pb-4">
      <FamilyFilterPills />

      <div className="px-5 mb-4">
        <h1 className="text-[22px] font-bold text-kc-text">
          Belege{activeMemberObj ? ` — ${activeMemberObj.name.split(" ")[0]}` : ""}
        </h1>
      </div>

      {/* Search */}
      <div className="px-5 mb-3">
        <div className="relative">
          <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-kc-textTri pointer-events-none" />
          <input
            className="w-full h-11 bg-kc-surfaceAlt rounded-md pl-10 pr-4 text-[14px] text-kc-text border border-transparent focus:outline-none focus:border-kc-accent placeholder:text-kc-textTri"
            placeholder="Belege durchsuchen..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Status filter tabs */}
      <div className="flex gap-2 px-5 mb-4">
        {(Object.keys(FILTER_LABELS) as FilterGroup[]).map((key) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={clsx(
              "px-3.5 py-1.5 rounded-full text-[13px] font-semibold transition-colors",
              filter === key ? "bg-kc-brand text-white" : "bg-kc-surfaceAlt text-kc-textSec"
            )}
          >
            {FILTER_LABELS[key]}
          </button>
        ))}
      </div>

      {/* List */}
      {invoices.length > 0 ? (
        <KCCard className="mx-5 divide-y divide-kc-borderLight">
          {invoices.map((inv) => (
            <InvoiceCard
              key={inv.id}
              invoice={inv}
              members={familyMembers}
              onClick={() => navigate(`/invoices/${inv.id}`)}
            />
          ))}
        </KCCard>
      ) : (
        <div className="flex flex-col items-center gap-3 py-16 text-center px-8">
          <Receipt size={40} className="text-kc-textTri" />
          <p className="text-[15px] font-semibold text-kc-text">Keine Belege gefunden</p>
          <p className="text-[13px] text-kc-textSec">
            {search ? "Keine Belege für diese Suche." : "Laden Sie Ihren ersten Beleg hoch."}
          </p>
        </div>
      )}
    </div>
  );
}
