import React, { useEffect, useState } from 'react';
import { BatteryCharging, Battery, Zap, ShieldCheck, Activity, Cpu } from 'lucide-react';
import { api } from '../api/client';
import { BatteryConfigRead, BatteryStatusResponse } from '../types/api';
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

export const BatteryPage: React.FC = () => {
  const [bConfig, setBConfig] = useState<BatteryConfigRead | null>(null);
  const [bStatus, setBStatus] = useState<BatteryStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [cfgRes, statusRes] = await Promise.all([
        api.getBatteryConfig(),
        api.getBatteryStatus(),
      ]);
      setBConfig(cfgRes);
      setBStatus(statusRes);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch battery telemetry demo');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) return <LoadingState message="Connecting to Battery Energy Storage System (BESS)..." />;
  if (error || !bConfig || !bStatus) return <ErrorState message={error || 'No battery status.'} onRetry={fetchData} />;

  const scheduleData = [
    { hour: '00:00', soc: 40, power: -15 },
    { hour: '04:00', soc: 30, power: -10 },
    { hour: '08:00', soc: 50, power: 25 },
    { hour: '12:00', soc: 88, power: 45 },
    { hour: '16:00', soc: 75, power: -20 },
    { hour: '20:00', soc: 55, power: -30 },
    { hour: '23:00', soc: 42, power: -10 },
  ];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-white tracking-tight">
              Battery Storage (BESS)
            </h1>
            <DemoBadge label="SIMULATED" size="sm" note={bStatus.explanatory_note} />
          </div>
          <p className="text-slate-400 text-xs mt-0.5">
            200 kWh Lithium Iron Phosphate (LFP) BESS Telemetry & State-of-Charge loop.
          </p>
        </div>
      </div>

      <DemoBanner note={bStatus.explanatory_note} />

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <StatCard
          title="Current State of Charge"
          value={`${bStatus.current_soc_pct}%`}
          subtext={`${bStatus.current_stored_kwh} / ${bStatus.capacity_kwh} kWh`}
          icon={BatteryCharging}
          iconColor="text-emerald-400"
          isDemo={true}
        />
        <StatCard
          title="Power Output"
          value={`${bStatus.current_power_kw} kW`}
          subtext={`Mode: ${bStatus.operation_mode}`}
          icon={Zap}
          iconColor="text-amber-400"
          isDemo={true}
        />
        <StatCard
          title="State of Health (SOH)"
          value={`${bStatus.health_soh_pct}%`}
          subtext="LFP Cell Degradation Normal"
          icon={ShieldCheck}
          iconColor="text-cyan-400"
          isDemo={true}
        />
        <StatCard
          title="Round-Trip Efficiency"
          value={`${(bConfig.round_trip_efficiency * 100).toFixed(0)}%`}
          subtext={`Max Charge: ${bConfig.max_charge_kw} kW`}
          icon={Cpu}
          iconColor="text-violet-400"
          isDemo={true}
        />
      </div>

      {/* Main SOC & Battery Status Visualizer */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* SOC Visual Gauge */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 flex flex-col justify-between space-y-4">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Battery className="w-4 h-4 text-emerald-400" />
            BESS Storage Status
          </h3>

          <div className="flex flex-col items-center justify-center p-4 space-y-3">
            <div className="w-32 h-32 flex items-center justify-center rounded-full bg-slate-950 border-2 border-slate-800">
              <div className="text-center space-y-0.5">
                <span className="text-2xl font-bold font-mono text-emerald-400">{bStatus.current_soc_pct}%</span>
                <span className="text-[10px] text-slate-400 font-mono block uppercase">State of Charge</span>
              </div>
            </div>

            <div className="w-full space-y-1.5">
              <div className="flex justify-between text-xs text-slate-400 font-mono text-[11px]">
                <span>Min ({bConfig.min_soc_pct}%)</span>
                <span className="text-white font-semibold">{bStatus.current_stored_kwh} kWh</span>
                <span>Max ({bConfig.max_soc_pct}%)</span>
              </div>
              <div className="w-full bg-slate-950 border border-slate-800 h-2.5 rounded-full overflow-hidden p-0.5">
                <div
                  className="bg-emerald-500 h-full rounded-full transition-all duration-300"
                  style={{ width: `${bStatus.current_soc_pct}%` }}
                />
              </div>
            </div>
          </div>

          <div className="p-2.5 bg-slate-950 border border-slate-800 rounded text-xs font-mono space-y-1 text-[11px]">
            <div className="flex justify-between text-slate-400">
              <span>Operation Mode:</span>
              <span className="text-emerald-400 font-semibold">{bStatus.operation_mode}</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Current Power:</span>
              <span className="text-amber-400 font-semibold">{bStatus.current_power_kw} kW</span>
            </div>
          </div>
        </div>

        {/* 24-Hour Battery Schedule Simulation Chart */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-amber-400" />
              24-Hour Battery SOC Curve (Simulation)
            </h3>
            <DemoBadge note="Battery schedule simulation" />
          </div>

          <div className="h-64 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={scheduleData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="socGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.8} />
                <XAxis dataKey="hour" stroke="#64748b" fontSize={10} />
                <YAxis stroke="#64748b" fontSize={10} unit="%" />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.375rem', fontSize: '11px' }} />
                <Area type="monotone" dataKey="soc" name="State of Charge (%)" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#socGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
