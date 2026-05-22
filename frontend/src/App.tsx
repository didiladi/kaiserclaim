import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppProvider, useAppContext } from "./state/AppContext";
import { AppShell } from "./components/AppShell";
import { Login } from "./pages/Login";
import { Home } from "./pages/Home";
import { Upload } from "./pages/Upload";
import { InvoiceList } from "./pages/InvoiceList";
import { InvoiceDetail } from "./pages/InvoiceDetail";
import { Benefits } from "./pages/Benefits";
import { Stats } from "./pages/Stats";
import { Onboarding } from "./pages/Onboarding";
import { Settings } from "./pages/Settings";
import { listFamilyMembers } from "./api";

function AppRoutes() {
  const { loggedIn, setFamilyMembers } = useAppContext();

  useEffect(() => {
    if (loggedIn) {
      listFamilyMembers().then(setFamilyMembers).catch(() => {});
    }
  }, [loggedIn]);

  if (!loggedIn) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Home />} />
        <Route path="/invoices" element={<InvoiceList />} />
        <Route path="/invoices/:id" element={<InvoiceDetail />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/benefits" element={<Benefits />} />
        <Route path="/stats" element={<Stats />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        {/* On >430px screens, letterbox the app on a warm grey background */}
        <div className="min-h-screen flex items-center justify-center bg-[#E8E7E4]">
          <div
            className="w-full relative flex flex-col bg-kc-bg overflow-hidden"
            style={{ maxWidth: 430, height: "100svh" }}
          >
            <AppRoutes />
          </div>
        </div>
      </AppProvider>
    </BrowserRouter>
  );
}
