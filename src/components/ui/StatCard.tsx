import React from 'react';
import { LucideIcon } from 'lucide-react';
import { DemoBadge } from './DemoBadge';
import { useCountUp } from '../../hooks/useCountUp';

interface StatCardProps {
  title: string;
  value: string | number;
  unit?: string;
  subtext?: string;
  icon: LucideIcon;
  iconColor?: string;
  iconBg?: string;
  trend?: {
    value: string;
    isPositive?: boolean;
  };
  isDemo?: boolean;
  demoNote?: string;
  accentColor?: string;
}

const AnimatedNumber: React.FC<{ value: number }> = ({ value }) => {
  const animated = useCountUp(value);
  return <span className="tabular-nums">{Math.round(animated).toLocaleString()}</span>;
};

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  unit,
  subtext,
  icon: Icon,
  iconColor = '#6366f1',
  iconBg,
  trend,
  isDemo = false,
  demoNote,
  accentColor,
}) => {
  const bgStyle = iconBg || 'rgba(99,102,241,0.12)';

  return (
    <div className="stat-card group">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-center gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
              {title}
            </p>
            {isDemo && <DemoBadge size="sm" note={demoNote} />}
          </div>
          <div className="flex items-baseline gap-1.5 pt-1">
<span
              className="text-2xl font-bold"
              style={{ color: accentColor || 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}
            >
              {typeof value === 'number' ? <AnimatedNumber value={value} /> : value}
            </span>
            {unit && (
              <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                {unit}
              </span>
            )}
          </div>
        </div>
<div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ml-3 transition-transform duration-200 group-hover:scale-105"
          style={{ background: bgStyle }}
        >
          <Icon className="w-5 h-5" style={{ color: iconColor }} />
        </div>
      </div>

      {(subtext || trend) && (
        <div
          className="mt-3 pt-3 flex items-center justify-between"
          style={{ borderTop: '1px solid rgba(15,23,42,0.05)' }}
        >
          {subtext && (
            <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
              {subtext}
            </span>
          )}
          {trend && (
            <span
              className="text-[11px] font-semibold px-2 py-0.5 rounded-full"
              style={
                trend.isPositive
                  ? { background: 'rgba(52,211,153,0.1)', color: '#059669', border: '1px solid rgba(52,211,153,0.2)' }
                  : { background: 'rgba(248,113,113,0.1)', color: '#dc2626', border: '1px solid rgba(248,113,113,0.2)' }
              }
            >
              {trend.isPositive ? '↑' : '↓'} {trend.value}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
