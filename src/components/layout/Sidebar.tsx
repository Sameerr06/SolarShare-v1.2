import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  Activity,
  Sun,
  TrendingUp,
  Share2,
  BatteryCharging,
  Receipt,
  BarChart3,
  SunMedium,
  Building2,
  LogOut,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface SidebarProps {
  collapsed: boolean;
  setCollapsed: (val: boolean) => void;
}

const adminNavigationItems = [
  { name: 'Overview',          path: '/',             icon: LayoutDashboard },
  { name: 'Tenant Dashboard',  path: '/tenants',      icon: Users           },
  { name: 'Load Profiles',     path: '/load-profiles',icon: Activity        },
  { name: 'Solar Generation',  path: '/solar',        icon: Sun             },
  { name: 'Forecasting',       path: '/forecasting',  icon: TrendingUp      },
  { name: 'Energy Allocation', path: '/allocation',   icon: Share2          },
  { name: 'Battery',           path: '/battery',      icon: BatteryCharging },
  { name: 'Billing & Tariffs', path: '/billing',      icon: Receipt         },
  { name: 'Analytics',         path: '/analytics',    icon: BarChart3       },
];

const tenantNavigationItems = [
  { name: 'Tenant Self-Service Portal', path: '/portal', icon: Building2 },
];

export const Sidebar: React.FC<SidebarProps> = ({ collapsed }) => {
  const { user, isTenant, logout } = useAuth();
  const navigationItems = isTenant ? tenantNavigationItems : adminNavigationItems;

  return (
    <aside
      style={{ background: 'var(--sidebar-bg)', borderRight: '1px solid rgba(99,102,241,0.1)' }}
      className={`fixed left-0 top-0 bottom-0 z-40 flex flex-col transition-all duration-300 ${
        collapsed ? 'w-[70px]' : 'w-[240px]'
      }`}
    >
      {/* Brand */}
      <div className="h-16 px-4 flex items-center shrink-0" style={{ borderBottom: '1px solid rgba(99,102,241,0.1)' }}>
        <div className="flex items-center gap-3 overflow-hidden min-w-0">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', boxShadow: '0 4px 16px rgba(99,102,241,0.4)' }}
          >
            <SunMedium className="w-5 h-5 text-white" />
          </div>
          {!collapsed && (
            <div className="flex flex-col min-w-0">
              <span className="font-bold text-[15px] text-slate-900 tracking-tight leading-tight">
                Solar<span style={{ color: '#6366f1' }}>Share</span>
              </span>
              <span className="text-[10px] font-medium tracking-widest uppercase" style={{ color: 'var(--text-muted)' }}>
                {isTenant ? 'Tenant Portal' : 'Energy Hub'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <div className="flex-1 py-4 overflow-y-auto overflow-x-hidden">
        {!collapsed && (
          <div className="px-4 mb-2">
            <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
              {isTenant ? 'Self-Service' : 'Main Menu'}
            </span>
          </div>
        )}
        <div className={`space-y-0.5 stagger-children ${collapsed ? 'px-2' : 'px-3'}`}>
          {navigationItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
className={({ isActive }) =>
                  `sidebar-nav-item nav-item-glow group relative flex items-center gap-3 rounded-xl transition-all duration-200 ${
                    collapsed ? 'justify-center px-0 py-3' : 'px-3 py-2.5'
                  } ${isActive ? 'nav-active-pill' : 'hover:bg-slate-100'}`
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      aria-hidden="true"
                      className="absolute left-0 top-1/2 -translate-y-1/2 rounded-r-full"
                      style={{
                        width: 3,
                        height: isActive ? '60%' : 0,
                        background: 'linear-gradient(180deg, #818cf8, #a78bfa)',
                        boxShadow: '0 0 8px rgba(129,140,248,0.7)',
                        transition: 'height 300ms cubic-bezier(0.22,1,0.36,1)',
                      }}
                    />
                    <Icon
                      className={`icon-pop shrink-0 ${collapsed ? 'w-5 h-5' : 'w-4 h-4'}`}
                      style={{ color: isActive ? '#6366f1' : 'var(--text-secondary)' }}
                    />
                    {!collapsed && (
                      <span
                        className="text-[13px] font-medium truncate"
                        style={{ color: isActive ? '#4f46e5' : 'var(--text-secondary)' }}
                      >
                        {item.name}
                      </span>
                    )}
                    {!collapsed && isActive && (
                      <span
                        className="ml-auto w-1.5 h-1.5 rounded-full shrink-0"
                        style={{ background: '#6366f1', boxShadow: '0 0 6px #6366f1' }}
                      />
                    )}
                    {collapsed && <span className="sidebar-tooltip">{item.name}</span>}
                  </>
                )}
              </NavLink>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="shrink-0 p-3" style={{ borderTop: '1px solid rgba(99,102,241,0.1)' }}>
        {collapsed ? (
          <div className="sidebar-nav-item relative flex justify-center">
            <button
              onClick={logout}
className="pressable w-9 h-9 rounded-xl flex items-center justify-center hover:bg-red-500/15"
              style={{ color: '#dc2626' }}
              title="Logout"
              aria-label="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
            <span className="sidebar-tooltip">Logout</span>
          </div>
        ) : (
          <div className="rounded-xl p-3 space-y-3" style={{ background: 'rgba(15,23,42,0.03)', border: '1px solid rgba(99,102,241,0.12)' }}>
            {isTenant && user ? (
              <>
                <div className="flex items-center gap-2.5">
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0"
                    style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: 'white' }}
                  >
                    {(user.tenant_name || user.email || 'T').charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[12px] font-semibold text-slate-900 truncate">{user.tenant_name || user.email}</div>
                    <div className="text-[10px] font-mono" style={{ color: '#6366f1' }}>ID: {user.source_client_series_id || 'T258'}</div>
                  </div>
                </div>
                <button
                  onClick={logout}
className="pressable w-full py-1.5 px-3 rounded-lg text-[11px] font-medium flex items-center justify-center gap-1.5 hover:bg-red-500/15"
                  style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.18)', color: '#dc2626' }}
                >
                  <LogOut className="w-3 h-3" />Sign Out
                </button>
              </>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
<div className="relative w-2 h-2">
                        <span className="absolute inset-0 rounded-full ping-slow" style={{ background: 'rgba(52,211,153,0.4)' }} />
                        <span className="relative block w-2 h-2 rounded-full dot-breathe" style={{ background: '#059669' }} />
                      </div>
                    <span className="text-[11px] font-medium" style={{ color: '#059669' }}>Online</span>
                  </div>
                  <span className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>v0.2.0</span>
                </div>
                <div className="grid grid-cols-2 gap-2 pt-2" style={{ borderTop: '1px solid rgba(15,23,42,0.05)' }}>
                  <div className="text-center">
                    <div className="text-[14px] font-bold text-slate-900">319</div>
                    <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Profiles</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[14px] font-bold text-slate-900">6</div>
                    <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Tenants</div>
                  </div>
                </div>
                <button
                  onClick={logout}
className="pressable w-full py-1.5 px-3 rounded-lg text-[11px] font-medium flex items-center justify-center gap-1.5 hover:bg-red-500/15"
                  style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.18)', color: '#dc2626' }}
                >
                  <LogOut className="w-3 h-3" />Sign Out
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
