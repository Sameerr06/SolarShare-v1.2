import React, { useEffect, useState } from 'react';
import { Share2, Sun, Battery, Award } from 'lucide-react';
import { api } from '../api/client';
import { AllocationCurrentResponse } from '../types/api';
import { StatCard } from '../components/ui/StatCard';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import { DemoBadge, DemoBanner } from '../components/ui/DemoBadge';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

export const AllocationPage: React.FC = () => {
  const [allocation, setAllocation] = useState<AllocationCurrentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getCurrentAllocation();
      setAllocation(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch allocation payload');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) return <LoadingState message="Querying Energy Allocation Solver..." />;
  if (error || !allocation) return <ErrorState message={error || 'No allocation data.'} onRetry={fetchData} />;

  const chartData = allocation.allocations.map((a) => ({
    name: a.tenant_name.length > 15 ? `${a.tenant_name.substring(0, 15)}...` : a.tenant_name,
    solar: a.allocated_solar_kw,
    battery: a.battery_power_kw,
    grid: a.grid_power_kw,
    demanded: a.demanded_kw,
  }));

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Fair Solar Energy Allocation
            </h1>
            <DemoBadge label="SIMULATED" size="sm" note={allocation.explanatory_note} />
          </div>
          <p className="text-slate-500 text-xs mt-0.5">
            Proportional fair share optimization dividing shared 500 kW solar PV generation across MSME tenants.
          </p>
        </div>

        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-white border border-slate-200 rounded text-slate-700 text-xs font-mono">
          Solver: {allocation.optimization_status}
        </div>
      </div>

      <DemoBanner note={allocation.explanatory_note} />

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <StatCard
          title="Available Solar Power"
          value={allocation.total_solar_available_kw.toFixed(1)}
          unit="kW"
          subtext="500 kW System Output"
          icon={Sun}
          iconColor="text-amber-700"
          isDemo={true}
        />
        <StatCard
          title="Total Estate Demand"
          value={allocation.total_estate_demand_kw.toFixed(1)}
          unit="kW"
          subtext="Sum of Active MSME Tenants"
          icon={Share2}
          iconColor="text-cyan-700"
          isDemo={true}
        />
        <StatCard
          title="Unallocated Solar Power"
          value={allocation.unallocated_solar_kw.toFixed(1)}
          unit="kW"
          subtext="Excess to Battery BESS"
          icon={Battery}
          iconColor="text-emerald-700"
          isDemo={true}
        />
        <StatCard
          title="Optimization Strategy"
          value="PROPORTIONAL"
          subtext="Fair Share Weighting"
          icon={Award}
          iconColor="text-violet-600"
          isDemo={true}
        />
      </div>

      {/* Stacked Bar Chart */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <Share2 className="w-4 h-4 text-amber-700" />
            Power Sources Breakdown per MSME Tenant (kW)
          </h3>
          <DemoBadge note="Illustrative allocation breakdown" />
        </div>

        <div className="h-64 w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.8} />
              <XAxis dataKey="name" stroke="#64748b" fontSize={10} />
              <YAxis stroke="#64748b" fontSize={10} unit=" kW" />
              <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', borderRadius: '0.375rem', fontSize: '11px' }} />
              <Legend wrapperStyle={{ fontSize: '11px' }} />
              <Bar dataKey="solar" name="Allocated Solar (kW)" stackId="a" fill="#f59e0b" />
              <Bar dataKey="battery" name="Battery Power (kW)" stackId="a" fill="#10b981" />
              <Bar dataKey="grid" name="Grid Power (kW)" stackId="a" fill="#06b6d4" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Allocation Table */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden space-y-0">
        <div className="p-3 border-b border-slate-200 flex items-center justify-between">
          <h3 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
            Tenant Proportional Allocation Summary
          </h3>
          <span className="text-[11px] text-slate-500 font-mono">PuLP Model Target Schema</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs table-interactive">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase tracking-wider font-semibold text-[10px]">
                <th className="py-2.5 px-3">Tenant Name</th>
                <th className="py-2.5 px-3 text-right">Demanded (kW)</th>
                <th className="py-2.5 px-3 text-right text-amber-700">Allocated Solar (kW)</th>
                <th className="py-2.5 px-3 text-right text-emerald-700">Battery (kW)</th>
                <th className="py-2.5 px-3 text-right text-cyan-700">Grid (kW)</th>
                <th className="py-2.5 px-3 text-right">Fairness Share</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/60 font-mono text-slate-700">
              {allocation.allocations.map((item) => (
                <tr key={item.tenant_id} className="hover:bg-slate-100/40 transition-colors">
                  <td className="py-2.5 px-3 font-sans font-medium text-slate-900">{item.tenant_name}</td>
                  <td className="py-2.5 px-3 text-right font-semibold">{item.demanded_kw.toFixed(1)}</td>
                  <td className="py-2.5 px-3 text-right font-semibold text-amber-700">{item.allocated_solar_kw.toFixed(1)}</td>
                  <td className="py-2.5 px-3 text-right text-emerald-700">{item.battery_power_kw.toFixed(1)}</td>
                  <td className="py-2.5 px-3 text-right text-cyan-700">{item.grid_power_kw.toFixed(1)}</td>
                  <td className="py-2.5 px-3 text-right font-semibold text-slate-800">{item.fairness_share_pct.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
