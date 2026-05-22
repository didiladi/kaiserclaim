import { createContext, useContext, useState, ReactNode } from "react";
import type { FamilyMember } from "../api";

export type ActiveMember = "all" | string; // "all" or a member_key

interface AppState {
  activeMember: ActiveMember;
  setActiveMember: (key: ActiveMember) => void;
  familyMembers: FamilyMember[];
  setFamilyMembers: (members: FamilyMember[]) => void;
  loggedIn: boolean;
  setLoggedIn: (v: boolean) => void;
}

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [activeMember, setActiveMember] = useState<ActiveMember>("all");
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>([]);
  const [loggedIn, setLoggedIn] = useState(true); // default true; login screen sets this

  return (
    <AppContext.Provider value={{ activeMember, setActiveMember, familyMembers, setFamilyMembers, loggedIn, setLoggedIn }}>
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppContext must be inside AppProvider");
  return ctx;
}
