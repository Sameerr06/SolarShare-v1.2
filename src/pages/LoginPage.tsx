import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { SunMedium, Lock, User, Key, ShieldCheck, Building2, AlertCircle, ArrowRight } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as any)?.from?.pathname || null;

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) {
      setError('Please enter both username and password');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const loggedUser = await login(username.trim(), password.trim());
      if (from) {
        navigate(from, { replace: true });
      } else if (loggedUser.role === 'ADMIN') {
        navigate('/', { replace: true });
      } else {
        navigate('/portal', { replace: true });
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to authenticate. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const tenantNames = [
    'Textile Manufacturing',
    'Food Processing',
    'Electronics Assembly',
    'Packaging & Plastics',
    'General Engineering',
    'Precision Tooling',
  ];

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 sm:p-6 font-sans"
      style={{ background: 'var(--surface-1)' }}
    >
      {/* Background glow */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse 60% 40% at 50% 0%, rgba(99,102,241,0.12) 0%, transparent 70%)',
        }}
      />

      <div
        className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-0 rounded-2xl relative overflow-hidden shadow-2xl scale-in"
        style={{
          background: 'var(--surface-2)',
          border: '1px solid rgba(99,102,241,0.15)',
          boxShadow: '0 24px 64px rgba(15,23,42,0.12), 0 0 0 1px rgba(99,102,241,0.1)',
        }}
      >
        {/* Left Column — Sign-in form */}
        <div className="p-8 flex flex-col justify-between space-y-6">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div
              className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', boxShadow: '0 4px 20px rgba(99,102,241,0.45)' }}
            >
              <SunMedium className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                Solar<span style={{ color: '#6366f1' }}>Share</span>
              </h1>
              <p className="text-[11px] font-medium tracking-wider" style={{ color: 'var(--text-muted)' }}>
                MSME Energy Hub
              </p>
            </div>
          </div>

          <div>
            <h2 className="text-xl font-bold text-slate-900 mb-1">Welcome back</h2>
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Sign in to access your estate management or tenant portal.
            </p>
          </div>

          {error && (
            <div
              className="p-3 rounded-xl flex items-start gap-2.5 text-xs"
              style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#dc2626' }}
            >
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleLoginSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--text-secondary)' }}>
                User ID / Username
              </label>
              <div className="relative">
                <User className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your user ID"
                  className="w-full pl-9 pr-3 py-2.5 rounded-xl text-sm text-slate-900 placeholder:text-[color:var(--text-muted)] focus:outline-none font-mono transition-all duration-200"
                  style={{
                    background: 'rgba(15,23,42,0.04)',
                    border: '1px solid rgba(15,23,42,0.08)',
                  }}
                  onFocus={(e) => { e.target.style.borderColor = 'rgba(99,102,241,0.5)'; e.target.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.1)'; }}
                  onBlur={(e) => { e.target.style.borderColor = 'rgba(15,23,42,0.08)'; e.target.style.boxShadow = 'none'; }}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold mb-1.5" style={{ color: 'var(--text-secondary)' }}>
                Password
              </label>
              <div className="relative">
                <Key className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  className="w-full pl-9 pr-3 py-2.5 rounded-xl text-sm text-slate-900 placeholder:text-[color:var(--text-muted)] focus:outline-none font-mono transition-all duration-200"
                  style={{
                    background: 'rgba(15,23,42,0.04)',
                    border: '1px solid rgba(15,23,42,0.08)',
                  }}
                  onFocus={(e) => { e.target.style.borderColor = 'rgba(99,102,241,0.5)'; e.target.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.1)'; }}
                  onBlur={(e) => { e.target.style.borderColor = 'rgba(15,23,42,0.08)'; e.target.style.boxShadow = 'none'; }}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="pressable w-full py-2.5 px-4 font-semibold rounded-xl text-sm flex items-center justify-center gap-2 disabled:opacity-50 disabled:pointer-events-none hover:brightness-110"
              style={{
                background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                color: 'white',
                boxShadow: loading ? 'none' : '0 4px 20px rgba(99,102,241,0.4)',
              }}
            >
              {loading ? 'Authenticating...' : 'Sign In'}
              {!loading && <ArrowRight className="w-4 h-4" />}
            </button>
          </form>

          <div className="flex items-center gap-1.5 text-[11px]" style={{ color: 'var(--text-muted)' }}>
            <Lock className="w-3.5 h-3.5" />
            <span>Encrypted JWT · Strict Tenant Isolation</span>
          </div>
        </div>

        {/* Right Column — Tenant Directory */}
        <div
          className="p-6 flex flex-col justify-between space-y-4"
          style={{ background: 'rgba(15,23,42,0.02)', borderLeft: '1px solid rgba(99,102,241,0.1)' }}
        >
          <div>
            <div className="flex items-center gap-2 pb-3 mb-1" style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
              <Building2 className="w-4 h-4" style={{ color: '#6366f1' }} />
              <h3 className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--text-primary)' }}>
                Estate Tenants
              </h3>
            </div>
            <p className="text-[11px] mt-2 mb-4" style={{ color: 'var(--text-muted)' }}>
              Coimbatore Industrial Estate — registered units:
            </p>

            {/* Admin */}
            <div className="mb-4">
              <div className="text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
                Administrator
              </div>
              <div
                className="w-full p-3 rounded-xl flex items-center gap-2.5"
                style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.15)' }}
              >
                <div className="p-1.5 rounded-lg" style={{ background: 'rgba(99,102,241,0.2)' }}>
                  <ShieldCheck className="w-4 h-4" style={{ color: '#6366f1' }} />
                </div>
                <div className="text-xs font-semibold text-slate-900">Estate Administrator</div>
              </div>
            </div>

            {/* Tenants */}
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
                Industrial Tenants
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {tenantNames.map((name) => (
                  <div
                    key={name}
                    className="p-2.5 rounded-xl flex items-center gap-2"
                    style={{ background: 'rgba(15,23,42,0.03)', border: '1px solid rgba(15,23,42,0.06)' }}
                  >
                    <Building2 className="w-3.5 h-3.5 shrink-0" style={{ color: '#059669' }} />
                    <div className="text-[11px] font-semibold text-slate-900 truncate">{name}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div
            className="p-3 rounded-xl text-[10px] leading-relaxed"
            style={{ background: 'rgba(99,102,241,0.05)', border: '1px solid rgba(99,102,241,0.12)', color: 'var(--text-muted)' }}
          >
            <span className="font-semibold text-slate-900">Note:</span> Each tenant is strictly isolated to their own load shapes, forecasts, and billing summaries.
          </div>
        </div>
      </div>
    </div>
  );
};
