// aurachain-ui/src/components/Canvas/AgentCard.tsx
import React from 'react';
import { clsx } from 'clsx';
import { CheckCircle2, Clock, AlertCircle, Database, TrendingUp, BrainCircuit, Loader2 } from 'lucide-react';
import { useUIStore } from '../../store/uiStore';

export interface Agent {
  id: string;
  name: string;
  type: 'harvester' | 'analyst' | 'forecaster';
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number;
  summary?: string;
}

interface AgentCardProps {
  agent: Agent;
}

const AgentCard: React.FC<AgentCardProps> = ({ agent }) => {
  // Get live streaming data
  const { agentProgress, agentActivities, agentMetrics } = useUIStore();
  
  // Use live data if available, fallback to prop data
  const liveProgress = agentProgress.get(agent.id) ?? agent.progress;
  const liveActivity = agentActivities.get(agent.id) ?? 'Processing...';
  const liveMetrics = agentMetrics.get(agent.id) ?? {};
  
  // Icon Selection
  const Icon = {
    harvester: Database,
    analyst: TrendingUp,
    forecaster: BrainCircuit
  }[agent.type];

  return (
    <div className={clsx(
      "p-4 rounded-xl border transition-all duration-300 relative overflow-hidden group",
      agent.status === 'processing' 
        ? "bg-light-elevated dark:bg-dark-elevated border-primary-200 dark:border-primary-800 shadow-md-light dark:shadow-none ring-1 ring-primary-100 dark:ring-primary-900/30" 
        : "bg-light-elevated dark:bg-dark-elevated border-light-border dark:border-dark-border hover:border-primary-200 dark:hover:border-primary-700"
    )}>
      
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center">
          <div className={clsx(
            "p-2 rounded-lg mr-3 transition-colors",
            agent.status === 'processing' 
              ? "bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400" 
              : "bg-slate-100 dark:bg-zinc-800 text-slate-500 dark:text-zinc-400"
          )}>
            <Icon size={18} />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-slate-800 dark:text-zinc-100">{agent.name}</h4>
            <span className="text-xs text-slate-500 dark:text-zinc-500 capitalize">{agent.status}</span>
          </div>
        </div>
        
        {/* Status Icon */}
        <div>
          {agent.status === 'completed' && <CheckCircle2 size={18} className="text-accent-teal" />}
          {agent.status === 'processing' && <Loader2 size={18} className="text-accent-amber animate-spin" />}
          {agent.status === 'failed' && <AlertCircle size={18} className="text-accent-coral" />}
          {agent.status === 'queued' && <Clock size={18} className="text-slate-400 dark:text-zinc-600" />}
        </div>
      </div>

      {/* Live Progress Bar (Only for processing) */}
      {agent.status === 'processing' && (
        <div className="space-y-2 mb-3">
          {/* Live Activity Text */}
          <div className="text-[10px] font-mono text-primary-600 dark:text-primary-400 animate-pulse truncate">
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
                className="h-full bg-gradient-to-r from-primary-500 to-accent-teal rounded-full relative transition-all duration-500 ease-out"
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
                  <div className="font-semibold text-slate-700 dark:text-zinc-300">{String(value)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Summary (For completed) */}
      {agent.status === 'completed' && agent.summary && (
        <div className="mt-2 text-xs text-slate-600 dark:text-zinc-400 bg-slate-50 dark:bg-zinc-900/50 p-2 rounded-lg border border-slate-100 dark:border-zinc-800">
          {agent.summary}
        </div>
      )}

      {/* Active Glow Effect */}
      {agent.status === 'processing' && (
        <div className="absolute inset-0 border-2 border-primary-500/10 dark:border-primary-400/20 rounded-xl pointer-events-none animate-pulse"></div>
      )}
    </div>
  );
};

export default AgentCard;