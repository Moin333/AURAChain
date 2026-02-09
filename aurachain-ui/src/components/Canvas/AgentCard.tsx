// aurachain-ui/src/components/Canvas/AgentCard.tsx
import React from 'react';
import { clsx } from 'clsx';
import { 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  Database, 
  TrendingUp, 
  BrainCircuit, 
  Loader2,
  BarChart3,
  ShoppingCart,
  Bell,
  Target
} from 'lucide-react';
import { useUIStore, normalizeAgentName } from '../../store/uiStore';

export interface Agent {
  id: string;
  name: string;
  type: 'harvester' | 'analyst' | 'forecaster' | 'visualizer' | 'optimizer' | 'order_manager' | 'notifier';
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number;
  summary?: string;
}

interface AgentCardProps {
  agent: Agent;
}

// COMPLETE AGENT CONFIGURATION
const AGENT_CONFIG: Record<string, {
  icon: React.ElementType;
  color: string;
  displayName: string;
}> = {
  'data_harvester': {
    icon: Database,
    color: 'blue',
    displayName: 'Data Harvester'
  },
  'dataharvester': {
    icon: Database,
    color: 'blue',
    displayName: 'Data Harvester'
  },
  'trend_analyst': {
    icon: TrendingUp,
    color: 'purple',
    displayName: 'Trend Analyst'
  },
  'trendanalyst': {
    icon: TrendingUp,
    color: 'purple',
    displayName: 'Trend Analyst'
  },
  'visualizer': {
    icon: BarChart3,
    color: 'emerald',
    displayName: 'Visualizer'
  },
  'forecaster': {
    icon: BrainCircuit,
    color: 'amber',
    displayName: 'Forecaster'
  },
  'mcts_optimizer': {
    icon: Target,
    color: 'rose',
    displayName: 'MCTS Optimizer'
  },
  'mctsoptimizer': {
    icon: Target,
    color: 'rose',
    displayName: 'MCTS Optimizer'
  },
  'order_manager': {
    icon: ShoppingCart,
    color: 'indigo',
    displayName: 'Order Manager'
  },
  'ordermanager': {
    icon: ShoppingCart,
    color: 'indigo',
    displayName: 'Order Manager'
  },
  'notifier': {
    icon: Bell,
    color: 'cyan',
    displayName: 'Notifier'
  }
};

// Color theme mapping
const COLOR_THEMES = {
  blue: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/20',
    text: 'text-blue-600 dark:text-blue-400',
    activeBg: 'bg-blue-50 dark:bg-blue-900/20',
    progress: 'from-blue-500 to-blue-600'
  },
  purple: {
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/20',
    text: 'text-purple-600 dark:text-purple-400',
    activeBg: 'bg-purple-50 dark:bg-purple-900/20',
    progress: 'from-purple-500 to-purple-600'
  },
  emerald: {
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/20',
    text: 'text-emerald-600 dark:text-emerald-400',
    activeBg: 'bg-emerald-50 dark:bg-emerald-900/20',
    progress: 'from-emerald-500 to-emerald-600'
  },
  amber: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/20',
    text: 'text-amber-600 dark:text-amber-400',
    activeBg: 'bg-amber-50 dark:bg-amber-900/20',
    progress: 'from-amber-500 to-amber-600'
  },
  rose: {
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/20',
    text: 'text-rose-600 dark:text-rose-400',
    activeBg: 'bg-rose-50 dark:bg-rose-900/20',
    progress: 'from-rose-500 to-rose-600'
  },
  indigo: {
    bg: 'bg-indigo-500/10',
    border: 'border-indigo-500/20',
    text: 'text-indigo-600 dark:text-indigo-400',
    activeBg: 'bg-indigo-50 dark:bg-indigo-900/20',
    progress: 'from-indigo-500 to-indigo-600'
  },
  cyan: {
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/20',
    text: 'text-cyan-600 dark:text-cyan-400',
    activeBg: 'bg-cyan-50 dark:bg-cyan-900/20',
    progress: 'from-cyan-500 to-cyan-600'
  }
};

