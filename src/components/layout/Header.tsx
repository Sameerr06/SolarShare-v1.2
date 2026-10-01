import React, { useEffect, useState } from 'react';
import {
  Menu,
  RotateCw,
  MapPin,
  ShieldCheck,
  Building2,
  LogOut,
  Bell,
  Search,
} from 'lucide-react';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useEstate } from '../../context/EstateContext';

interface HeaderProps {
  collapsed: boolean;
  setCollapsed: (val: boolean) => void;
  onRefresh?: () => void;
  onOpenLocation?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  collapsed,
  setCollapsed,
  onRefresh,
  onOpenLocation,
}) => {
  const { user, logout, isTenant } = useAuth();
  const { activeEstate } = useEstate();
  const [healthStatus, setHealthStatus] = useState<'healthy' | 'error' | 'checking'>('checking');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const checkBackendHealth = async () => {
    try {
      const res = await api.getHealth();
      if (res.status === 'ok') {
        setHealthStatus('healthy');
      } else {
        setHealthStatus('error');
      }
    } catch {
      setHealthStatus('error');
    }
  };

  useEffect(() => {
    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleRefreshClick = () => {
    setIsRefreshing(true);
    checkBackendHealth();
    if (onRefresh) onRefresh();
    setTimeout(() => setIsRefreshing(false), 600);
  };

  const healthColor =
    healthStatus === 'healthy' ? '#059669' :
    healthStatus === 'checking' ? '#d97706' : '#dc2626';

  const healthLabel =
    healthStatus === 'healthy' ? 'Connected' :
    healthStatus === 'checking' ? 'Checking' : 'Offline';

  return (
    <header
      className={`fixed top-0 right-0 z-30 h-16 transition-all duration-300 flex items-center justify-between px-5`}
      style={{
        left: collapsed ? '70px' : '240px',
        background: 'rgba(255,255,255,0.88)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(99,102,241,0.1)',
      }}
    >
      {/* Left */}
      <div className="flex items-center gap-3">
        {/* Sidebar toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
className="pressable w-8 h-8 rounded-lg flex items-center justify-center hover:bg-slate-100"
          style={{ color: 'var(--text-secondary)', border: '1px solid rgba(15,23,42,0.06)' }}
          title="Toggle Navigation Sidebar"
          aria-label="Toggle navigation sidebar"
        >
          <Menu className="w-4 h-4" />
        </button>

{/* Location badge — click to change coordinates (admin only) */}
        <button
          onClick={onOpenLocation}
          disabled={!onOpenLocation || isTenant}
          className={`group hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all duration-200 ${
            onOpenLocation && !isTenant
              ? 'cursor-pointer hover:brightness-125 hover:-translate-y-px'
              : 'cursor-default'
          }`}
          style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.15)' }}
          title={isTenant ? 'Estate location is managed by the administrator' : 'Change estate location and fetch data for those coordinates'}
        >
          <MapPin className="w-3.5 h-3.5 shrink-0" style={{ color: '#6366f1' }} />
          <span className="text-[12px] font-medium text-slate-900">
            {activeEstate?.name ?? 'Coimbatore MSME Estate'}
          </span>
          <span className="text-[10px] font-mono hidden md:inline" style={{ color: 'var(--text-muted)' }}>
            {activeEstate
              ? `${activeEstate.latitude.toFixed(4)}°N ${activeEstate.longitude.toFixed(4)}°E`
              : '11.0168°N 76.9558°E'}
          </span>
          {activeEstate && activeEstate.weather_observation_count > 0 && (
            <span
              className="text-[9px] font-mono px-1 py-0.5 rounded hidden lg:inline"
              style={{ background: 'rgba(52,211,153,0.12)', color: '#059669' }}
              title={`${activeEstate.weather_observation_count} observations stored for these coordinates`}
            >
              {activeEstate.weather_observation_count} obs
            </span>
          )}
        </button>

        {/* Tenant badge */}
        {isTenant && user?.tenant_name && (
          <div
            className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-lg"
            style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.15)' }}
          >
            <Building2 className="w-3.5 h-3.5 shrink-0" style={{ color: '#6366f1' }} />
            <span className="text-[12px] font-semibold text-slate-900 truncate max-w-[200px]">{user.tenant_name}</span>
            {user.source_client_series_id && (
              <span
                className="text-[10px] font-mono px-1.5 py-0.5 rounded"
                style={{ background: 'rgba(99,102,241,0.15)', color: '#6366f1' }}
              >
                {user.source_client_series_id}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Right */}
      <div className="flex items-center gap-2">
{/* API Status */}
        <div
          className="group flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors duration-200 hover:brightness-125 cursor-default"
          style={{ background: 'rgba(15,23,42,0.04)', border: '1px solid rgba(15,23,42,0.06)' }}
          title={`Backend API status: ${healthLabel}`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full transition-all duration-500 ${healthStatus === 'healthy' ? 'dot-breathe' : 'skeleton-pulse'}`}
            style={{ background: healthColor, transition: 'background 400ms ease' }}
          />
          <span className="text-[11px] font-medium hidden md:inline transition-colors duration-300" style={{ color: healthColor }}>
            API: {healthLabel}
          </span>
        </div>

        {/* Refresh */}
        <button
          onClick={handleRefreshClick}
          className="pressable w-8 h-8 rounded-lg flex items-center justify-center hover:bg-slate-100"
          style={{
            color: isRefreshing ? '#6366f1' : 'var(--text-secondary)',
            border: '1px solid rgba(15,23,42,0.06)',
          }}
          title="Refresh All Telemetry"
          aria-label="Refresh all telemetry"
        >
          <RotateCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
        </button>

        {/* Notifications (decorative) */}
        <button
          className="pressable relative w-8 h-8 rounded-lg flex items-center justify-center hover:bg-slate-100"
          style={{ color: 'var(--text-secondary)', border: '1px solid rgba(15,23,42,0.06)' }}
          title="Notifications"
          aria-label="Notifications"
        >
          <Bell className="w-3.5 h-3.5" />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full skeleton-pulse" style={{ background: '#6366f1' }} />
        </button>

        {/* Role badge */}
        <div
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg"
          style={{ background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)' }}
        >
          <ShieldCheck className="w-3.5 h-3.5" style={{ color: '#6366f1' }} />
          <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: '#4f46e5' }}>
            {user?.role || 'Guest'}
          </span>
        </div>

        {/* Logout */}
        <button
          onClick={logout}
className="pressable hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium hover:brightness-125"
          style={{
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.18)',
            color: '#dc2626',
          }}
          title="Sign Out"
          aria-label="Sign out"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span className="hidden md:inline">Logout</span>
        </button>
      </div>
    </header>
  );
};
