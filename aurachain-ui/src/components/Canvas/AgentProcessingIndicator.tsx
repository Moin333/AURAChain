// aurachain-ui/src/components/Canvas/AgentProcessingIndicator.tsx
import React from 'react';
import { InfinityIcon } from 'lucide-react';
import { clsx } from 'clsx';

interface AgentProcessingIndicatorProps {
  agentName: string;
  progress?: number;
  className?: string;
}

const AgentProcessingIndicator: React.FC<AgentProcessingIndicatorProps> = ({ 
  agentName,
  progress = 0,
  className
}) => {
  return (
    <div className={clsx("flex items-center gap-3", className)}>
      {/* Mini Animated Icon */}
      <div className="relative flex-shrink-0">
        {/* Subtle Glow */}
        <div className="absolute inset-0 -m-1 bg-primary-400/20 rounded-full blur-md animate-pulse-slow" />
        
        {/* Icon Container */}
        <div className="relative w-8 h-8 rounded-full bg-gradient-to-tr from-primary-400 to-accent-teal flex items-center justify-center shadow-md">
          <InfinityIcon 
            size={16} 
            className="text-white animate-spin-smooth" 
            strokeWidth={2.5} 
          />
        </div>
      </div>

      {/* Progress Info */}
      <div className="flex-1 min-w-0">
        <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 truncate mb-1">
          {agentName}
        </div>
        
        {/* Progress Bar */}
        {progress > 0 && (
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-primary-500 to-accent-teal rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400 w-8 text-right">
              {progress}%
            </span>
          </div>
        )}
        
        {/* Indeterminate State */}
        {progress === 0 && (
          <div className="h-1 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full w-1/3 bg-gradient-to-r from-primary-500 to-accent-teal rounded-full animate-indeterminate-progress" />
          </div>
        )}
      </div>
    </div>
  );
};

export default AgentProcessingIndicator;