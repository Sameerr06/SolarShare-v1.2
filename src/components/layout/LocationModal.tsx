import React, { useEffect, useState } from 'react';
import {
  X,
  MapPin,
  Globe,
  Sun,
  RefreshCw,
  Check,
  Plus,
  Building2,
  AlertTriangle,
  Info,
} from 'lucide-react';
import { useEstate } from '../../context/EstateContext';
import { EstatePreset } from '../../types/api';

interface LocationModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Bumped by the parent to force every estate-scoped page to refetch. */
  onLocationChanged?: () => void;
}

type Tab = 'presets' | 'custom' | 'existing';

const fmtCoord = (value: number, positive: string, negative: string) =>
  `${Math.abs(value).toFixed(4)}°${value >= 0 ? positive : negative}`;

export const LocationModal: React.FC<LocationModalProps> = ({
  isOpen,
  onClose,
  onLocationChanged,
}) => {
  const {
    activeEstate,
    presets,
    estates,
    loading,
    syncingWeather,
    syncMessage,
    syncWarning,
    updateLocation,
    createLocation,
    selectEstate,
    syncWeather,
  } = useEstate();

  const [activeTab, setActiveTab] = useState<Tab>('presets');
  const [name, setName] = useState('');
  const [latitude, setLatitude] = useState<number>(11.0168);
  const [longitude, setLongitude] = useState<number>(76.9558);
  const [timezone, setTimezone] = useState('Asia/Kolkata');
  const [useCache, setUseCache] = useState(true);
  const [saveAsNew, setSaveAsNew] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Seed the form from the active estate whenever the modal opens.
  useEffect(() => {
    if (isOpen && activeEstate) {
      setName(activeEstate.name);
      setLatitude(activeEstate.latitude);
      setLongitude(activeEstate.longitude);
      setTimezone(activeEstate.timezone || 'Asia/Kolkata');
      setFormError(null);
    }
  }, [isOpen, activeEstate]);

  // ESC to close.
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const coordsChanged =
    !!activeEstate &&
    (Math.abs(latitude - activeEstate.latitude) > 1e-6 ||
      Math.abs(longitude - activeEstate.longitude) > 1e-6);

  const handleSelectPreset = (preset: EstatePreset) => {
    setName(preset.name);
    setLatitude(preset.latitude);
    setLongitude(preset.longitude);
    setTimezone(preset.timezone);
    setFormError(null);
  };

  /** Apply the form: optionally save as a new estate, else update the active one. */
  const handleSave = async () => {
    if (!name.trim()) {
      setFormError('Location name is required');
      return;
    }
    if (latitude < -90 || latitude > 90) {
      setFormError('Latitude must be between -90 and 90');
      return;
    }
    if (longitude < -180 || longitude > 180) {
      setFormError('Longitude must be between -180 and 180');
      return;
    }

    setBusy(true);
    setFormError(null);
    try {
      let targetId: number;
      if (saveAsNew) {
        const created = await createLocation({
          name: name.trim(),
          latitude,
          longitude,
          timezone,
        });
        targetId = created.id;
        await selectEstate(targetId);
      } else {
        if (!activeEstate) throw new Error('No active location to update');
        await updateLocation(activeEstate.id, {
          name: name.trim(),
          latitude,
          longitude,
          timezone,
        });
        targetId = activeEstate.id;
      }

      await syncWeather({ useCache });
      onLocationChanged?.();
      setSaveAsNew(false);
    } catch (e) {
      setFormError((e as Error)?.message || 'Failed to save location');
    } finally {
      setBusy(false);
    }
  };

  /** Pull fresh NASA POWER data for the coordinates already saved. */
  const handleSyncOnly = async () => {
    if (!activeEstate) return;
    setBusy(true);
    setFormError(null);
    try {
      await syncWeather({ useCache });
      onLocationChanged?.();
    } catch (e) {
      setFormError((e as Error)?.message || 'Weather sync failed');
    } finally {
      setBusy(false);
    }
  };

  /** One-click switch to a preset: update coords, fetch its data, refresh pages. */
  const handleApplyPresetDirectly = async (preset: EstatePreset) => {
    if (!activeEstate) return;
    setBusy(true);
    setFormError(null);
    try {
      await updateLocation(activeEstate.id, {
        name: preset.name,
        latitude: preset.latitude,
        longitude: preset.longitude,
        timezone: preset.timezone,
      });
      await syncWeather({ useCache });
      onLocationChanged?.();
    } catch (e) {
      setFormError((e as Error)?.message || 'Failed to switch location');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="overlay-in fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-md"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="panel-in w-full max-w-2xl glass-panel bg-white border-slate-300 shadow-2xl flex flex-col max-h-[88vh] overflow-hidden outline-none"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Estate location and weather telemetry"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-white/90 shrink-0">
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: 'rgba(99,102,241,0.15)' }}
            >
              <MapPin className="w-5 h-5" style={{ color: '#6366f1' }} />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900 tracking-tight">
                Estate Location &amp; Weather Telemetry
              </h3>
              <p className="text-[11px] text-slate-500">
                Change coordinates to fetch NASA POWER data for any location
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="pressable p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          {loading ? (
            <div className="flex items-center gap-3 text-sm text-slate-500 py-8 justify-center">
              <RefreshCw className="w-4 h-4 animate-spin" />
              Loading estate configuration...
            </div>
          ) : (
            <>
              {/* Current active location */}
              {activeEstate && (
                <div
                  className="rounded-xl p-3 flex items-center justify-between gap-3"
                  style={{ background: 'rgba(99,102,241,0.07)', border: '1px solid rgba(99,102,241,0.18)' }}
                >
                  <div className="min-w-0">
                    <p className="text-[10px] uppercase tracking-widest font-semibold text-slate-500">
                      Active location
                    </p>
                    <p className="text-sm font-semibold text-slate-900 truncate">{activeEstate.name}</p>
                    <p className="text-[11px] font-mono" style={{ color: '#6366f1' }}>
                      {fmtCoord(activeEstate.latitude, 'N', 'S')}{' '}
                      {fmtCoord(activeEstate.longitude, 'E', 'W')}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold">
                      Stored data
                    </p>
                    <p className="text-xs font-mono text-slate-800">
                      {activeEstate.weather_observation_count} obs
                    </p>
                    <p className="text-xs font-mono text-slate-800">
                      {activeEstate.solar_generation_estimate_count} est
                    </p>
                  </div>
                </div>
              )}

              {/* Tabs */}
              <div className="flex items-center gap-1 p-1 rounded-xl" style={{ background: 'rgba(15,23,42,0.03)' }}>
                {([
                  { id: 'presets' as Tab, label: 'Presets', icon: Globe },
                  { id: 'custom' as Tab, label: 'Custom', icon: MapPin },
                  { id: 'existing' as Tab, label: 'Saved', icon: Building2 },
                ]).map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`pressable flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium ${
                        isActive ? 'text-slate-900' : 'text-slate-500 hover:text-slate-800'
                      }`}
                      style={
                        isActive
                          ? { background: 'rgba(99,102,241,0.2)', border: '1px solid rgba(99,102,241,0.3)' }
                          : { border: '1px solid transparent' }
                      }
                    >
                      <Icon className="w-3.5 h-3.5" />
                      {tab.label}
                    </button>
                  );
                })}
              </div>

              {/* Presets */}
              {activeTab === 'presets' && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {presets.map((preset) => {
                    const isCurrent =
                      !!activeEstate &&
                      Math.abs(activeEstate.latitude - preset.latitude) < 1e-6 &&
                      Math.abs(activeEstate.longitude - preset.longitude) < 1e-6;
                    return (
                      <div
                        key={preset.id}
                        className={`p-3 rounded-xl space-y-1.5 group transition-all duration-200 hover:-translate-y-0.5 ${
                          isCurrent ? '' : 'cursor-pointer'
                        }`}
                        style={{
                          background: isCurrent ? 'rgba(99,102,241,0.12)' : 'rgba(15,23,42,0.05)',
                          border: `1px solid ${isCurrent ? 'rgba(99,102,241,0.35)' : 'rgba(15,23,42,0.12)'}`,
                        }}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-xs font-semibold text-slate-900 group-hover:text-amber-700 transition-colors">
                            {preset.name}
                          </span>
                          {isCurrent && (
                            <Check className="w-3.5 h-3.5 shrink-0" style={{ color: '#059669' }} />
                          )}
                        </div>
                        <p className="text-[10px] text-slate-500">{preset.region}</p>
                        <p className="text-[10px] font-mono" style={{ color: '#6366f1' }}>
                          {fmtCoord(preset.latitude, 'N', 'S')}{' '}
                          {fmtCoord(preset.longitude, 'E', 'W')}
                        </p>
                        <p className="text-[10px] text-slate-500 leading-snug">{preset.description}</p>
                        <div className="flex items-center gap-1.5 pt-1">
                          <button
                            onClick={() => handleSelectPreset(preset)}
                            className="pressable px-2 py-1 rounded text-[10px] font-medium text-slate-700 hover:text-slate-900"
                            style={{ background: 'rgba(15,23,42,0.05)' }}
                          >
                            Select
                          </button>
                          {!isCurrent && (
                            <button
                              onClick={() => handleApplyPresetDirectly(preset)}
                              disabled={busy}
                              className="pressable px-2 py-1 rounded text-[10px] font-medium text-slate-950 disabled:opacity-50 disabled:pointer-events-none"
                              style={{ background: 'linear-gradient(135deg,#6366f1,#8b5cf6)' }}
                            >
                              Switch &amp; fetch
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Custom coordinates */}
              {activeTab === 'custom' && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1.5">
                      Location name
                    </label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="e.g. My Industrial Estate"
                      className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-900 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-700 mb-1.5">
                        Latitude
                      </label>
                      <input
                        type="number"
                        step="0.0001"
                        min={-90}
                        max={90}
                        value={latitude}
                        onChange={(e) => setLatitude(Number(e.target.value))}
                        className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-900 font-mono focus:outline-none focus:border-indigo-500 transition-colors"
                      />
                      <p className="text-[10px] text-slate-500 mt-1">-90 to 90</p>
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-slate-700 mb-1.5">
                        Longitude
                      </label>
                      <input
                        type="number"
                        step="0.0001"
                        min={-180}
                        max={180}
                        value={longitude}
                        onChange={(e) => setLongitude(Number(e.target.value))}
                        className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-900 font-mono focus:outline-none focus:border-indigo-500 transition-colors"
                      />
                      <p className="text-[10px] text-slate-500 mt-1">-180 to 180</p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-700 mb-1.5">
                      Timezone
                    </label>
                    <select
                      value={timezone}
                      onChange={(e) => setTimezone(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-indigo-500 transition-colors"
                    >
                      {[
                        'Asia/Kolkata',
                        'Asia/Karachi',
                        'Asia/Dhaka',
                        'Asia/Bangkok',
                        'Asia/Singapore',
                        'Asia/Dubai',
                        'Africa/Lagos',
                        'Africa/Nairobi',
                        'Europe/London',
                        'UTC',
                      ].map((tz) => (
                        <option key={tz} value={tz}>
                          {tz}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    <label className="flex items-center gap-2 text-[11px] text-slate-700 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={useCache}
                        onChange={(e) => setUseCache(e.target.checked)}
                        className="accent-indigo-500"
                      />
                      Use cached NASA POWER responses
                    </label>
                    <label className="flex items-center gap-2 text-[11px] text-slate-700 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={saveAsNew}
                        onChange={(e) => setSaveAsNew(e.target.checked)}
                        className="accent-indigo-500"
                      />
                      <Plus className="w-3 h-3" />
                      Save as a new location
                    </label>
                  </div>

                  {coordsChanged && (
                    <div
                      className="flex items-start gap-2 p-2.5 rounded-lg text-[11px]"
                      style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.22)', color: '#d97706' }}
                    >
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                      <span>
                        Coordinates differ from the active location. Saving will discard the
                        stored observations for the previous coordinates and fetch NASA POWER
                        data for the new ones.
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Saved estates */}
              {activeTab === 'existing' && (
                <div className="space-y-2">
                  {estates.length === 0 ? (
                    <p className="text-xs text-slate-500 py-6 text-center">
                      No saved locations yet.
                    </p>
                  ) : (
                    estates.map((est) => {
                      const isActive = activeEstate?.id === est.id;
                      return (
                        <button
                          key={est.id}
                          onClick={async () => {
                            await selectEstate(est.id);
                            onLocationChanged?.();
                          }}
                          className={`pressable w-full text-left p-3 rounded-xl flex items-center justify-between gap-3 ${
                            isActive ? '' : 'hover:bg-slate-100'
                          }`}
                          style={{
                            background: isActive ? 'rgba(99,102,241,0.1)' : 'rgba(15,23,42,0.05)',
                            border: `1px solid ${isActive ? 'rgba(99,102,241,0.3)' : 'rgba(15,23,42,0.12)'}`,
                          }}
                        >
                          <div className="min-w-0">
                            <p className="text-xs font-semibold text-slate-900 truncate">{est.name}</p>
                            <p className="text-[10px] font-mono" style={{ color: '#6366f1' }}>
                              {fmtCoord(est.latitude, 'N', 'S')}{' '}
                              {fmtCoord(est.longitude, 'E', 'W')}
                            </p>
                            <p className="text-[10px] text-slate-500">
                              {est.weather_observation_count} obs &middot;{' '}
                              {est.solar_generation_estimate_count} estimates
                            </p>
                          </div>
                          {isActive && <Check className="w-4 h-4 shrink-0" style={{ color: '#059669' }} />}
                        </button>
                      );
                    })
                  )}
                </div>
              )}

              {/* Feedback */}
              {formError && (
                <div
                  className="flex items-start gap-2 p-2.5 rounded-lg text-[11px]"
                  style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: '#dc2626' }}
                >
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>{formError}</span>
                </div>
              )}

              {syncWarning && !formError && (
                <div
                  className="flex items-start gap-2 p-2.5 rounded-lg text-[11px]"
                  style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.22)', color: '#d97706' }}
                >
                  <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>{syncWarning}</span>
                </div>
              )}

              {syncMessage && !syncWarning && (
                <div
                  className="flex items-start gap-2 p-2.5 rounded-lg text-[11px]"
                  style={{ background: 'rgba(52,211,153,0.08)', border: '1px solid rgba(52,211,153,0.22)', color: '#059669' }}
                >
                  <Check className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>{syncMessage}</span>
                </div>
              )}

              <p className="text-[10px] text-slate-500 leading-relaxed">
                Saving updates the active coordinates and immediately triggers NASA POWER
                hourly solar data ingestion for this location. Solar generation, irradiance
                graphs and PV capacity are re-estimated for the new coordinates.
                <br />
                <span className="text-slate-600">
                  Note: NASA POWER hourly data lags real time by roughly 4 months, so the
                  default sync window is back-dated automatically.
                </span>
              </p>
            </>
          )}
        </div>

        {/* Footer actions */}
        <div
          className="px-6 py-4 border-t border-slate-200 flex items-center justify-between gap-3 shrink-0"
          style={{ background: 'rgba(255,255,255,0.92)' }}
        >
          <button
            onClick={handleSyncOnly}
            disabled={busy || syncingWeather || !activeEstate}
            className="pressable px-3 py-2 rounded-lg text-xs font-medium flex items-center gap-1.5 text-slate-700 disabled:opacity-40 disabled:pointer-events-none"
            style={{ background: 'rgba(15,23,42,0.05)', border: '1px solid rgba(15,23,42,0.08)' }}
            title="Fetch NASA POWER data for the coordinates already saved"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncingWeather ? 'animate-spin' : ''}`} />
            Refresh data
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="pressable px-3.5 py-2 rounded-lg text-xs font-medium text-slate-500 hover:text-slate-900"
            >
              Close
            </button>
            <button
              onClick={handleSave}
              disabled={busy || syncingWeather}
              className="pressable px-4 py-2 rounded-lg text-xs font-semibold text-white flex items-center gap-1.5 disabled:opacity-50 disabled:pointer-events-none"
              style={{
                background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
                boxShadow: '0 4px 16px rgba(99,102,241,0.35)',
              }}
            >
              <Sun className="w-3.5 h-3.5" />
              {busy || syncingWeather ? 'Fetching...' : 'Save & fetch data'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};