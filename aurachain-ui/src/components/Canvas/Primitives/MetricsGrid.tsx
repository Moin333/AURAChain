/* eslint-disable @typescript-eslint/no-explicit-any */
// src/components/Canvas/Primitives/MetricsGrid.tsx
import React from 'react';
import { clsx } from 'clsx';

interface MetricsGridProps {
  metrics?: Record<string, any>;
  title?: string;
  variant?: 'default' | 'primary' | 'success' | 'warning';
  columns?: 2 | 3 | 4;
}

const MetricsGrid: React.FC<MetricsGridProps> = ({
  metrics = {},
  title,
  variant = 'default',
  columns = 2
}) => {
  const entries = Object.entries(metrics);

  const variantStyles: Record<string, string> = {
    default: 'bg-slate-50 dark:bg-zinc-900/50 border-slate-200 dark:border-zinc-800',
    primary: 'bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800',
    success: 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800',
    warning: 'bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800'
  };

  const valueStyles: Record<string, string> = {
    default: 'text-slate-900 dark:text-zinc-100',
    primary: 'text-blue-700 dark:text-blue-300',
    success: 'text-green-700 dark:text-green-300',
    warning: 'text-amber-700 dark:text-amber-300'
  };

  if (entries.length === 0) {
    return (
      <div className="p-4 text-sm text-slate-500 dark:text-zinc-500 text-center border border-dashed border-slate-200 dark:border-zinc-700 rounded-xl">
        No metrics available
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {title && (
        <h3 className="text-sm font-semibold text-slate-700 dark:text-zinc-300">
          {title}
        </h3>
      )}

      <div className={clsx(
        'grid gap-3',
        columns === 2 && 'grid-cols-2',
        columns === 3 && 'grid-cols-3',
        columns === 4 && 'grid-cols-4'
      )}>
        {entries.map(([key, value]) => (
          <div
            key={key}
            className={clsx(
              'p-3 rounded-xl border transition-all',
              variantStyles[variant]
            )}
          >
            {/* 🔥 FIX: Label uses break-words + line-clamp */}
            <div className="text-[10px] text-slate-500 dark:text-zinc-500 uppercase tracking-wider mb-1 font-medium break-words leading-tight">
              {key}
            </div>
            {/* 🔥 FIX: Value uses break-all to prevent overflow */}
            <div className={clsx(
              'text-base font-bold break-words leading-snug',
              valueStyles[variant]
            )}>
              {String(value ?? 'N/A')}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default MetricsGrid;