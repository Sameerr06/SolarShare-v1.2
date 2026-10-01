import React from 'react';
import { Loader2, AlertTriangle, Inbox, RefreshCw } from 'lucide-react';

export const LoadingState: React.FC<{ message?: string }> = ({
  message = 'Fetching SolarShare telemetry data...',
}) => {
  return (
    <div className="fade-in glass-panel p-12 flex flex-col items-center justify-center min-h-[300px] text-center space-y-4">
      <div className="relative flex items-center justify-center">
        <div
          className="w-12 h-12 rounded-full border-2 animate-spin"
          style={{ borderColor: 'rgba(99,102,241,0.2)', borderTopColor: '#6366f1' }}
        />
        <Loader2 className="w-5 h-5 absolute animate-pulse" style={{ color: '#6366f1' }} />
      </div>
      <div>
        <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{message}</p>
        <div className="flex items-center justify-center gap-1.5 mt-2">
          <span className="w-1 h-1 rounded-full skeleton-pulse" style={{ background: 'var(--text-muted)' }} />
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Connecting to FastAPI Backend...
          </span>
          <span className="w-1 h-1 rounded-full skeleton-pulse" style={{ background: 'var(--text-muted)', animationDelay: '0.3s' }} />
        </div>
      </div>
    </div>
  );
};

export const ErrorState: React.FC<{
  title?: string;
  message?: string;
  onRetry?: () => void;
}> = ({
  title = 'Failed to load telemetry data',
  message = 'An unexpected error occurred while communicating with the backend.',
  onRetry,
}) => {
  return (
    <div
      className="fade-in glass-panel p-8 flex flex-col items-center justify-center text-center space-y-4 min-h-[250px]"
      style={{ borderColor: 'rgba(239,68,68,0.2)', background: 'rgba(239,68,68,0.04)' }}
    >
      <div className="p-3 rounded-full" style={{ background: 'rgba(239,68,68,0.15)' }}>
        <AlertTriangle className="w-7 h-7" style={{ color: '#dc2626' }} />
      </div>
      <div className="max-w-md space-y-1">
        <h3 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>{title}</h3>
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="pressable inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold hover:brightness-125"
          style={{
            background: 'rgba(239,68,68,0.12)',
            border: '1px solid rgba(239,68,68,0.25)',
            color: '#dc2626',
          }}
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry Request
        </button>
      )}
    </div>
  );
};

export const EmptyState: React.FC<{
  title?: string;
  message?: string;
  icon?: React.ElementType;
}> = ({
  title = 'No records found',
  message = 'No data is available for the selected criteria.',
  icon: Icon = Inbox,
}) => {
  return (
    <div className="fade-in glass-panel p-10 flex flex-col items-center justify-center text-center space-y-3 min-h-[250px]">
      <div className="p-3 rounded-full" style={{ background: 'rgba(99,102,241,0.1)' }}>
        <Icon className="w-7 h-7" style={{ color: '#6366f1' }} />
      </div>
      <div className="space-y-1 max-w-sm">
        <h4 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{title}</h4>
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{message}</p>
      </div>
    </div>
  );
};