// src/components/Canvas/Primitives/AlertBanner.tsx
import React from 'react';
import { clsx } from 'clsx';
import { AlertTriangle, Info, CheckCircle2, XCircle } from 'lucide-react';

interface AlertBannerProps {
  type: 'info' | 'success' | 'warning' | 'error';
  title?: string;
  message: string;
}

const AlertBanner: React.FC<AlertBannerProps> = ({ type, title, message }) => {
  const config = {
    info: {
      icon: Info,
      bg: 'bg-blue-50 dark:bg-blue-900/10',
      border: 'border-blue-200 dark:border-blue-800',
      iconColor: 'text-blue-600 dark:text-blue-400',
      textColor: 'text-blue-800 dark:text-blue-300'
    },
    success: {
      icon: CheckCircle2,
      bg: 'bg-green-50 dark:bg-green-900/10',
      border: 'border-green-200 dark:border-green-800',
      iconColor: 'text-green-600 dark:text-green-400',
      textColor: 'text-green-800 dark:text-green-300'
    },
    warning: {
      icon: AlertTriangle,
      bg: 'bg-amber-50 dark:bg-amber-900/10',
      border: 'border-amber-200 dark:border-amber-800',
      iconColor: 'text-amber-600 dark:text-amber-400',
      textColor: 'text-amber-800 dark:text-amber-300'
    },
    error: {
      icon: XCircle,
      bg: 'bg-red-50 dark:bg-red-900/10',
      border: 'border-red-200 dark:border-red-800',
      iconColor: 'text-red-600 dark:text-red-400',
      textColor: 'text-red-800 dark:text-red-300'
    }
  };

  const { icon: Icon, bg, border, iconColor, textColor } = config[type];

  return (
    <div className={clsx(
      'p-4 rounded-xl border flex items-start gap-3',
      bg,
      border
    )}>
      <Icon className={clsx('flex-shrink-0 mt-0.5', iconColor)} size={20} />
      <div className="flex-1">
        {title && (
          <h4 className={clsx('font-semibold text-sm mb-1', textColor)}>
            {title}
          </h4>
        )}
        <p className={clsx('text-sm', textColor)}>
          {message}
        </p>
      </div>
    </div>
  );
};

export default AlertBanner;