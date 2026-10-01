import React, { useEffect, useState } from 'react';
import {
  Database,
  Sun,
  Receipt,
  Layers,
  Activity,
  ArrowRight,
} from 'lucide-react';
import { api } from '../api/client';
import { DashboardOverviewResponse } from '../types/api';
import { StatCard } from '../components/ui/StatCard';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import { DemoBadge, DemoBanner } from '../components/ui/DemoBadge';
import { Link } from 'react-router-dom';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export const OverviewPage: React.FC = () => {
  const [data, setData] = useState<DashboardOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getDashboardOverview();
      setData(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch dashboard overview');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) return <LoadingState message="Loading Overview Dashboard..." />;
  if (error || !data) return <ErrorState message={error || 'No overview data received.'} onRetry={fetchData} />;

  const { dataset_metrics, solar_metrics, battery_metrics, allocation_metrics, billing_metrics, selected_profiles_summary } = data;

  const solarGenTrend = [
    { hour: '00:00', solar: 0, demand: 150 },
    { hour: '04:00', solar: 0, demand: 120 },
    { hour: '08:00', solar: 140, demand: 380 },
    { hour: '12:00', solar: 480, demand: 450 },
    { hour: '16:00', solar: 320, demand: 420 },
    { hour: '20:00', solar: 10, demand: 280 },
    { hour: '23:00', solar: 0, demand: 180 },
  ];

  return (
    <div className="space-y-5">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              Executive Overview
            </h1>
            <span
              className="px-2 py-0.5 rounded text-[11px] font-semibold"
              style={{ background: 'rgba(52,211,153,0.1)', border: '1px solid rgba(52,211,153,0.2)', color: '#059669' }}
            >
              SYSTEM ONLINE
            </span>
          </div>
          <p className="text-slate-500 text-xs mt-0.5">
            Dataset telemetry (8.44M observations, 321 series) and operational estate balance.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/load-profiles"
            className="pressable px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 hover:brightness-110"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: 'white', boxShadow: '0 4px 12px rgba(99,102,241,0.35)' }}
          >
            Explore Profiles <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {/* Explanatory Banner */}
      <DemoBanner note={data.explanatory_note} />

      {/* Top Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 stagger-children">
        <StatCard
          title="Zenodo Observations"
          value={dataset_metrics.total_observations}
          unit="obs"
          subtext="321 Public Load Series"
          icon={Database}
          iconColor="text-emerald-700"
        />
        <StatCard
          title="Computed Profiles"
          value={dataset_metrics.total_profiles_computed}
          unit="profiles"
          subtext="6 Cluster Centroid Profiles"
          icon={Layers}
          iconColor="text-cyan-700"
        />
        <StatCard
          title="Installed PV Capacity"
          value={solar_metrics.installed_capacity_kw}
          unit="kW"
          subtext={`Current Output: ${solar_metrics.current_generation_kw} kW`}
          icon={Sun}
          iconColor="text-amber-700"
          isDemo={true}
        />
        <StatCard
          title="Est. Monthly Savings"
          value={`₹${(billing_metrics.estimated_monthly_savings_inr / 1000).toFixed(0)}k`}
          unit="/ mo"
          subtext="Tamil Nadu ToU Tariff"
          icon={Receipt}
          iconColor="text-violet-600"
          isDemo={true}
        />
      </div>

      {/* Real 6 Selected Profiles Summary & Generation Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left Column: Real 6 Selected Profiles List */}
        <div className="glass-panel glass-panel-hover p-4 flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-amber-700" />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Centroid Profile Archetypes</h3>
            </div>
            <span
              className="px-2 py-0.5 rounded font-mono text-[10px] font-semibold"
              style={{ background: 'rgba(99,102,241,0.12)', color: '#6366f1', border: '1px solid rgba(99,102,241,0.2)' }}
            >
              k=6 WARD
            </span>
          </div>
          <p className="text-[11px] text-slate-500">
            Selected cluster centroids representing 321 public load series.
          </p>

          <div className="space-y-2">
            {selected_profiles_summary.map((prof) => (
              <div
                key={prof.series_name}
                className="pressable p-2.5 rounded-xl flex items-center justify-between hover:bg-slate-100"
                style={{ background: 'rgba(15,23,42,0.03)', border: '1px solid rgba(15,23,42,0.06)' }}
              >
                <div className="flex items-center gap-2.5">
                  <span
                    className="w-6 h-6 rounded-lg font-mono text-[11px] font-bold flex items-center justify-center"
                    style={{ background: 'rgba(99,102,241,0.15)', color: '#6366f1' }}
                  >
                    C{prof.cluster_id}
                  </span>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-semibold text-xs text-slate-900">
                        {prof.series_name}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-500">
                      Mean: <strong className="text-slate-800 font-mono">{prof.mean_demand_kw} kW</strong>
                    </span>
                  </div>
                </div>

                <div className="text-right text-xs font-mono">
                  <div className="text-slate-700 text-[11px]">CV: {(prof.cv ?? prof.coefficient_of_variation).toFixed(2)}</div>
                  <div className="text-slate-500 text-[10px]">PAR: {(prof.par ?? prof.peak_to_average_ratio).toFixed(2)}</div>
                </div>
              </div>
            ))}
          </div>

          <Link
            to="/load-profiles"
            className="w-full py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-medium rounded text-center transition-colors block"
          >
            View Full 319 Profiles Table →
          </Link>
        </div>

        {/* Right Column: Generation vs Demand Curve & Operational Grid */}
        <div className="lg:col-span-2 space-y-5">
          {/* Chart */}
          <div className="glass-panel glass-panel-hover p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                  <Sun className="w-4 h-4 text-amber-700" />
                  Estate Energy Balance (24h Telemetry)
                </h3>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Solar PV output vs total estate demand (500 kW System).
                </p>
              </div>
              <DemoBadge note="Prototype solar estimation" />
            </div>

            <div className="h-60 w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={solarGenTrend} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorSolar" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorDemand" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.8} />
                  <XAxis dataKey="hour" stroke="#64748b" fontSize={10} />
                  <YAxis stroke="#64748b" fontSize={10} unit=" kW" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', borderRadius: '0.375rem', fontSize: '11px' }}
                    itemStyle={{ color: '#0f172a' }}
                  />
                  <Area type="monotone" dataKey="solar" name="Solar Gen (kW)" stroke="#f59e0b" strokeWidth={2} fillOpacity={1} fill="url(#colorSolar)" animationDuration={800} animationEasing="ease-out" />
                  <Area type="monotone" dataKey="demand" name="Estate Demand (kW)" stroke="#06b6d4" strokeWidth={2} fillOpacity={1} fill="url(#colorDemand)" animationDuration={800} animationEasing="ease-out" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Operational Metrics Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
            <div className="glass-panel glass-panel-hover p-3.5 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold uppercase text-[10px] tracking-widest" style={{ color: 'var(--text-muted)' }}>Battery (BESS)</span>
                <DemoBadge size="sm" />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-lg font-semibold font-mono text-slate-900">{battery_metrics.current_soc_pct}%</span>
                <span className="text-xs text-emerald-700 font-medium">{battery_metrics.status}</span>
              </div>
              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{ width: `${battery_metrics.current_soc_pct}%`, background: 'linear-gradient(90deg, #34d399, #6ee7b7)' }}
                />
              </div>
              <p className="text-[10px] font-mono text-slate-500">
                {battery_metrics.stored_energy_kwh} / {battery_metrics.capacity_kwh} kWh
              </p>
            </div>

            <div className="glass-panel glass-panel-hover p-3.5 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold uppercase text-[10px] tracking-widest" style={{ color: 'var(--text-muted)' }}>Solar Coverage</span>
                <DemoBadge size="sm" />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-lg font-semibold font-mono text-amber-700">{allocation_metrics.solar_coverage_pct}%</span>
                <span className="text-xs text-slate-500">of load</span>
              </div>
              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{ width: `${allocation_metrics.solar_coverage_pct}%`, background: 'linear-gradient(90deg, #f59e0b, #fbbf24)' }}
                />
              </div>
              <p className="text-[10px] text-slate-500">
                Active Tenants: {allocation_metrics.active_tenants}
              </p>
            </div>

            <div className="glass-panel glass-panel-hover p-3.5 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold uppercase text-[10px] tracking-widest" style={{ color: 'var(--text-muted)' }}>Grid Dependency</span>
                <DemoBadge size="sm" />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-lg font-semibold font-mono text-cyan-700">{allocation_metrics.grid_dependency_pct}%</span>
                <span className="text-xs text-slate-500">supplemental</span>
              </div>
              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{ width: `${allocation_metrics.grid_dependency_pct}%`, background: 'linear-gradient(90deg, #6366f1, #818cf8)' }}
                />
              </div>
              <p className="text-[10px] text-slate-500">
                BESS Share: {allocation_metrics.battery_contribution_pct}%
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
