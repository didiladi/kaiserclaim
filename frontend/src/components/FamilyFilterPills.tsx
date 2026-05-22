import clsx from "clsx";
import { Avatar } from "./Avatar";
import { useAppContext } from "../state/AppContext";

export function FamilyFilterPills() {
  const { activeMember, setActiveMember, familyMembers } = useAppContext();

  return (
    <div className="flex gap-2 px-5 py-4 overflow-x-auto no-scrollbar">
      <button
        onClick={() => setActiveMember("all")}
        className={clsx(
          "flex-shrink-0 px-3 py-1.5 rounded-full text-[13px] font-semibold transition-colors",
          activeMember === "all"
            ? "bg-kc-accent text-white"
            : "bg-kc-surfaceAlt text-kc-textSec"
        )}
      >
        Alle
      </button>
      {familyMembers.map((m) => (
        <button
          key={m.member_key}
          onClick={() => setActiveMember(m.member_key)}
          className={clsx(
            "flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] font-semibold transition-colors",
            activeMember === m.member_key
              ? "text-white"
              : "bg-kc-surfaceAlt text-kc-textSec"
          )}
          style={activeMember === m.member_key ? { backgroundColor: m.color } : {}}
        >
          <Avatar initials={m.initials} color={activeMember === m.member_key ? "#fff" : m.color} size={20} />
          {m.name.split(" ")[0]}
        </button>
      ))}
    </div>
  );
}
