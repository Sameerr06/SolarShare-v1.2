import React, { useEffect, useState } from 'react';
import { Receipt, IndianRupee, Clock, TrendingDown, ShieldCheck } from 'lucide-react';
import { api } from '../api/client';
import { TariffRead, BillingSummaryResponse } from '../types/api';
import { StatCard } from '../components/ui/StatCard';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import { DemoBadge, DemoBanner } from '../components/ui/DemoBadge';

export const BillingPage: React.FC = () => {
  const [tariff, setTariff] = useState<TariffRead | null>(null);
  const [billing, setBilling] = useState<BillingSummaryResponse | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<string>('2026-08');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [tRes, bRes] = await Promise.all([
        api.getTariffs(),
        api.getBillingSummary(selectedMonth),
      ]);
      setTariff(tRes);
      setBilling(bRes);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch billing payload');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [selectedMonth]);

  if (loading) return <LoadingState message="Calculating Tariffs & Billing Summary..." />;
  if (error || !tariff || !billing) return <ErrorState message={error || 'No billing data.'} onRetry={fetchData} />;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-white tracking-tight">
              ToU Billing & Financial Savings
            </h1>
            <DemoBadge label="SIMULATED" size="sm" note={billing.explanatory_note} />
          </div>
          <p className="text-slate-400 text-xs mt-0.5">
            Tamil Nadu HT Industrial Tariff (TNERC FY 2025-26) with Time-of-Use peak rates & solar savings.
          </p>
        </div>

        {/* Month Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 font-medium">Billing Period:</span>
          <select
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-amber-500 font-mono"
          >
            <option value="2026-08">August 2026</option>
            <option value="2026-07">July 2026</option>
            <option value="2026-06">June 2026</option>
          </select>
        </div>
      </div>

      <DemoBanner note={billing.explanatory_note} />

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <StatCard
          title="Total Estate Savings"
          value={`₹${(billing.total_savings_inr / 1000).toFixed(0)}k`}
          unit="INR / mo"
          subtext="Solar vs Grid Displacement"
          icon={IndianRupee}
          iconColor="text-emerald-400"
          trend={{ value: 'SAVE 35%', isPositive: true }}
          isDemo={true}
        />
        <StatCard
          title="Solar Consumed"
          value={billing.total_solar_consumed_kwh.toLocaleString()}
          unit="kWh"
          subtext="Solar Rate: ₹5.00/kWh"
          icon={Receipt}
          iconColor="text-amber-400"
          isDemo={true}
        />
        <StatCard
          title="Grid Consumed"
          value={billing.total_grid_consumed_kwh.toLocaleString()}
          unit="kWh"
          subtext="Avg ToU Rate: ₹8.50/kWh"
          icon={Clock}
          iconColor="text-cyan-400"
          isDemo={true}
        />
        <StatCard
          title="Total Estate Bill"
          value={`₹${(billing.tenants.reduce((a, b) => a + b.total_bill_inr, 0) / 1000).toFixed(0)}k`}
          unit="INR"
          subtext={`5 Tenants | Period ${billing.billing_period}`}
          icon={TrendingDown}
          iconColor="text-violet-400"
          isDemo={true}
        />
      </div>

      {/* Tamil Nadu ToU Tariff Structure Cards */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-white">
              {tariff.name} Structure
            </h3>
          </div>
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono text-[10px]">
            TNERC SPEC
          </span>
        </div>

        <p className="text-xs text-slate-400">
          Source: {tariff.source} ({tariff.source_reference}). Base Charge: ₹7.50 / kWh + 5% Tax.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
          {tariff.periods.map((period) => (
            <div
              key={period.id}
              className="p-2.5 bg-slate-950 border border-slate-800 rounded space-y-1.5 font-mono text-xs"
            >
              <div className="flex items-center justify-between">
                <span className="font-sans font-semibold text-amber-400 text-xs">{period.period_name}</span>
                <span className="text-[10px] text-slate-400">{period.start_time} - {period.end_time}</span>
              </div>
              <div className="flex items-baseline justify-between pt-0.5">
                <span className="text-slate-400 font-sans text-[11px]">Effective Rate:</span>
                <span className="text-xs font-semibold text-white">₹{period.effective_rate_inr_per_kwh.toFixed(3)}/kWh</span>
              </div>
              <div className="text-[10px] text-slate-400 font-sans border-t border-slate-800 pt-1 flex justify-between">
                <span>Base: ₹{period.base_energy_charge_inr_per_kwh.toFixed(2)}</span>
                <span>Tax: {period.electricity_tax_pct}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Tenant Monthly Billing Summary Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden space-y-0">
        <div className="p-3 border-b border-slate-800 flex items-center justify-between">
          <h3 className="text-xs font-semibold text-white uppercase tracking-wider">
            Tenant Billing Breakdown ({billing.billing_period})
          </h3>
          <span className="text-[11px] text-slate-400 font-mono">Billing Calculator Schema</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs table-interactive">
            <thead>
              <tr className="bg-slate-950 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold text-[10px]">
                <th className="py-2.5 px-3">Tenant Name</th>
                <th className="py-2.5 px-3 text-right">Consumption (kWh)</th>
                <th className="py-2.5 px-3 text-right text-amber-400">Solar Consumed</th>
                <th className="py-2.5 px-3 text-right text-cyan-400">Grid Consumed</th>
                <th className="py-2.5 px-3 text-right">Solar Cost (₹)</th>
                <th className="py-2.5 px-3 text-right">Grid Cost (₹)</th>
                <th className="py-2.5 px-3 text-right font-semibold">Total Bill (₹)</th>
                <th className="py-2.5 px-3 text-right text-emerald-400 font-semibold">Savings (₹)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
              {billing.tenants.map((t) => (
                <tr key={t.tenant_id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="py-2.5 px-3 font-sans font-medium text-white">{t.tenant_name}</td>
                  <td className="py-2.5 px-3 text-right font-semibold">{t.total_consumption_kwh.toLocaleString()}</td>
                  <td className="py-2.5 px-3 text-right text-amber-400">{t.solar_consumed_kwh.toLocaleString()}</td>
                  <td className="py-2.5 px-3 text-right text-cyan-400">{t.grid_consumed_kwh.toLocaleString()}</td>
                  <td className="py-2.5 px-3 text-right">₹{t.solar_cost_inr.toLocaleString()}</td>
                  <td className="py-2.5 px-3 text-right">₹{t.grid_cost_inr.toLocaleString()}</td>
                  <td className="py-2.5 px-3 text-right font-semibold text-white">₹{t.total_bill_inr.toLocaleString()}</td>
                  <td className="py-2.5 px-3 text-right font-semibold text-emerald-400">₹{t.savings_inr.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
