import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Upload from "./pages/Upload";
import InvoiceList from "./pages/InvoiceList";
import InvoiceDetail from "./pages/InvoiceDetail";
import BenefitDashboard from "./pages/BenefitDashboard";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-6">
          <span className="font-bold text-lg text-blue-700">KaiserClaim</span>
          <nav className="flex gap-4 text-sm">
            <NavLink to="/" end className={({ isActive }) => isActive ? "font-semibold text-blue-700" : "text-gray-600 hover:text-gray-900"}>
              Upload
            </NavLink>
            <NavLink to="/invoices" className={({ isActive }) => isActive ? "font-semibold text-blue-700" : "text-gray-600 hover:text-gray-900"}>
              Invoices
            </NavLink>
            <NavLink to="/contracts" className={({ isActive }) => isActive ? "font-semibold text-blue-700" : "text-gray-600 hover:text-gray-900"}>
              Benefits
            </NavLink>
          </nav>
        </header>
        <main className="flex-1 p-4 max-w-2xl mx-auto w-full">
          <Routes>
            <Route path="/" element={<Upload />} />
            <Route path="/invoices" element={<InvoiceList />} />
            <Route path="/invoices/:id" element={<InvoiceDetail />} />
            <Route path="/contracts" element={<BenefitDashboard />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
