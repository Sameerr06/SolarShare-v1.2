import React from 'react';
import { Info } from 'lucide-react';

interface DemoBadgeProps {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  note?: string;
  showIcon?: boolean;
}

export const DemoBadge: React.FC<DemoBadgeProps> = ({
  label = 'SIMULATED',
  size = 'md',
  note,
}) => {
  const sizePadding = {
    sm: 'px-1.5 py-0.5 text-[10px]',
    md: 'px-2 py-0.5 text-[10px]',
    lg: 'px-2.5 py-1 text-xs',
  };

  return (
    <div className="inline-flex items-center gap-1.5 group relative">
      <span
        className={`inline-flex items-center rounded-full uppercase font-bold tracking-wider font-mono ${sizePadding[size]}`}
        style={{ background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.25)', color: '#7c3aed' }}
      >
        {label}
      </span>
      {note && (
        <div className="relative">
          <Info className="w-3.5 h-3.5 cursor-pointer transition-colors duration-200 hover:text-[#a78bfa]" style={{ color: 'var(--text-muted)' }} />
          <div
            className="tooltip-fade absolute right-0 top-full mt-1.5 z-50 w-64 p-2.5 rounded-xl shadow-lg text-xs leading-relaxed"
            style={{ background: 'var(--surface-3)', border: '1px solid rgba(99,102,241,0.2)', color: 'var(--text-secondary)' }}
          >
            <span className="font-semibold block mb-1" style={{ color: '#7c3aed' }}>Simulated Data Notice</span>
            {note}
          </div>
        </div>
      )}
    </div>
  );
};

export const DemoBanner: React.FC<{ note?: string }> = ({ note }) => {
  return (
    <div
      className="w-full rounded-xl p-3 flex items-start gap-3 text-xs"
      style={{ background: 'rgba(139,92,246,0.06)', border: '1px solid rgba(139,92,246,0.15)' }}
    >
      <div
        className="px-2 py-0.5 rounded-full font-mono text-[10px] uppercase font-bold tracking-wider shrink-0"
        style={{ background: 'rgba(139,92,246,0.15)', border: '1px solid rgba(139,92,246,0.25)', color: '#7c3aed' }}
      >
        SIMULATED
      </div>
      <div className="flex-1 min-w-0">
        <p className="leading-normal" style={{ color: 'var(--text-secondary)' }}>
          {note || 'This module currently uses prototype endpoints. In future phases, deep algorithms will replace these simulation endpoints.'}
        </p>
      </div>
    </div>
  );
};

