import { useEffect, useState } from "react";
import { listContracts, getBenefits, Contract, BenefitRule } from "../api";

export default function BenefitDashboard() {
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [benefits, setBenefits] = useState<Record<string, BenefitRule[]>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const cs = await listContracts();
        setContracts(cs);
        const entries = await Promise.all(
          cs.map(async (c) => [c.id, await getBenefits(c.id)] as const)
        );
        setBenefits(Object.fromEntries(entries));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      }
    }
    load();
  }, []);

  if (error) return <p className="mt-6 text-red-600">{error}</p>;

  return (
    <div className="mt-6 space-y-6">
      <h1 className="text-xl font-bold">Benefits</h1>
      {contracts.length === 0 && (
        <p className="text-gray-500 text-sm">No contracts yet.</p>
      )}
      {contracts.map((contract) => (
        <div key={contract.id} className="bg-white rounded-xl shadow-sm p-4">
          <h2 className="font-semibold text-gray-900 mb-1">{contract.provider_name}</h2>
          {contract.policy_number && (
            <p className="text-xs text-gray-400 mb-3">Policy: {contract.policy_number}</p>
          )}
          <ul className="space-y-3">
            {(benefits[contract.id] ?? []).map((rule) => {
              const pct = Math.min(100, (rule.amount_used / rule.limit_amount) * 100);
              return (
                <li key={rule.id}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700">{rule.benefit_name}</span>
                    <span className="text-gray-500">
                      €{rule.amount_remaining.toFixed(2)} left / €{rule.limit_amount.toFixed(2)}
                    </span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${pct >= 100 ? "bg-red-400" : pct >= 75 ? "bg-orange-400" : "bg-green-400"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-400 mt-1">{rule.limit_type}</p>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}
