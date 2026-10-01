import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  EstateCreatePayload,
  EstatePreset,
  EstateRead,
  EstateSyncWeatherResponse,
  EstateUpdatePayload,
} from '../types/api';
import { api, clearActiveEstateId, getActiveEstateId, setActiveEstateId } from '../api/client';

interface EstateContextType {
  activeEstate: EstateRead | null;
  estates: EstateRead[];
  presets: EstatePreset[];
  loading: boolean;
  syncingWeather: boolean;
  syncMessage: string | null;
  syncWarning: string | null;
  error: string | null;

  selectEstate: (estateId: number) => Promise<void>;
  updateLocation: (estateId: number, payload: EstateUpdatePayload) => Promise<EstateRead>;
  createLocation: (payload: EstateCreatePayload) => Promise<EstateRead>;
  syncWeather: (opts?: { startDate?: string; endDate?: string; useCache?: boolean }) => Promise<EstateSyncWeatherResponse>;
  refresh: () => Promise<void>;
}

const EstateContext = createContext<EstateContextType | undefined>(undefined);

const errMessage = (e: unknown, fallback: string): string =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
  (e as Error)?.message ||
  fallback;

export const EstateProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeEstate, setActiveEstate] = useState<EstateRead | null>(null);
  const [estates, setEstates] = useState<EstateRead[]>([]);
  const [presets, setPresets] = useState<EstatePreset[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncingWeather, setSyncingWeather] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [syncWarning, setSyncWarning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadEstates = useCallback(async () => {
    const [list, presetList] = await Promise.all([api.getEstates(), api.getEstatePresets()]);
    setEstates(list);
    setPresets(presetList);
    return list;
  }, []);

  // Initial load: presets are public; estate list requires auth.
  useEffect(() => {
    const init = async () => {
      try {
        const presetList = await api.getEstatePresets();
        setPresets(presetList);

        const token = localStorage.getItem('solarshare_token');
        if (!token) {
          setLoading(false);
          return;
        }

        const list = await api.getEstates();
        setEstates(list);

        // Honour a previously selected estate, else fall back to the backend's
        // notion of "active" (lowest id), else the first estate available.
        const storedId = getActiveEstateId();
        const chosen =
          (storedId !== undefined ? list.find((e) => e.id === storedId) : undefined) ??
          (await api.getActiveEstate().catch(() => undefined)) ??
          list[0];

        if (chosen) {
          setActiveEstateId(chosen.id);
          setActiveEstate(chosen);
        }
      } catch (e) {
        setError(errMessage(e, 'Failed to load estate configuration'));
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const refresh = useCallback(async () => {
    try {
      const list = await loadEstates();
      if (activeEstate) {
        const fresh = list.find((e) => e.id === activeEstate.id);
        setActiveEstate(fresh ?? null);
      }
    } catch (e) {
      setError(errMessage(e, 'Failed to refresh estates'));
    }
  }, [loadEstates, activeEstate]);

  const selectEstate = useCallback(async (estateId: number) => {
    setActiveEstateId(estateId);
    const fresh = await api.getEstate(estateId);
    setActiveEstate(fresh);
    setEstates((prev) => prev.map((e) => (e.id === estateId ? fresh : e)));
  }, []);

  const updateLocation = useCallback(
    async (estateId: number, payload: EstateUpdatePayload): Promise<EstateRead> => {
      setSyncMessage(null);
      setSyncWarning(null);
      try {
        const updated = await api.updateEstate(estateId, payload);
        setEstates((prev) => prev.map((e) => (e.id === estateId ? updated : e)));
        if (activeEstate?.id === estateId) {
          setActiveEstate(updated);
        }
        return updated;
      } catch (e) {
        const message = errMessage(e, 'Failed to update location');
        setSyncWarning(message);
        throw new Error(message);
      }
    },
    [activeEstate],
  );

  const createLocation = useCallback(async (payload: EstateCreatePayload): Promise<EstateRead> => {
    setSyncMessage(null);
    setSyncWarning(null);
    try {
      const created = await api.createEstate(payload);
      setEstates((prev) => [...prev, created]);
      return created;
    } catch (e) {
      const message = errMessage(e, 'Failed to create location');
      setSyncWarning(message);
      throw new Error(message);
    }
  }, []);

  const syncWeather = useCallback(
    async (opts: { startDate?: string; endDate?: string; useCache?: boolean } = {}) => {
      if (!activeEstate) {
        throw new Error('No active estate selected');
      }
      setSyncingWeather(true);
      setSyncMessage(null);
      setSyncWarning(null);
      try {
        const result = await api.syncEstateWeather(activeEstate.id, opts);
        setSyncMessage(result.message);
        setSyncWarning(result.warning ?? null);
        // Reflect the refreshed observation/estimate counts on the active estate.
        const fresh = await api.getEstate(activeEstate.id);
        setActiveEstate(fresh);
        setEstates((prev) => prev.map((e) => (e.id === fresh.id ? fresh : e)));
        return result;
      } catch (e) {
        const message = errMessage(e, 'Weather sync failed');
        setSyncWarning(message);
        throw new Error(message);
      } finally {
        setSyncingWeather(false);
      }
    },
    [activeEstate],
  );

  const signOutReset = useCallback(() => {
    clearActiveEstateId();
  }, []);

  const value = useMemo<EstateContextType>(
    () => ({
      activeEstate,
      estates,
      presets,
      loading,
      syncingWeather,
      syncMessage,
      syncWarning,
      error,
      selectEstate,
      updateLocation,
      createLocation,
      syncWeather,
      refresh,
    }),
    [
      activeEstate,
      estates,
      presets,
      loading,
      syncingWeather,
      syncMessage,
      syncWarning,
      error,
      selectEstate,
      updateLocation,
      createLocation,
      syncWeather,
      refresh,
    ],
  );

  // Keep the stored estate id in step when the provider unmounts on logout.
  useEffect(() => {
    if (!localStorage.getItem('solarshare_token')) signOutReset();
  }, [signOutReset]);

  return <EstateContext.Provider value={value}>{children}</EstateContext.Provider>;
};

export const useEstate = (): EstateContextType => {
  const context = useContext(EstateContext);
  if (!context) {
    throw new Error('useEstate must be used within an EstateProvider');
  }
  return context;
};