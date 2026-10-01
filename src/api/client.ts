import axios from 'axios';
import {
  DashboardOverviewResponse,
  LoadProfilesListResponse,
  LoadProfileRead,
  PVConfigRead,
  SolarGenerationListResponse,
  SolarForecastResponse,
  TenantForecastResponse,
  AllocationCurrentResponse,
  BatteryConfigRead,
  BatteryStatusResponse,
  TariffRead,
  BillingSummaryResponse,
  InvoiceListResponse,
  AnalyticsOverviewResponse,
  HealthCheckResponse,
  UserRead,
  TokenResponse,
  EstateRead,
  EstatePreset,
  EstateCreatePayload,
  EstateUpdatePayload,
  EstateSyncWeatherResponse,
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('solarshare_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * Id of the estate the dashboard is currently showing.
 *
 * Stored in localStorage rather than React state so the API layer can read it
 * synchronously without importing the Estate context (which would create a
 * circular dependency). Every estate-scoped endpoint below defaults to this,
 * so switching location re-points the whole dashboard at the new coordinates.
 */
const ACTIVE_ESTATE_KEY = 'solarshare_active_estate_id';

export const getActiveEstateId = (): number | undefined => {
  const raw = localStorage.getItem(ACTIVE_ESTATE_KEY);
  if (!raw) return undefined;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
};

export const setActiveEstateId = (id: number): void => {
  localStorage.setItem(ACTIVE_ESTATE_KEY, String(id));
};

export const clearActiveEstateId = (): void => {
  localStorage.removeItem(ACTIVE_ESTATE_KEY);
};

/** Resolve an explicit id, else the active estate. */
const estateParam = (estateId?: number): { estate_id?: number } =>
  estateId !== undefined ? { estate_id: estateId } : { estate_id: getActiveEstateId() };

/** Trigger a browser download for a Blob (PDF etc.). */
export const saveBlob = (blob: Blob, filename: string): void => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

/** Pull the filename out of a Content-Disposition header, else use the fallback. */
const filenameFromDisposition = (headers: unknown, fallback: string): string => {
  const h = headers as Record<string, unknown> | undefined;
  const raw =
    (h?.['content-disposition'] as string | undefined) ??
    (typeof (h as { get?: (k: string) => string | null })?.get === 'function'
      ? (h as unknown as { get: (k: string) => string | null }).get('content-disposition') ?? undefined
      : undefined);
  const match = raw && /filename="?([^";]+)"?/i.exec(raw);
  return match?.[1] ?? fallback;
};

