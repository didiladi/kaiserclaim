import { Outlet, useLocation } from "react-router-dom";
import { TopBar } from "./TopBar";
import { BottomNav } from "./BottomNav";

const NO_BOTTOM_NAV = ["/upload", "/onboarding", "/login"];
const SHOW_BACK = ["/upload", "/onboarding"];
const SUB_TITLES: Record<string, string> = {
  "/upload": "Beleg hochladen",
  "/onboarding": "Neuer Vertrag",
  "/settings": "Einstellungen",
};

function isSubScreen(path: string) {
  return SHOW_BACK.includes(path) || path.startsWith("/invoices/");
}

function getSubTitle(path: string) {
  if (path.startsWith("/invoices/") && path !== "/invoices") return "Belegdetails";
  return SUB_TITLES[path];
}

export function AppShell() {
  const { pathname } = useLocation();

  if (pathname === "/login") {
    return <Outlet />;
  }

  const sub = isSubScreen(pathname);
  const showBottomNav = !NO_BOTTOM_NAV.includes(pathname) && !pathname.startsWith("/invoices/");

  return (
    <div className="flex flex-col h-full">
      <TopBar
        showBack={sub}
        title={getSubTitle(pathname)}
        showSettings={!sub && pathname === "/"}
      />
      <main className="flex-1 overflow-y-auto animate-kcFadeUp bg-kc-bg">
        <Outlet />
      </main>
      {showBottomNav && <BottomNav />}
    </div>
  );
}
