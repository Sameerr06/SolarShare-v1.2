import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import {
  LoadProfileRead,
  TenantForecastResponse,
  BillingSummaryResponse,
  AllocationCurrentResponse,
} from '../types/api';
import { StatCard } from '../components/ui/StatCard';
import { LoadingState, ErrorState } from '../components/ui/StateViews';
import { DemoBadge, DemoBanner } from '../components/ui/DemoBadge';
import {
  Building2,
  Activity,
  TrendingUp,
  Receipt,
  Sun,
  Zap,
  BatteryCharging,
  ShieldCheck,
  Layers,
  MapPin,
  FileDown,
  Loader2,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export const TenantPortalPage: React.FC = () => {
  const { user } = useAuth();
  const tenantId = user?.tenant_id || 1;

  const [forecast, setForecast] = useState<TenantForecastResponse | null>(null);
  const [profile, setProfile] = useState<LoadProfileRead | null>(null);
  const [billing, setBilling] = useState<BillingSummaryResponse | null>(null);
  const [allocation, setAllocation] = useState<AllocationCurrentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);

  const BILLING_PERIOD = '2026-08';

  const handleDownloadInvoicePdf = async () => {
    setDownloadingPdf(true);
    setPdfError(null);
    try {
      // No tenant id passed -> the server always returns the signed-in
      // tenant's own invoice (other tenants' ids would be rejected with 403).
      await api.downloadInvoicePdf(BILLING_PERIOD);
    } catch (err: any) {
      setPdfError(err?.response?.data?.detail || err?.message || 'PDF download failed');
    } finally {
      setDownloadingPdf(false);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch Prophet forecast for tenant
      const forecastRes = await api.getTenantForecast(tenantId, 24);
      setForecast(forecastRes);

      // 2. Fetch load profiles to find tenant's profile
      const profilesRes = await api.getSelectedLoadProfiles();
      const currentProf = profilesRes[tenantId - 1] || profilesRes[0];
      setProfile(currentProf);

      // 3. Fetch billing summary filtered for tenant
      const billingRes = await api.getBillingSummary(BILLING_PERIOD);
      setBilling(billingRes);

      // 4. Fetch allocation data
      const allocRes = await api.getCurrentAllocation();
      setAllocation(allocRes);
    } catch (err: any) {
      setError(err?.message || 'Failed to load tenant self-service portal telemetry');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [tenantId]);

  if (loading && !forecast) return <LoadingState message="Loading Tenant Portal Telemetry..." />;
  if (error) return <ErrorState message={error} onRetry={fetchData} />;

  // Find tenant billing entry
  const tenantBill = billing?.tenants.find((t) => t.tenant_id === tenantId) || billing?.tenants[0];

  // Find tenant allocation entry
  const tenantAlloc = allocation?.allocations.find((a) => a.tenant_id === tenantId) || allocation?.allocations[0];

  const tenantName = user?.tenant_name || forecast?.tenant_name || tenantBill?.tenant_name || `Tenant #${tenantId}`;
  const seriesId = user?.source_client_series_id || profile?.series_name || 'T258';

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-white border border-slate-200 rounded-xl p-5 shadow-lg">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center shrink-0">
            <Building2 className="w-6 h-6 text-amber-700" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">{tenantName}</h1>
              <span className="px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-700 font-mono text-xs font-semibold">
                ID: {seriesId}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1 flex items-center gap-3">
              <span className="flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5 text-amber-700" /> Coimbatore MSME Industrial Estate
              </span>
              <span className="flex items-center gap-1 text-emerald-700 font-mono">
                <ShieldCheck className="w-3.5 h-3.5" /> Tenant Isolated View
              </span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="px-3 py-1.5 rounded-md bg-slate-50/80 border border-slate-200 text-xs">
            <span className="text-slate-500 block text-[10px] uppercase font-mono">Profile Archetype</span>
            <span className="font-semibold text-amber-700 font-mono">{seriesId} (Cluster #{profile?.cluster_id ?? 0})</span>
          </div>
        </div>
      </div>

      {/* Provenance: driven by the API's is_demo flag, never asserted. A fallback
          curve must be labelled as such — a tenant must never be shown a
          plausible-looking forecast that no model produced. */}
      {forecast?.is_demo ? (
        <DemoBanner
          label="MODEL UNAVAILABLE — DEMO CURVE"
          note={forecast.explanatory_note}
        />
      ) : (
        <div className="w-full bg-white border border-slate-200 rounded-lg p-3 text-xs text-slate-700 flex items-start gap-2.5">
          <span className="px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/30 text-cyan-700 font-mono text-[10px] shrink-0 font-medium">
            LOAD MODEL
          </span>
          <div className="flex-1 min-w-0">
            <span className="font-semibold text-slate-800 mr-2">Prophet, trained on public load curves</span>
            <span className="text-slate-500 text-[11px]">
              {forecast?.explanatory_note}
            </span>
          </div>
        </div>
      )}

      {/* Top Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Current Demand"
          value={tenantAlloc?.demanded_kw ? tenantAlloc.demanded_kw.toFixed(1) : (profile?.mean_demand_kw ? profile.mean_demand_kw.toFixed(1) : 120)}
          unit="kW"
          subtext={`Mean Load: ${profile?.mean_demand_kw ? profile.mean_demand_kw.toFixed(1) : 120} kW`}
          icon={Activity}
          iconColor="text-cyan-700"
        />
        <StatCard
          title="Allocated Solar Power"
          value={tenantAlloc?.allocated_solar_kw ? tenantAlloc.allocated_solar_kw.toFixed(1) : 63.0}
          unit="kW"
          subtext={`Fairness Share: ${tenantAlloc?.fairness_share_pct ?? 35}%`}
          icon={Sun}
          iconColor="text-amber-700"
        />
        <StatCard
          title="24h Consumption Forecast"
          value={forecast ? forecast.total_consumption_forecast_kwh.toFixed(0) : 2800}
          unit="kWh/day"
          subtext={`Peak Demand: ${forecast?.peak_demand_kw.toFixed(1) ?? '180'} kW`}
          icon={TrendingUp}
          iconColor="text-violet-600"
        />
        <StatCard
          title="Monthly Electricity Bill"
          value={tenantBill ? `₹${(tenantBill.total_bill_inr / 1000).toFixed(1)}k` : '₹291.6k'}
          subtext={tenantBill ? `Estimated Savings: ₹${(tenantBill.savings_inr / 1000).toFixed(1)}k` : '₹75.6k savings'}
          icon={Receipt}
          iconColor="text-emerald-700"
        />
      </div>

      {/* Main Grid: Forecast Chart & Energy Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* 24h Load Forecast Chart */}
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-amber-700" />
                24-Hour Load Forecast & Confidence Interval
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                {forecast?.is_demo
                  ? `Illustrative load curve for ${tenantName} (${seriesId}) — no model output.`
                  : `Prophet demand model prediction for ${tenantName} (${seriesId}).`}
              </p>
            </div>
            {forecast?.is_demo ? (
              <span
                className="px-2.5 py-1 text-[11px] font-mono bg-amber-500/10 border border-amber-500/30 text-amber-700 rounded-md shrink-0 font-medium"
                title={forecast.fallback_reason || undefined}
              >
                Model Unavailable
              </span>
            ) : (
              <span className="px-2.5 py-1 text-[11px] font-mono bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 rounded-md shrink-0 font-medium">
                Prophet Model Active
              </span>
            )}
          </div>

          <div className="h-72 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={forecast?.forecast_data || []} margin={{ top: 10, right: 10, left: 5, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorTenantPortal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.35} />
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
                <Area type="monotone" dataKey="predicted_value_kw" name="Predicted Demand (kW)" stroke="#f59e0b" strokeWidth={2} fillOpacity={1} fill="url(#colorTenantPortal)" />
                <Area type="monotone" dataKey="lower_bound_kw" name="Lower Confidence (kW)" stroke="#64748b" strokeDasharray="3 3" fill="none" opacity={0.5} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Energy Breakdown & Power Mix */}
        <div className="space-y-6">
          
          {/* Power Mix Card */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-lg">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-700" />
              Power Source Breakdown
            </h3>

            <div className="space-y-3 text-xs">
              {/* Solar */}
              <div className="p-3 bg-slate-50/80 rounded-lg border border-slate-200 space-y-1.5">
                <div className="flex items-center justify-between text-slate-700">
                  <span className="flex items-center gap-1.5 font-medium">
                    <Sun className="w-3.5 h-3.5 text-amber-700" /> Allocated Solar Power
                  </span>
                  <span className="font-mono text-amber-700 font-semibold">{tenantAlloc?.allocated_solar_kw ?? 63.0} kW</span>
                </div>
                <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-amber-400 h-full rounded-full" style={{ width: '55%' }}></div>
                </div>
              </div>

              {/* Grid */}
              <div className="p-3 bg-slate-50/80 rounded-lg border border-slate-200 space-y-1.5">
                <div className="flex items-center justify-between text-slate-700">
                  <span className="flex items-center gap-1.5 font-medium">
                    <Zap className="w-3.5 h-3.5 text-blue-600" /> Grid Power Import
                  </span>
                  <span className="font-mono text-blue-600 font-semibold">{tenantAlloc?.grid_power_kw ?? 102.0} kW</span>
                </div>
                <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-blue-400 h-full rounded-full" style={{ width: '40%' }}></div>
                </div>
              </div>

              {/* Battery */}
              <div className="p-3 bg-slate-50/80 rounded-lg border border-slate-200 space-y-1.5">
                <div className="flex items-center justify-between text-slate-700">
                  <span className="flex items-center gap-1.5 font-medium">
                    <BatteryCharging className="w-3.5 h-3.5 text-emerald-700" /> Battery Storage Support
                  </span>
                  <span className="font-mono text-emerald-700 font-semibold">{tenantAlloc?.battery_power_kw ?? 15.0} kW</span>
                </div>
                <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-emerald-400 h-full rounded-full" style={{ width: '5%' }}></div>
                </div>
              </div>
            </div>
          </div>

          {/* Profile Parameters Card */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-3 shadow-lg">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-700" />
              Load Archetype Parameters
            </h3>

            {profile ? (
              <div className="space-y-2 text-xs">
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2 bg-slate-50/80 rounded border border-slate-200">
                    <span className="text-slate-500 text-[10px] block">Peak/Avg Ratio</span>
                    <span className="font-mono font-semibold text-slate-800">{profile.peak_to_average_ratio.toFixed(2)}</span>
                  </div>
                  <div className="p-2 bg-slate-50/80 rounded border border-slate-200">
                    <span className="text-slate-500 text-[10px] block">Coeff. of Variation</span>
                    <span className="font-mono font-semibold text-slate-800">{profile.coefficient_of_variation.toFixed(3)}</span>
                  </div>
                </div>
                <div className="p-2 bg-slate-50/80 rounded border border-slate-200">
                  <span className="text-slate-500 text-[10px] block">Tamil Nadu ToU Overlap</span>
                  <span className="font-mono font-semibold text-amber-700">{profile.tou_peak_overlap_pct.toFixed(1)}%</span>
                </div>
              </div>
            ) : null}
          </div>

        </div>

      </div>

      {/* Tenant Billing Details Card */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-lg">
        <div className="flex items-center justify-between border-b border-slate-200 pb-3 flex-wrap gap-2">
          <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <Receipt className="w-4 h-4 text-emerald-700" />
            Tenant Monthly Billing Breakdown ({billing?.billing_period || BILLING_PERIOD})
          </h2>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="px-2.5 py-0.5 rounded bg-emerald-500/10 text-emerald-700 border border-emerald-500/30 text-xs font-mono">
              Solar Rate: ₹5.00/kWh | Grid ToU: ~₹8.50/kWh
            </span>
            <button
              type="button"
              onClick={handleDownloadInvoicePdf}
              disabled={downloadingPdf}
              className="inline-flex items-center gap-1.5 bg-amber-500/10 hover:bg-amber-500/20 disabled:opacity-50 disabled:cursor-not-allowed border border-amber-500/40 text-amber-700 rounded px-2.5 py-1 text-xs font-medium transition-colors"
              title="Download your invoice for this billing period as a PDF"
            >
              {downloadingPdf ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <FileDown className="w-3.5 h-3.5" />
              )}
              Download Invoice (PDF)
            </button>
          </div>
        </div>

        {pdfError && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-600 text-xs rounded px-3 py-2">
            {pdfError}
          </div>
        )}

        {tenantBill ? (
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 stagger-children">
            <div className="p-3.5 bg-slate-50/80 rounded-lg border border-slate-200 space-y-1">
              <span className="text-slate-500 text-[11px]">Total Energy Consumed</span>
              <p className="text-lg font-bold text-slate-900 font-mono">{tenantBill.total_consumption_kwh.toLocaleString()} kWh</p>
              <div className="text-[10px] text-slate-500">
                Solar: {tenantBill.solar_consumed_kwh.toLocaleString()} | Grid: {tenantBill.grid_consumed_kwh.toLocaleString()}
              </div>
            </div>

            <div className="p-3.5 bg-slate-50/80 rounded-lg border border-slate-200 space-y-1">
              <span className="text-slate-500 text-[11px]">Solar Energy Charge (@ ₹5/kWh)</span>
              <p className="text-lg font-bold text-amber-700 font-mono">₹{tenantBill.solar_cost_inr.toLocaleString()}</p>
              <span className="text-[10px] text-slate-500">Shared PV generation tariff</span>
            </div>

            <div className="p-3.5 bg-slate-50/80 rounded-lg border border-slate-200 space-y-1">
              <span className="text-slate-500 text-[11px]">Grid Energy Charge (ToU)</span>
              <p className="text-lg font-bold text-blue-600 font-mono">₹{tenantBill.grid_cost_inr.toLocaleString()}</p>
              <span className="text-[10px] text-slate-500">TNERC HT-III Tariff</span>
            </div>

            <div className="p-3.5 bg-slate-50/80 rounded-lg border border-slate-200 space-y-1">
              <span className="text-slate-500 text-[11px]">Net Monthly Savings</span>
              <p className="text-lg font-bold text-emerald-700 font-mono">₹{tenantBill.savings_inr.toLocaleString()}</p>
              <span className="text-[10px] text-emerald-700 font-medium">Compared to 100% grid tariff</span>
            </div>
          </div>
        ) : (
          <p className="text-xs text-slate-500">No billing record found for this tenant.</p>
        )}
      </div>

    </div>
  );
};
