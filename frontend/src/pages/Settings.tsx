import { useNavigate } from "react-router-dom";
import { User, Mail, Globe, Shield, LogOut, ChevronRight, Plus } from "lucide-react";
import { useAppContext } from "../state/AppContext";
import { KCCard } from "../components/KCCard";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="px-1 mb-2 text-[12px] font-bold uppercase tracking-widest text-kc-textSec">{title}</p>
      <KCCard className="divide-y divide-kc-borderLight">{children}</KCCard>
    </div>
  );
}

function SettingsRow({ icon: Icon, label, value, onClick }: {
  icon: React.ElementType; label: string; value?: string; onClick?: () => void;
}) {
  return (
    <button onClick={onClick} className="flex items-center gap-3 px-4 py-3.5 w-full text-left hover:bg-kc-surfaceAlt/50 transition-colors">
      <div className="w-8 h-8 rounded-lg bg-kc-surfaceAlt flex items-center justify-center flex-shrink-0">
        <Icon size={17} className="text-kc-textSec" />
      </div>
      <div className="flex-1">
        <p className="text-[14px] font-medium text-kc-text">{label}</p>
        {value && <p className="text-[12px] text-kc-textSec">{value}</p>}
      </div>
      <ChevronRight size={16} className="text-kc-textTri" />
    </button>
  );
}

function PortalRow({ label, status }: { label: string; status: "hinterlegt" | "nicht hinterlegt" }) {
  const ok = status === "hinterlegt";
  return (
    <div className="flex items-center gap-3 px-4 py-3.5">
      <div className="w-8 h-8 rounded-lg bg-kc-surfaceAlt flex items-center justify-center flex-shrink-0">
        <Shield size={17} className="text-kc-textSec" />
      </div>
      <div className="flex-1">
        <p className="text-[14px] font-medium text-kc-text">{label}</p>
        <div className="flex items-center gap-1.5 mt-0.5">
          <div className={`w-2 h-2 rounded-full ${ok ? "bg-green-500" : "bg-kc-textTri"}`} />
          <p className="text-[12px] text-kc-textSec">{status}</p>
        </div>
      </div>
    </div>
  );
}

export function Settings() {
  const navigate = useNavigate();
  const { setLoggedIn } = useAppContext();

  return (
    <div className="px-5 py-6 flex flex-col gap-6">
      <h1 className="text-[22px] font-bold text-kc-text">Einstellungen</h1>

      <Section title="Konto">
        <SettingsRow icon={User} label="Profil" value="Dieter" />
        <SettingsRow icon={Mail} label="E-Mail" value="didi.barfoo@gmail.com" />
        <SettingsRow icon={Globe} label="Sprache" value="Deutsch (Österreich)" />
      </Section>

      <Section title="Versicherungsportal">
        {/* Vault banner */}
        <div className="flex items-start gap-3 px-4 py-3.5 bg-green-50 rounded-t-lg">
          <div className="w-8 h-8 rounded-lg bg-green-100 flex items-center justify-center flex-shrink-0">
            <Shield size={17} className="text-green-600" />
          </div>
          <div>
            <p className="text-[13px] font-semibold text-green-800">Sicherer Tresor</p>
            <p className="text-[12px] text-green-700">AES-256 verschlüsselt · Nur auf Ihrem Gerät</p>
          </div>
        </div>
        <PortalRow label="ÖGK-Portal" status="hinterlegt" />
        <PortalRow label="Merkur-Portal" status="hinterlegt" />
      </Section>

      <Section title="Verträge">
        <SettingsRow icon={Shield} label="Merkur Sonderklasse" value="MS-2024-78912" />
        <button
          onClick={() => navigate("/onboarding")}
          className="flex items-center gap-3 px-4 py-3.5 w-full text-left text-kc-accent"
        >
          <div className="w-8 h-8 rounded-lg bg-kc-accentLight flex items-center justify-center flex-shrink-0">
            <Plus size={17} className="text-kc-accent" />
          </div>
          <p className="text-[14px] font-medium">Vertrag hinzufügen</p>
        </button>
      </Section>

      <Section title="Sonstiges">
        <button
          onClick={() => { setLoggedIn(false); navigate("/login"); }}
          className="flex items-center gap-3 px-4 py-3.5 w-full text-left"
        >
          <div className="w-8 h-8 rounded-lg bg-kc-dangerBg flex items-center justify-center flex-shrink-0">
            <LogOut size={17} className="text-kc-danger" />
          </div>
          <p className="text-[14px] font-medium text-kc-danger">Abmelden</p>
        </button>
      </Section>
    </div>
  );
}
