// src/components/Canvas/Primitives/MetricsGrid.tsx
import React from 'react';
import { clsx } from 'clsx';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface MetricsGridProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  metrics: Record<string, any>;
  title?: string;
  variant?: 'default' | 'primary' | 'success' | 'warning';
  columns?: 2 | 3 | 4;
}

const MetricsGrid: React.FC<MetricsGridProps> = ({ 
  metrics, 
  title, 
  variant = 'default',
  columns = 2 
}) => {
  const entries = Object.entries(metrics);

  const variantStyles = {
    default: 'bg-slate-50 dark:bg-zinc-900 border-slate-200 dark:border-zinc-800',
    primary: 'bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800',
    success: 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800',
    warning: 'bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800'
  };

  const detectTrend = (value: string): 'up' | 'down' | 'neutral' => {
    if (value.includes('↑') || value.includes('+')) return 'up';
    if (value.includes('↓') || value.includes('-')) return 'down';
    return 'neutral';
  };

  const TrendIcon = (trend: 'up' | 'down' | 'neutral') => {
    switch (trend) {
      case 'up': return <TrendingUp size={14} className="text-green-500" />;
      case 'down': return <TrendingDown size={14} className="text-red-500" />;
      default: return <Minus size={14} className="text-slate-400" />;
    }
  };

  return (
    <div className="space-y-3">
      {title && (
        <h3 className="text-sm font-semibold text-slate-700 dark:text-zinc-300">
          {title}
        </h3>
      )}
      
      <div className={clsx(
        'grid gap-4',
        columns === 2 && 'grid-cols-2',
        columns === 3 && 'grid-cols-3',
        columns === 4 && 'grid-cols-4'
      )}>
        {entries.map(([key, value]) => {
          const trend = detectTrend(String(value));
          
          return (
            <div 
              key={key} 
              className={clsx(
                'p-4 rounded-xl border transition-all hover:shadow-md',
                variantStyles[variant]
              )}
            >
              <div className="text-xs text-slate-500 dark:text-zinc-500 uppercase tracking-wider mb-1 font-medium">
                {key}
              </div>
              <div className="flex items-center justify-between">
                <div className="text-lg font-bold text-slate-900 dark:text-zinc-100">
                  {String(value)}
                </div>
                {trend !== 'neutral' && TrendIcon(trend)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default MetricsGrid;