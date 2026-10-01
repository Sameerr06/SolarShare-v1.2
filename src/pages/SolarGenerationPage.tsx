import React, { useEffect, useState } from 'react';
import { Sun, Shield, Activity, Compass, Zap } from 'lucide-react';
import { api } from '../api/client';
import { PVConfigRead, SolarGenerationListResponse } from '../types/api';
import { StatCard } from '../components/ui/StatCard';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import { DemoBadge } from '../components/ui/DemoBadge';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export const SolarGenerationPage: React.FC = () => {
  const [pvConfig, setPvConfig] = useState<PVConfigRead | null>(null);
  const [generation, setGeneration] = useState<SolarGenerationListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [pvRes, genRes] = await Promise.all([
        api.getPVConfig(),
        api.getSolarGeneration(24),
      ]);
      setPvConfig(pvRes);
      setGeneration(genRes);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch solar generation telemetry');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) return <LoadingState message="Loading Solar PV Telemetry..." />;
  if (error || !pvConfig || !generation) return <ErrorState message={error || 'No solar telemetry.'} onRetry={fetchData} />;

  const chartData = generation.records.map((r) => ({
    time: typeof r.timestamp_local === 'string' && r.timestamp_local.includes('T')
      ? r.timestamp_local.split('T')[1].substring(0, 5)
      : r.timestamp_local,
    power: r.pv_power_kw,
    ghi: r.ghi_wm2,
    dni: r.dni_wm2,
    temp: r.cell_temperature_c,
  }));

  const maxGenKw = Math.max(...generation.records.map((r) => r.pv_power_kw), 0);
  const totalGenKwh = generation.records.reduce((acc, r) => acc + r.pv_energy_kwh, 0);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-white tracking-tight">
              Solar PV Generation & Irradiance
            </h1>
            {generation.is_demo ? (
              <DemoBadge note={generation.explanatory_note} />
            ) : (
              <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 text-[11px] font-mono">
                NASA POWER DATA
              </span>
            )}
          </div>
          <p className="text-slate-400 text-xs mt-0.5">
            500 kW STC Solar Array — Coimbatore MSME Estate (11.0168°N, 76.9558°E).
          </p>
        </div>
      </div>

      {/* PV System Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 stagger-children">
        <StatCard
          title="Installed PV Capacity"
          value={pvConfig.capacity_kw}
          unit="kW"
          subtext={`STC Rating | PR: ${(pvConfig.performance_ratio * 100).toFixed(0)}%`}
          icon={Sun}
          iconColor="text-amber-400"
        />
        <StatCard
          title="Peak Generation Output"
          value={maxGenKw.toFixed(1)}
          unit="kW"
          subtext="24h Maximum Output"
          icon={Activity}
          iconColor="text-emerald-400"
        />
        <StatCard
          title="Total Daily Production"
          value={totalGenKwh.toFixed(0)}
          unit="kWh"
          subtext="24-Hour Solar Energy"
          icon={Zap}
          iconColor="text-cyan-400"
        />
        <StatCard
          title="Module Efficiency"
          value={`${(pvConfig.efficiency * 100).toFixed(0)}%`}
          subtext="Monocrystalline PERC"
          icon={Shield}
          iconColor="text-violet-400"
        />
      </div>

      {/* 24-Hour Generation Curve & Solar Spec Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Main Generation Chart */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Sun className="w-4 h-4 text-amber-400" />
              24-Hour Solar Generation Profile (kW)
            </h3>
            {generation.is_demo && <DemoBadge size="sm" note="Illustrative bell curve" />}
          </div>

          <div className="h-64 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorPv" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.8} />
                <XAxis dataKey="time" stroke="#64748b" fontSize={10} />
                <YAxis stroke="#64748b" fontSize={10} unit=" kW" />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.375rem', fontSize: '11px' }} />
                <Area type="monotone" dataKey="power" name="PV Output (kW)" stroke="#f59e0b" strokeWidth={2} fillOpacity={1} fill="url(#colorPv)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* PV Specs Side Panel */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Compass className="w-4 h-4 text-amber-400" />
            PV Array Configuration
          </h3>

          <div className="space-y-2.5 text-xs">
            <div className="p-2.5 bg-slate-950 border border-slate-800 rounded space-y-0.5">
              <span className="text-slate-400 text-[10px]">Array Orientation</span>
              <p className="text-xs font-semibold text-white">South Facing (Azimuth 180°)</p>
              <p className="text-[10px] text-slate-400">Optimal Tilt Angle: 11.0°</p>
            </div>

            <div className="p-2.5 bg-slate-950 border border-slate-800 rounded space-y-1.5 font-mono text-[11px]">
              <div className="flex justify-between">
                <span className="text-slate-400">STC Rated Capacity:</span>
                <span className="text-amber-400 font-semibold">500.0 kW</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Performance Ratio:</span>
                <span className="text-emerald-400 font-semibold">0.80 (80%)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Cell Temp Range:</span>
                <span className="text-slate-200">25.0°C - 40.0°C</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Inverter Efficiency:</span>
                <span className="text-slate-200">98.5%</span>
              </div>
            </div>

            <div className="p-2.5 bg-slate-950 border border-slate-800 rounded text-[11px] text-slate-400">
              {pvConfig.notes || 'PV array configuration parameters for Coimbatore MSME Industrial Estate.'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
