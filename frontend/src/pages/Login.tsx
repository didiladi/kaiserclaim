import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Shield, KeyRound, Lock } from "lucide-react";
import { setToken, verifyToken } from "../api";
import { useAppContext } from "../state/AppContext";
import { Input } from "../components/Input";
import { Button } from "../components/Button";

export function Login() {
  const [token, setTokenValue] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setLoggedIn } = useAppContext();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const value = token.trim();
    if (!value) {
      setError("Bitte Zugangs-Token eingeben");
      return;
    }
    setError("");
    setLoading(true);
    try {
      if (await verifyToken(value)) {
        setToken(value);
        setLoggedIn(true);
        navigate("/");
      } else {
        setError("Token ungültig");
      }
    } catch {
      setError("Server nicht erreichbar");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-kc-bg flex flex-col items-center justify-center px-6 py-10">
      <div className="w-full max-w-[390px] flex flex-col items-center gap-8">
        {/* Logo */}
        <div className="flex flex-col items-center gap-4">
          <div
            className="w-16 h-16 rounded-xl flex items-center justify-center"
            style={{
              background: "#0D9488",
              boxShadow: "0 8px 24px #0D948833",
            }}
          >
            <Shield size={32} className="text-white" />
          </div>
          <div className="text-center">
            <h1 className="text-[28px] font-bold text-kc-brand" style={{ letterSpacing: "-0.02em" }}>
              KaiserClaim
            </h1>
            <p className="text-[15px] text-kc-textSec mt-1 leading-relaxed">
              Ihre Gesundheitskosten.<br />Automatisch erstattet.
            </p>
          </div>
        </div>

        {/* Card */}
        <div className="w-full bg-white rounded-lg border border-kc-border p-6 shadow-card">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <Input
              label="Zugangs-Token"
              type="password"
              placeholder="Token einfügen"
              leftIcon={<KeyRound size={18} />}
              value={token}
              onChange={(e) => setTokenValue(e.target.value)}
              error={error}
              autoComplete="current-password"
            />
            <Button type="submit" fullWidth size="lg" loading={loading}>
              {loading ? null : "Anmelden"}
            </Button>
          </form>
        </div>

        {/* Trust line */}
        <p className="flex items-center gap-1.5 text-[12px] text-kc-textTri">
          <Lock size={12} />
          Ende-zu-Ende verschlüsselt · DSGVO-konform
        </p>
      </div>
    </div>
  );
}
