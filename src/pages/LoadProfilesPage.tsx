import React, { useEffect, useState } from 'react';
import {
  Search,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Eye,
  Activity,
} from 'lucide-react';
import { api } from '../api/client';
import { LoadProfileRead } from '../types/api';
import { LoadingState, ErrorState, EmptyState } from '../components/ui/StateViews';
import { Modal } from '../components/ui/Modal';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

export const LoadProfilesPage: React.FC = () => {
  const [profiles, setProfiles] = useState<LoadProfileRead[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [selectedCount, setSelectedCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Pagination
  const [selectedOnly, setSelectedOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [clusterFilter, setClusterFilter] = useState<string>('ALL');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(20);

  // Profile Detail Modal
  const [selectedProfileDetail, setSelectedProfileDetail] = useState<LoadProfileRead | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchProfiles = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getLoadProfiles({ selected_only: selectedOnly, limit: 350, offset: 0 });
      setProfiles(res.profiles);
      setTotalCount(res.total_count);
      setSelectedCount(res.selected_count);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch load profiles dataset');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfiles();
  }, [selectedOnly]);

  const filteredProfiles = profiles.filter((p) => {
    const matchesSearch =
      !searchQuery ||
      p.series_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.series_id.toString().includes(searchQuery);

    const matchesCluster =
      clusterFilter === 'ALL' || (p.cluster_id !== undefined && p.cluster_id.toString() === clusterFilter);

    return matchesSearch && matchesCluster;
  });

  const totalPages = Math.ceil(filteredProfiles.length / pageSize) || 1;
  const paginatedProfiles = filteredProfiles.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const openDetail = (prof: LoadProfileRead) => {
    setSelectedProfileDetail(prof);
    setIsModalOpen(true);
  };

  const getShapeDataForChart = (prof: LoadProfileRead) => {
    const weekdayValues: number[] = Array.isArray(prof.weekday_shape)
      ? prof.weekday_shape
      : (prof.weekday_shape as any)?.values_kw || (prof.weekday_shape as any)?.normalized_values || [];

    const weekendValues: number[] = Array.isArray(prof.weekend_shape)
      ? prof.weekend_shape
      : (prof.weekend_shape as any)?.values_kw || (prof.weekend_shape as any)?.normalized_values || [];

    const chartData = [];
    for (let h = 0; h < 24; h++) {
      const hourStr = `${h.toString().padStart(2, '0')}:00`;
      const wVal = weekdayValues[h] !== undefined ? weekdayValues[h] : 0;
      const weVal = weekendValues[h] !== undefined ? weekendValues[h] : 0;

      chartData.push({
        hour: hourStr,
        weekday: Number(wVal.toFixed(3)),
        weekend: Number(weVal.toFixed(3)),
      });
    }
    return chartData;
  };

  return (
    <div className="space-y-5">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-white tracking-tight">
              321 → 6 Load Profiling Catalog
            </h1>
            <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 text-[11px] font-mono">
              {totalCount} PROFILES
            </span>
          </div>
          <p className="text-slate-400 text-xs mt-0.5">
            Ward hierarchical clustering over 8.44M electricity observation records.
          </p>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-900 border border-slate-800 rounded text-xs font-mono text-slate-300">
          Centroids: T258, T11, T301, T300, T84, T3
        </div>
      </div>

      {/* Highlights of 6 Selected Profiles Cards */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Cluster Centroids (k=6)
          </h3>
          <span className="text-[11px] text-slate-400 font-mono">Ward Hierarchical Clustering</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
          {profiles.filter((p) => p.is_selected).map((prof) => (
            <div
              key={prof.series_name}
              onClick={() => openDetail(prof)}
              className="p-2.5 bg-slate-950/80 border border-slate-800 hover:border-amber-500/50 hover:-translate-y-0.5 cursor-pointer transition-all duration-200 rounded space-y-1.5 group"
            >
              <div className="flex items-center justify-between">
                <span className="px-1.5 py-0.5 rounded bg-slate-800 text-amber-400 text-[10px] font-mono">
                  C{prof.cluster_id}
                </span>
                <span className="text-[9px] font-mono text-emerald-400">
                  CENTROID
                </span>
              </div>

              <div>
                <span className="font-semibold text-white text-xs block group-hover:text-amber-400 transition-colors">
                  {prof.series_name}
                </span>
                <span className="text-[10px] text-slate-400">
                  Mean: <strong className="text-slate-200 font-mono">{prof.mean_demand_kw.toFixed(1)} kW</strong>
                </span>
              </div>

              <div className="grid grid-cols-2 gap-1 text-[10px] pt-1 border-t border-slate-800 text-slate-400 font-mono">
                <div>CV: {prof.coefficient_of_variation.toFixed(2)}</div>
                <div>PAR: {prof.peak_to_average_ratio.toFixed(2)}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Controls Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-900 border border-slate-800 rounded-lg p-3">
        {/* Search */}
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search series (e.g. T258)..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            className="w-full bg-slate-950 border border-slate-800 rounded pl-8 pr-3 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto justify-end">
          <button
            onClick={() => {
              setSelectedOnly(!selectedOnly);
              setCurrentPage(1);
            }}
            className={`pressable px-2.5 py-1 rounded text-xs ${
              selectedOnly
                ? 'bg-amber-500 text-slate-950 font-semibold'
                : 'bg-slate-800 text-slate-300 hover:bg-slate-750'
            }`}
          >
            Centroids Only ({selectedCount})
          </button>

          <select
            value={clusterFilter}
            onChange={(e) => {
              setClusterFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-xs text-slate-300 focus:outline-none focus:border-amber-500"
          >
            <option value="ALL">All Clusters (0 - 5)</option>
            <option value="0">Cluster 0</option>
            <option value="1">Cluster 1</option>
            <option value="2">Cluster 2</option>
            <option value="3">Cluster 3</option>
            <option value="4">Cluster 4</option>
            <option value="5">Cluster 5</option>
          </select>

          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setCurrentPage(1);
            }}
            className="bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-amber-500"
          >
            <option value={15}>15 / page</option>
            <option value={25}>25 / page</option>
            <option value={50}>50 / page</option>
            <option value={100}>100 / page</option>
          </select>
        </div>
      </div>

      {/* Profiles Data Table */}
      {loading ? (
        <LoadingState message="Querying profile database..." />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchProfiles} />
      ) : paginatedProfiles.length === 0 ? (
        <EmptyState title="No matching load profiles" message="Try relaxing your search query or cluster filter." />
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden space-y-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs table-interactive">
              <thead>
                <tr className="bg-slate-950 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold text-[10px]">
                  <th className="py-2.5 px-3">Series ID / Name</th>
                  <th className="py-2.5 px-3">Cluster</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Mean Demand (kW)</th>
                  <th className="py-2.5 px-3 text-right">Max Demand (kW)</th>
                  <th className="py-2.5 px-3 text-right">CV</th>
                  <th className="py-2.5 px-3 text-right">PAR</th>
                  <th className="py-2.5 px-3 text-right">TOU Peak Overlap</th>
                  <th className="py-2.5 px-3 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
                {paginatedProfiles.map((p) => (
                  <tr
                    key={p.id}
                    className={`hover:bg-slate-800/40 transition-colors ${
                      p.is_selected ? 'bg-amber-500/5 font-medium' : ''
                    }`}
                  >
                    <td className="py-2.5 px-3 font-sans font-medium text-white flex items-center gap-2">
                      <span className="text-amber-400">{p.series_name || `Series #${p.series_id}`}</span>
                      {p.is_selected && (
                        <span className="px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 text-[9px] font-mono">
                          CENTROID
                        </span>
                      )}
                    </td>

                    <td className="py-2.5 px-3 font-sans">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[10px]">
                        Cluster {p.cluster_id ?? 'N/A'}
                      </span>
                    </td>

                    <td className="py-2.5 px-3 font-sans">
                      {p.is_selected ? (
                        <span className="inline-flex items-center gap-1 text-emerald-400 text-[11px] font-medium">
                          <CheckCircle2 className="w-3 h-3" /> Selected Centroid
                        </span>
                      ) : (
                        <span className="text-slate-500 text-[11px]">Computed</span>
                      )}
                    </td>

                    <td className="py-2.5 px-3 text-right font-semibold text-white">
                      {p.mean_demand_kw.toFixed(2)}
                    </td>

                    <td className="py-2.5 px-3 text-right">{p.max_demand_kw.toFixed(2)}</td>

                    <td className="py-2.5 px-3 text-right text-slate-300">{p.coefficient_of_variation.toFixed(3)}</td>

                    <td className="py-2.5 px-3 text-right text-slate-300">{p.peak_to_average_ratio.toFixed(3)}</td>

                    <td className="py-2.5 px-3 text-right text-amber-400">
                      {p.tou_peak_overlap_pct.toFixed(1)}%
                    </td>

                    <td className="py-2.5 px-3 text-center font-sans">
                      <button
                        onClick={() => openDetail(p)}
                        className="pressable px-2 py-0.5 bg-slate-800 hover:bg-amber-500 hover:text-slate-950 text-slate-300 rounded text-[11px] font-medium inline-flex items-center gap-1"
                      >
                        <Eye className="w-3 h-3" /> Shape
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          <div className="p-3 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-400">
            <span>
              Showing{' '}
              <strong className="text-white">
                {(currentPage - 1) * pageSize + 1} - {Math.min(currentPage * pageSize, filteredProfiles.length)}
              </strong>{' '}
              of <strong className="text-white">{filteredProfiles.length}</strong> matching profiles
            </span>

            <div className="flex items-center gap-2">
              <button
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((prev) => prev - 1)}
                className="pressable p-1 rounded bg-slate-800 hover:bg-slate-750 disabled:opacity-40 disabled:pointer-events-none text-slate-300"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="font-semibold text-slate-200">
                Page {currentPage} of {totalPages}
              </span>
              <button
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((prev) => prev + 1)}
                className="pressable p-1 rounded bg-slate-800 hover:bg-slate-750 disabled:opacity-40 disabled:pointer-events-none text-slate-300"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Profile Detail Drawer Modal */}
      {selectedProfileDetail && (
        <Modal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          title={`Load Profile Analysis: ${selectedProfileDetail.series_name}`}
          subtitle={`Cluster #${selectedProfileDetail.cluster_id} | Zenodo Series #${selectedProfileDetail.series_id}`}
          maxWidth="4xl"
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3 bg-slate-950 border border-slate-800 rounded text-xs font-mono">
              <div>
                <span className="text-slate-400 block font-sans text-[10px]">Mean Demand</span>
                <span className="text-sm font-semibold text-white">{selectedProfileDetail.mean_demand_kw.toFixed(2)} kW</span>
              </div>
              <div>
                <span className="text-slate-400 block font-sans text-[10px]">Peak Demand</span>
                <span className="text-sm font-semibold text-amber-400">{selectedProfileDetail.max_demand_kw.toFixed(2)} kW</span>
              </div>
              <div>
                <span className="text-slate-400 block font-sans text-[10px]">Coef. Variation</span>
                <span className="text-sm font-semibold text-cyan-400">{selectedProfileDetail.coefficient_of_variation.toFixed(3)}</span>
              </div>
              <div>
                <span className="text-slate-400 block font-sans text-[10px]">Peak-to-Avg</span>
                <span className="text-sm font-semibold text-violet-400">{selectedProfileDetail.peak_to_average_ratio.toFixed(3)}</span>
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded p-3 space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                  <Activity className="w-4 h-4 text-amber-400" />
                  24-Hour Load Demand Shapes (Weekday vs Weekend)
                </h4>
              </div>

              <div className="h-60 w-full pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={getShapeDataForChart(selectedProfileDetail)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.8} />
                    <XAxis dataKey="hour" stroke="#64748b" fontSize={10} />
                    <YAxis stroke="#64748b" fontSize={10} label={{ value: 'Normalized Demand', angle: -90, position: 'insideLeft', fill: '#64748b', fontSize: 10 }} />
                    <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.375rem', fontSize: '11px' }} />
                    <Legend wrapperStyle={{ fontSize: '11px' }} />
                    <Line type="monotone" dataKey="weekday" name="Weekday 24h Shape" stroke="#f59e0b" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="weekend" name="Weekend 24h Shape" stroke="#06b6d4" strokeWidth={2} strokeDasharray="4 4" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1.5">
                <span className="font-semibold text-slate-200 block text-xs">Derived Metrics</span>
                <div className="space-y-1 font-mono text-slate-300 text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Day/Night Demand Ratio:</span>
                    <span>{selectedProfileDetail.day_night_ratio.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Weekday/Weekend Ratio:</span>
                    <span>{selectedProfileDetail.weekday_weekend_ratio.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">TOU Peak Period Overlap:</span>
                    <span className="text-amber-400 font-semibold">{selectedProfileDetail.tou_peak_overlap_pct.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Observation Count:</span>
                    <span>{selectedProfileDetail.observation_count?.toLocaleString() || '26,304'}</span>
                  </div>
                </div>
              </div>

              <div className="p-3 bg-slate-950 border border-slate-800 rounded space-y-1.5">
                <span className="font-semibold text-slate-200 block text-xs">Archetype Selection Info</span>
                <p className="text-slate-300 leading-normal text-[11px]">
                  {selectedProfileDetail.selection_rationale ||
                    'Series computed via Ward hierarchical clustering over PCA-reduced 24-hour load features.'}
                </p>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