const AgentCard: React.FC<AgentCardProps> = ({ agent }) => {
  // Get live streaming data
  const { agentStatuses, agentProgress, agentActivities, agentMetrics } = useUIStore();

  const normalizedId = normalizeAgentName(agent.id);
  
  // Use live data if available, fallback to prop data
  const currentStatus = agentStatuses.get(normalizedId) ?? agent.status;
  const liveProgress = agentProgress.get(normalizedId) ?? agent.progress;
  const liveActivity = agentActivities.get(normalizedId) ?? 'Processing...';
  const liveMetrics = agentMetrics.get(normalizedId) ?? {};
  
  // Get agent configuration (try normalized and original)
  const config = AGENT_CONFIG[normalizedId] || AGENT_CONFIG[agent.id] || AGENT_CONFIG['data_harvester'];
  const Icon = config.icon;
  const theme = COLOR_THEMES[config.color as keyof typeof COLOR_THEMES] || COLOR_THEMES.blue;

  return (
    <div className={clsx(
      "p-4 rounded-xl border transition-all duration-300 relative overflow-hidden group",
      currentStatus === 'processing' 
        ? "bg-light-elevated dark:bg-dark-elevated shadow-md-light dark:shadow-none ring-1 ring-primary-100 dark:ring-primary-900/30"
        : "bg-light-elevated dark:bg-dark-elevated border-light-border dark:border-dark-border hover:border-primary-200 dark:hover:border-primary-700",
      currentStatus === 'processing' && theme.border
    )}>
      
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center">
          <div className={clsx(
            "p-2 rounded-lg mr-3 transition-colors",
            currentStatus === 'processing' 
              ? clsx(theme.activeBg, theme.text)
              : "bg-slate-100 dark:bg-zinc-800 text-slate-500 dark:text-zinc-400"
          )}>
            <Icon size={18} />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-slate-800 dark:text-zinc-100">
              {config.displayName}
            </h4>
            <span className="text-xs text-slate-500 dark:text-zinc-500 capitalize">
              {currentStatus}
            </span>
          </div>
        </div>
        
        {/* Status Icon */}
        <div>
          {currentStatus === 'completed' && (
            <CheckCircle2 size={18} className="text-green-500" />
          )}
          {currentStatus === 'processing' && (
            <Loader2 size={18} className={clsx(theme.text, "animate-spin")} />
          )}
          {currentStatus === 'failed' && (
            <AlertCircle size={18} className="text-red-500" />
          )}
          {currentStatus === 'queued' && (
            <Clock size={18} className="text-slate-400 dark:text-zinc-600" />
          )}
        </div>
      </div>

      {/* Live Progress Bar (Only for processing) */}
      {currentStatus === 'processing' && (
        <div className="space-y-2 mb-3">
          {/* Live Activity Text */}
          <div className={clsx(
            "text-[10px] font-mono animate-pulse truncate",
            theme.text
          )}>
            {liveActivity}
          </div>
          
          {/* Progress Bar */}
          <div className="space-y-1">
            <div className="flex justify-between text-[10px] text-slate-500 dark:text-zinc-500 font-medium">
              <span>Progress</span>
              <span>{Math.round(liveProgress)}%</span>
            </div>
            <div className="h-1.5 w-full bg-slate-100 dark:bg-zinc-800 rounded-full overflow-hidden">
              <div 
                className={clsx(
                  "h-full rounded-full relative transition-all duration-500 ease-out bg-gradient-to-r",
                  theme.progress
                )}
                style={{ width: `${liveProgress}%` }}
              >
                <div className="absolute inset-0 bg-white/30 animate-[shimmer_1.5s_infinite]"></div>
              </div>
            </div>
          </div>
          
          {/* Live Metrics (if available) */}
          {Object.keys(liveMetrics).length > 0 && (
            <div className="mt-2 grid grid-cols-2 gap-2">
              {Object.entries(liveMetrics).slice(0, 2).map(([key, value]) => (
                <div key={key} className="text-[10px] bg-slate-50 dark:bg-zinc-900 px-2 py-1 rounded">
                  <div className="text-slate-500 dark:text-zinc-600 uppercase">{key}</div>
                  <div className="font-semibold text-slate-700 dark:text-zinc-300">
                    {String(value)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Summary (For completed) */}
      {currentStatus === 'completed' && agent.summary && (
        <div className="mt-2 text-xs text-slate-600 dark:text-zinc-400 bg-slate-50 dark:bg-zinc-900/50 p-2 rounded-lg border border-slate-100 dark:border-zinc-800">
          {agent.summary}
        </div>
      )}

      {/* Completion Badge */}
      {currentStatus === 'completed' && (
        <div className="mt-2 flex items-center gap-1.5 text-[10px] text-green-600 dark:text-green-400">
          <CheckCircle2 size={12} />
          <span className="font-medium">Execution complete</span>
        </div>
      )}

      {/* Active Glow Effect */}
      {currentStatus === 'processing' && (
        <div className={clsx(
          "absolute inset-0 border-2 rounded-xl pointer-events-none animate-pulse",
          theme.border
        )}></div>
      )}
    </div>
  );
};

export default AgentCard;