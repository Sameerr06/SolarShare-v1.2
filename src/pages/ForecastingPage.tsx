import React, { useEffect, useState } from 'react';
import { TrendingUp, Sun, Users, Activity } from 'lucide-react';
import { api } from '../api/client';
import { SolarForecastResponse, TenantForecastResponse } from '../types/api';
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

export const ForecastingPage: React.FC = () => {
  const [solarForecast, setSolarForecast] = useState<SolarForecastResponse | null>(null);
  const [tenantForecast, setTenantForecast] = useState<TenantForecastResponse | null>(null);
  const [selectedTenantId, setSelectedTenantId] = useState<number>(1);
  const [forecastHours, setForecastHours] = useState<number>(24);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sRes, tRes] = await Promise.all([
        api.getSolarForecast(forecastHours),
        api.getTenantForecast(selectedTenantId, forecastHours),
      ]);
      setSolarForecast(sRes);
      setTenantForecast(tRes);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch forecasting data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [selectedTenantId, forecastHours]);

  if (loading) return <LoadingState message="Fetching Prophet Forecast Data..." />;
  if (error || !solarForecast || !tenantForecast) return <ErrorState message={error || 'No forecast data.'} onRetry={fetchData} />;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Solar & Load Forecasting
            </h1>
            {solarForecast.is_demo ? (
              <DemoBadge label="SIMULATED" size="sm" note={solarForecast.explanatory_note} />
            ) : (
              <span className="px-2 py-0.5 text-[11px] font-mono rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-700">
                PROPHET ACTIVE
              </span>
            )}
          </div>
          <p className="text-slate-500 text-xs mt-0.5">
            Prophet time-series forecasting for solar PV generation and individual MSME tenant load curves.
          </p>
        </div>

        {/* Forecast Horizon Selector */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-slate-500 font-medium mr-1">Horizon:</span>
          {[24, 48, 72, 168].map((h) => (
            <button
              key={h}
              onClick={() => setForecastHours(h)}
              className={`pressable px-2.5 py-1 rounded text-xs font-mono ${
                forecastHours === h
                  ? 'bg-amber-500 text-slate-950 font-semibold'
                  : 'bg-white border border-slate-200 text-slate-700 hover:border-amber-500/50'
              }`}
            >
              {h === 168 ? '7d' : `${h}h`}
            </button>
          ))}
        </div>
      </div>

      {/* Provenance Banners */}
      <div className="flex flex-col gap-2.5">
        {solarForecast.is_demo ? (
          <DemoBanner note={solarForecast.explanatory_note} />
        ) : (
          <div className="w-full bg-white border border-slate-200 rounded-lg p-3 text-xs text-slate-700 flex items-start gap-2.5">
            <span className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 font-mono text-[10px] shrink-0 font-medium">
              SOLAR MODEL
            </span>
            <div className="flex-1 min-w-0">
              <span className="font-semibold text-slate-800 mr-2">NASA POWER PV Estimates</span>
              <span className="text-slate-500 text-[11px]">
                {solarForecast.explanatory_note}
              </span>
            </div>
          </div>
        )}

        {tenantForecast && !tenantForecast.is_demo && (
          <div className="w-full bg-white border border-slate-200 rounded-lg p-3 text-xs text-slate-700 flex items-start gap-2.5">
            <span className="px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/30 text-cyan-700 font-mono text-[10px] shrink-0 font-medium">
              TENANT MODEL
            </span>
            <div className="flex-1 min-w-0">
              <span className="font-semibold text-slate-800 mr-2">Zenodo Public Load Archetypes</span>
              <span className="text-slate-500 text-[11px]">
                {tenantForecast.explanatory_note}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 stagger-children">
        <StatCard
          title="Forecast Horizon"
          value={`${forecastHours} Hours`}
          subtext="Hourly Prediction Steps"
          icon={TrendingUp}
          iconColor="text-amber-700"
        />
        <StatCard
          title="Solar Generation Forecast"
          value={solarForecast.total_generation_forecast_kwh.toFixed(0)}
          unit="kWh"
          subtext={`Peak: ${solarForecast.peak_generation_kw.toFixed(1)} kW`}
          icon={Sun}
          iconColor="text-emerald-700"
          isDemo={solarForecast.is_demo}
        />
        <StatCard
          title="Tenant Demand Forecast"
          value={tenantForecast.total_consumption_forecast_kwh.toFixed(0)}
          unit="kWh"
          subtext={`Peak: ${tenantForecast.peak_demand_kw.toFixed(1)} kW`}
          icon={Users}
          iconColor="text-cyan-700"
          isDemo={tenantForecast.is_demo}
        />
        <StatCard
          title="Prophet Interval"
          value="80%"
          subtext="Upper / Lower Bounds"
          icon={Activity}
          iconColor="text-violet-600"
          isDemo={solarForecast.is_demo}
        />
      </div>

      {/* Solar Forecast Chart */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <Sun className="w-4 h-4 text-amber-700" />
              Solar PV Generation Forecast Curve ({forecastHours}h Horizon)
            </h3>
            <p className="text-[11px] text-slate-500 mt-0.5">Predicted generation with uncertainty bounds.</p>
          </div>
          {solarForecast.is_demo ? (
            <DemoBadge note="Illustrative Prophet solar curve" />
          ) : (
            <span className="px-2 py-0.5 text-[10px] font-mono bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 rounded">
              Prophet Active
            </span>
          )}
        </div>

        <div className="h-64 w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={solarForecast.forecast_data} margin={{ top: 10, right: 10, left: 5, bottom: 0 }}>
              <defs>
                <linearGradient id="solarForecastGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.8} />
              <XAxis dataKey="timestamp" stroke="#64748b" fontSize={10} tickFormatter={(val) => val.split('T')[1]?.substring(0, 5) || val} />
              <YAxis stroke="#64748b" fontSize={10} unit=" kW" />
              <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', borderRadius: '0.375rem', fontSize: '11px' }} />
              <Area type="monotone" dataKey="upper_bound_kw" name="Upper Bound (kW)" stroke="#64748b" strokeDasharray="3 3" fill="none" opacity={0.5} />
              <Area type="monotone" dataKey="predicted_value_kw" name="Solar Forecast (kW)" stroke="#f59e0b" strokeWidth={2} fillOpacity={1} fill="url(#solarForecastGrad)" />
              <Area type="monotone" dataKey="lower_bound_kw" name="Lower Bound (kW)" stroke="#64748b" strokeDasharray="3 3" fill="none" opacity={0.5} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Tenant Load Forecast Chart */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
          <div className="flex items-center gap-2.5">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <Users className="w-4 h-4 text-cyan-700" />
                Tenant Load Demand Forecast ({tenantForecast.tenant_name})
              </h3>
              <p className="text-[11px] text-slate-500 mt-0.5">Predicted hourly demand in kW.</p>
            </div>
            {tenantForecast.is_demo ? (
              <DemoBadge note="Illustrative tenant curve" />
            ) : (
              <span className="px-2 py-0.5 text-[10px] font-mono bg-cyan-500/10 border border-cyan-500/30 text-cyan-700 rounded shrink-0">
                Prophet Active
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium">Tenant:</span>
            <select
              value={selectedTenantId}
              onChange={(e) => setSelectedTenantId(Number(e.target.value))}
              className="bg-slate-50 border border-slate-200 rounded px-2.5 py-1 text-xs text-slate-800 focus:outline-none focus:border-amber-500"
            >
              {[1, 2, 3, 4, 5, 6].map((id) => (
                <option key={id} value={id}>
                  Tenant #{id}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="h-64 w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={tenantForecast.forecast_data} margin={{ top: 10, right: 10, left: 5, bottom: 0 }}>
              <defs>
                <linearGradient id="tenantForecastGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" opacity={0.8} />
              <XAxis dataKey="timestamp" stroke="#64748b" fontSize={10} tickFormatter={(val) => val.split('T')[1]?.substring(0, 5) || val} />
              <YAxis stroke="#64748b" fontSize={10} unit=" kW" />
              <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#e2e8f0', borderRadius: '0.375rem', fontSize: '11px' }} />
              <Area type="monotone" dataKey="predicted_value_kw" name="Tenant Load Forecast (kW)" stroke="#06b6d4" strokeWidth={2} fillOpacity={1} fill="url(#tenantForecastGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
