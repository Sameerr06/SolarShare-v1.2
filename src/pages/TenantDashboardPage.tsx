import React, { useEffect, useState } from 'react';
import { Users, Activity, TrendingUp, Layers, Shield } from 'lucide-react';
import { api } from '../api/client';
import { LoadProfileRead, TenantForecastResponse } from '../types/api';
import { StatCard } from '../components/ui/StatCard';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import { DemoBadge, DemoBanner } from '../components/ui/DemoBadge';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export const TenantDashboardPage: React.FC = () => {
  const [selectedProfiles, setSelectedProfiles] = useState<LoadProfileRead[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<number>(1);
  const [forecast, setForecast] = useState<TenantForecastResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const tenantNames = [
    'Textile Manufacturing Unit',
    'Food Processing Facility',
    'Electronics Assembly',
    'Packaging & Plastics Unit',
    'General Engineering Works',
    'Precision Tooling Workshop',
  ];

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const profilesRes = await api.getSelectedLoadProfiles();
      setSelectedProfiles(profilesRes);
      const forecastRes = await api.getTenantForecast(selectedTenantId, 24);
      setForecast(forecastRes);
    } catch (err: any) {
      setError(err?.message || 'Failed to load tenant telemetry');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [selectedTenantId]);

  if (loading && !forecast) return <LoadingState message="Fetching Tenant Telemetry..." />;
  if (error) return <ErrorState message={error} onRetry={fetchData} />;

  const currentProfile = selectedProfiles[selectedTenantId - 1] || selectedProfiles[0];
  const currentTenantName = tenantNames[selectedTenantId - 1] || `Tenant #${selectedTenantId}`;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              MSME Tenant Telemetry
            </h1>
            <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-300 text-slate-700 text-[11px] font-mono">
              6 TENANTS ACTIVE
            </span>
          </div>
          <p className="text-slate-500 text-xs mt-0.5">
            Individual tenant load shapes, profile cluster metrics, and Prophet demand projections.
          </p>
        </div>

        {/* Tenant Selector Switcher */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 max-w-full">
          {[1, 2, 3, 4, 5, 6].map((id) => (
            <button
              key={id}
              onClick={() => setSelectedTenantId(id)}
              className={`pressable px-2.5 py-1 rounded text-xs font-medium shrink-0 flex items-center gap-1.5 ${
                selectedTenantId === id
                  ? 'bg-amber-500 text-slate-950 font-semibold'
                  : 'bg-white border border-slate-200 text-slate-700 hover:border-amber-500/50'
              }`}
            >
              <Users className="w-3.5 h-3.5" />
              Tenant #{id}
            </button>
          ))}
        </div>
      </div>

      <DemoBanner note="Tenant load shape is matched with representative Zenodo series profiles." />

      {/* Tenant Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 stagger-children">
        <StatCard
          title="Tenant Name"
          value={currentTenantName}
          subtext={`Estate Slot #${selectedTenantId}`}
          icon={Users}
          iconColor="text-amber-700"
        />
        <StatCard
          title="Centroid Profile"
          value={currentProfile?.series_name || `Series #${selectedTenantId}`}
          subtext={`Cluster ID: ${currentProfile?.cluster_id ?? (selectedTenantId - 1)}`}
          icon={Layers}
          iconColor="text-emerald-700"
        />
        <StatCard
          title="Mean Load Demand"
          value={currentProfile?.mean_demand_kw ? currentProfile.mean_demand_kw.toFixed(1) : 120}
          unit="kW"
          subtext={`PAR: ${currentProfile?.peak_to_average_ratio.toFixed(2) ?? '1.45'}`}
          icon={Activity}
          iconColor="text-cyan-700"
        />
        <StatCard
          title="Forecast Consumption"
          value={forecast ? forecast.total_consumption_forecast_kwh.toFixed(0) : 2800}
          unit="kWh/day"
          subtext={`Peak: ${forecast?.peak_demand_kw.toFixed(1) ?? '180'} kW`}
          icon={TrendingUp}
          iconColor="text-violet-600"
          isDemo={forecast ? forecast.is_demo : true}
        />
      </div>

      {/* 24-Hour Load Forecast Chart & Statistics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Load Forecast Chart */}
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-amber-700" />
                24-Hour Load Forecast ({currentTenantName})
              </h3>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Predicted demand with upper and lower confidence intervals.
              </p>
            </div>
            {forecast?.is_demo ? (
              <DemoBadge note="Prophet model simulation" />
            ) : (
              <span className="px-2 py-0.5 text-[10px] font-mono bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 rounded shrink-0">
                Prophet Active
              </span>
            )}
          </div>

          <div className="h-64 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={forecast?.forecast_data || []} margin={{ top: 10, right: 10, left: 5, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorTenant" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.8} />
                <XAxis
                  dataKey="timestamp"
                  stroke="#64748b"
                  fontSize={10}
                  tickFormatter={(val) => val.split('T')[1]?.substring(0, 5) || val}
                />
                <YAxis stroke="#64748b" fontSize={10} unit=" kW" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', borderRadius: '0.375rem', fontSize: '11px' }}
                />
                <Area type="monotone" dataKey="upper_bound_kw" name="Upper Confidence (kW)" stroke="#64748b" strokeDasharray="3 3" fill="none" opacity={0.5} />
                <Area type="monotone" dataKey="predicted_value_kw" name="Predicted Load (kW)" stroke="#f59e0b" strokeWidth={2} fillOpacity={1} fill="url(#colorTenant)" />
                <Area type="monotone" dataKey="lower_bound_kw" name="Lower Confidence (kW)" stroke="#64748b" strokeDasharray="3 3" fill="none" opacity={0.5} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Historical Profiling Metrics */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <Shield className="w-4 h-4 text-emerald-700" />
              Profile Parameters
            </h3>
            <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-500 font-mono text-[10px]">
              DATASET
            </span>
          </div>

          {currentProfile ? (
            <div className="space-y-2.5 text-xs">
              <div className="p-2.5 bg-slate-50/80 rounded border border-slate-200 space-y-0.5">
                <span className="text-[11px] text-slate-500">Series ID</span>
                <p className="text-xs font-semibold text-amber-700 font-mono">{currentProfile.series_name}</p>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="p-2 bg-slate-50/80 rounded border border-slate-200">
                  <span className="text-slate-500 block text-[10px]">Min Demand</span>
                  <span className="font-semibold text-slate-800 font-mono">{currentProfile.min_demand_kw} kW</span>
                </div>
                <div className="p-2 bg-slate-50/80 rounded border border-slate-200">
                  <span className="text-slate-500 block text-[10px]">Max Demand</span>
                  <span className="font-semibold text-slate-800 font-mono">{currentProfile.max_demand_kw} kW</span>
                </div>
                <div className="p-2 bg-slate-50/80 rounded border border-slate-200">
                  <span className="text-slate-500 block text-[10px]">CV Factor</span>
                  <span className="font-semibold text-slate-800 font-mono">{currentProfile.coefficient_of_variation.toFixed(3)}</span>
                </div>
                <div className="p-2 bg-slate-50/80 rounded border border-slate-200">
                  <span className="text-slate-500 block text-[10px]">TOU Peak Overlap</span>
                  <span className="font-semibold text-amber-700 font-mono">{currentProfile.tou_peak_overlap_pct.toFixed(1)}%</span>
                </div>
              </div>

              <div className="p-2.5 bg-slate-50/80 rounded border border-slate-200 space-y-1">
                <span className="text-slate-500 text-[10px] uppercase font-mono tracking-wider">Profile Archetype Rationale</span>
                <p className="text-[11px] text-slate-700 leading-normal">
                  {currentProfile.selection_rationale || 'Selected centroid profile for Ward hierarchical clustering.'}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-500">No profile selected.</p>
          )}
        </div>
      </div>
    </div>
  );
};
