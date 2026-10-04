import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { clearToken, getToken, UNAUTHORIZED_EVENT, type FamilyMember } from "../api";

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
  const [loggedIn, setLoggedIn] = useState(() => getToken() !== null);

  // Any 401 from the API (revoked/rotated token) drops back to the login screen.
  useEffect(() => {
    const onUnauthorized = () => setLoggedIn(false);
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

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
