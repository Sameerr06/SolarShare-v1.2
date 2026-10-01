import React, { useEffect, useState } from 'react';
import { BarChart3, Database, Layers, Activity, Award, TrendingUp } from 'lucide-react';
import { api } from '../api/client';
import { AnalyticsOverviewResponse, LoadProfileRead } from '../types/api';
import { StatCard } from '../components/ui/StatCard';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
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

export const AnalyticsPage: React.FC = () => {
  const [analytics, setAnalytics] = useState<AnalyticsOverviewResponse | null>(null);
  const [selectedProfiles, setSelectedProfiles] = useState<LoadProfileRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [aRes, pRes] = await Promise.all([
        api.getAnalyticsOverview(),
        api.getSelectedLoadProfiles(),
      ]);
      setAnalytics(aRes);
      setSelectedProfiles(pRes);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch dataset analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) return <LoadingState message="Analyzing Dataset Observations..." />;
  if (error || !analytics) return <ErrorState message={error || 'No analytics.'} onRetry={fetchData} />;

  const cvParChartData = selectedProfiles.map((p) => ({
    name: p.series_name,
    cluster: `C${p.cluster_id}`,
    cv: p.coefficient_of_variation,
    par: p.peak_to_average_ratio,
    meanKw: p.mean_demand_kw,
    maxKw: p.max_demand_kw,
  }));

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-white tracking-tight">
              Dataset Analytics & Statistical Overview
            </h1>
            <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 text-[11px] font-mono">
              REAL DATASET
            </span>
          </div>
          <p className="text-slate-400 text-xs mt-0.5">
            Statistical metrics derived from 8,443,584 hourly observation records across 321 public load series.
          </p>
        </div>
      </div>

      {/* Real Dataset Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <StatCard
          title="Hourly Observations"
          value={analytics.total_observations}
          unit="obs"
          subtext="2012-01-01 to 2014-12-31"
          icon={Database}
          iconColor="text-emerald-400"
        />
        <StatCard
          title="Zenodo Public Series"
          value={analytics.total_public_series}
          unit="series"
          subtext="Zenodo Electricity Dataset"
          icon={Activity}
          iconColor="text-amber-400"
        />
        <StatCard
          title="Profiles Computed"
          value={analytics.total_profiles_computed}
          unit="profiles"
          subtext="Ward Hierarchical Clustering"
          icon={Layers}
          iconColor="text-cyan-400"
        />
        <StatCard
          title="Cluster Centroids"
          value={analytics.selected_profiles_count}
          unit="selected"
          subtext="Nearest Centroid Series"
          icon={Award}
          iconColor="text-violet-400"
        />
      </div>

      {/* Comparison Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* CV vs PAR Chart */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-amber-400" />
              Coefficient of Variation (CV) vs Peak-to-Average (PAR)
            </h3>
            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono text-[10px]">
              k=6 CENTROIDS
            </span>
          </div>

          <div className="h-64 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cvParChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.8} />
                <XAxis dataKey="name" stroke="#64748b" fontSize={10} />
                <YAxis stroke="#64748b" fontSize={10} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.375rem', fontSize: '11px' }} />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                <Bar dataKey="cv" name="Coefficient of Variation (CV)" fill="#f59e0b" radius={[2, 2, 0, 0]} />
                <Bar dataKey="par" name="Peak-to-Average Ratio (PAR)" fill="#06b6d4" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Mean vs Peak Demand Chart */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              Mean Demand vs Peak Demand Output (kW)
            </h3>
            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono text-[10px]">
              k=6 CENTROIDS
            </span>
          </div>

          <div className="h-64 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cvParChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.8} />
                <XAxis dataKey="name" stroke="#64748b" fontSize={10} />
                <YAxis stroke="#64748b" fontSize={10} unit=" kW" />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.375rem', fontSize: '11px' }} />
                <Legend wrapperStyle={{ fontSize: '11px' }} />
                <Bar dataKey="meanKw" name="Mean Demand (kW)" fill="#10b981" radius={[2, 2, 0, 0]} />
                <Bar dataKey="maxKw" name="Peak Demand (Max kW)" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Selected Profiles Statistical Summary Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden space-y-0">
        <div className="p-3 border-b border-slate-800 flex items-center justify-between">
          <h3 className="text-xs font-semibold text-white uppercase tracking-wider">
            6 Selected Centroid Series Statistical Summary
          </h3>
          <span className="text-[11px] text-slate-400 font-mono">Ingested Records</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs table-interactive">
            <thead>
              <tr className="bg-slate-950 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold text-[10px]">
                <th className="py-2.5 px-3">Cluster</th>
                <th className="py-2.5 px-3">Series Name</th>
                <th className="py-2.5 px-3 text-right">Mean Demand (kW)</th>
                <th className="py-2.5 px-3 text-right">Peak Demand (kW)</th>
                <th className="py-2.5 px-3 text-right">CV</th>
                <th className="py-2.5 px-3 text-right">PAR</th>
                <th className="py-2.5 px-3 text-right text-amber-400">Day/Night Ratio</th>
                <th className="py-2.5 px-3 text-right text-cyan-400">TOU Peak Overlap</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
              {selectedProfiles.map((p) => (
                <tr key={p.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="py-2.5 px-3 font-sans font-medium text-amber-400">Cluster #{p.cluster_id}</td>
                  <td className="py-2.5 px-3 font-sans font-medium text-white flex items-center gap-2">
                    {p.series_name}
                    <span className="px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 text-[9px] font-mono">
                      CENTROID
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right font-semibold text-white">{p.mean_demand_kw.toFixed(2)}</td>
                  <td className="py-2.5 px-3 text-right">{p.max_demand_kw.toFixed(2)}</td>
                  <td className="py-2.5 px-3 text-right">{p.coefficient_of_variation.toFixed(3)}</td>
                  <td className="py-2.5 px-3 text-right">{p.peak_to_average_ratio.toFixed(3)}</td>
                  <td className="py-2.5 px-3 text-right text-amber-400">{p.day_night_ratio.toFixed(2)}</td>
                  <td className="py-2.5 px-3 text-right text-cyan-400 font-semibold">{p.tou_peak_overlap_pct.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