export const api = {
  // Auth
  login: async (username: string, password: string): Promise<TokenResponse> => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const { data } = await apiClient.post<TokenResponse>('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return data;
  },

  getMe: async (): Promise<UserRead> => {
    const { data } = await apiClient.get<UserRead>('/auth/me');
    return data;
  },

  // Health
  getHealth: async (): Promise<HealthCheckResponse> => {
    const { data } = await apiClient.get<HealthCheckResponse>('/health');
    return data;
  },


  // Dashboard Overview
  getDashboardOverview: async (): Promise<DashboardOverviewResponse> => {
    const { data } = await apiClient.get<DashboardOverviewResponse>('/dashboard/overview');
    return data;
  },

  // Load Profiles (REAL 319 / 6 selected)
  getLoadProfiles: async (params?: { selected_only?: boolean; limit?: number; offset?: number }): Promise<LoadProfilesListResponse> => {
    const { data } = await apiClient.get<LoadProfilesListResponse>('/load-profiles', { params });
    return data;
  },

  getSelectedLoadProfiles: async (): Promise<LoadProfileRead[]> => {
    const { data } = await apiClient.get<LoadProfileRead[]>('/load-profiles/selected');
    return data;
  },

  getLoadProfileByIdOrName: async (identifier: string): Promise<LoadProfileRead> => {
    const { data } = await apiClient.get<LoadProfileRead>(`/load-profiles/${identifier}`);
    return data;
  },

  // Solar
  getPVConfig: async (estateId?: number): Promise<PVConfigRead> => {
    const { data } = await apiClient.get<PVConfigRead>('/solar/pv-config', { params: estateParam(estateId) });
    return data;
  },

  getSolarGeneration: async (limit = 24, estateId?: number): Promise<SolarGenerationListResponse> => {
    const { data } = await apiClient.get<SolarGenerationListResponse>('/solar/generation', {
      params: { limit, ...estateParam(estateId) },
    });
    return data;
  },

  // Forecasting (DEMO / Prophet)
  getSolarForecast: async (hours = 24, estateId?: number): Promise<SolarForecastResponse> => {
    const { data } = await apiClient.get<SolarForecastResponse>('/forecasting/solar', {
      params: { hours, ...estateParam(estateId) },
    });
    return data;
  },

  getTenantForecast: async (tenantId: number, hours = 24): Promise<TenantForecastResponse> => {
    const { data } = await apiClient.get<TenantForecastResponse>(`/forecasting/tenants/${tenantId}`, { params: { hours } });
    return data;
  },

  // Energy Allocation (DEMO / PuLP)
  getCurrentAllocation: async (): Promise<AllocationCurrentResponse> => {
    const { data } = await apiClient.get<AllocationCurrentResponse>('/allocation/current');
    return data;
  },

  // Battery
  getBatteryConfig: async (estateId?: number): Promise<BatteryConfigRead> => {
    const { data } = await apiClient.get<BatteryConfigRead>('/battery/config', { params: estateParam(estateId) });
    return data;
  },

  getBatteryStatus: async (estateId?: number): Promise<BatteryStatusResponse> => {
    const { data } = await apiClient.get<BatteryStatusResponse>('/battery/status', { params: estateParam(estateId) });
    return data;
  },

  // Billing & Tariffs
  getTariffs: async (): Promise<TariffRead> => {
    const { data } = await apiClient.get<TariffRead>('/billing/tariffs');
    return data;
  },

  getBillingSummary: async (month = '2026-08'): Promise<BillingSummaryResponse> => {
    const { data } = await apiClient.get<BillingSummaryResponse>('/billing/summary', { params: { month } });
    return data;
  },

  // Invoices & PDF downloads
  listInvoices: async (month = '2026-08'): Promise<InvoiceListResponse> => {
    const { data } = await apiClient.get<InvoiceListResponse>('/billing/invoices', { params: { month } });
    return data;
  },

  generateInvoices: async (month = '2026-08'): Promise<InvoiceListResponse> => {
    const { data } = await apiClient.post<InvoiceListResponse>('/billing/invoices/generate', { month });
    return data;
  },

  /** Download a single tenant's invoice PDF (admin passes tenantId; tenants omit it for their own). */
  downloadInvoicePdf: async (month = '2026-08', tenantId?: number): Promise<void> => {
    const response = await apiClient.get<Blob>('/billing/invoices/pdf', {
      params: tenantId !== undefined ? { month, tenant_id: tenantId } : { month },
      responseType: 'blob',
    });
    const filename = filenameFromDisposition(response.headers, `invoice-${month}.pdf`);
    saveBlob(response.data, filename);
  },

  /** Download the consolidated estate-wide billing summary PDF (admin only). */
  downloadEstateSummaryPdf: async (month = '2026-08'): Promise<void> => {
    const response = await apiClient.get<Blob>('/billing/invoices/estate/summary.pdf', {
      params: { month },
      responseType: 'blob',
    });
    const filename = filenameFromDisposition(response.headers, `estate-billing-summary-${month}.pdf`);
    saveBlob(response.data, filename);
  },

  // Analytics (REAL)
  getAnalyticsOverview: async (): Promise<AnalyticsOverviewResponse> => {
    const { data } = await apiClient.get<AnalyticsOverviewResponse>('/analytics/overview');
    return data;
  },

  // ─── Estates / Location ────────────────────────────────
  getEstatePresets: async (): Promise<EstatePreset[]> => {
    const { data } = await apiClient.get<EstatePreset[]>('/estates/presets');
    return data;
  },

  getEstates: async (): Promise<EstateRead[]> => {
    const { data } = await apiClient.get<EstateRead[]>('/estates');
    return data;
  },

  getActiveEstate: async (): Promise<EstateRead> => {
    const { data } = await apiClient.get<EstateRead>('/estates/active');
    return data;
  },

  getEstate: async (estateId: number): Promise<EstateRead> => {
    const { data } = await apiClient.get<EstateRead>(`/estates/${estateId}`);
    return data;
  },

  createEstate: async (payload: EstateCreatePayload): Promise<EstateRead> => {
    const { data } = await apiClient.post<EstateRead>('/estates', payload);
    return data;
  },

  updateEstate: async (estateId: number, payload: EstateUpdatePayload): Promise<EstateRead> => {
    const { data } = await apiClient.put<EstateRead>(`/estates/${estateId}`, payload);
    return data;
  },

  syncEstateWeather: async (
    estateId: number,
    opts: { startDate?: string; endDate?: string; useCache?: boolean } = {},
  ): Promise<EstateSyncWeatherResponse> => {
    const body: Record<string, unknown> = { use_cache: opts.useCache ?? true };
    if (opts.startDate) body.start_date = opts.startDate;
    if (opts.endDate) body.end_date = opts.endDate;
    const { data } = await apiClient.post<EstateSyncWeatherResponse>(
      `/estates/${estateId}/sync-weather`,
      body,
    );
    return data;
  },
};
