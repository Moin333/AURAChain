// src/components/Canvas/AgentDashboard.tsx
import React from 'react';
import AgentCard from './AgentCard';
import ArtifactRenderer from './ArtifactRenderer';
import DetailedReport from './DetailedReport';
import { useUIStore, normalizeAgentName } from '../../store/uiStore';
import { X, ArrowLeft, FileBarChart, ChevronRight } from 'lucide-react';

const AgentDashboard: React.FC = () => {
  const {
    selectedAgentId,
    setSelectedAgent,
    setRightPanelOpen,
    currentPlan,
    agentStatuses,
    agentProgress,
    messages,
    currentWorkflowId,
    fetchReport
  } = useUIStore();

  const planMessage = messages.find(m => m.type === 'analysis' && m.metadata?.agents);
  const agentResults = planMessage?.metadata?.agentResults || {};

  const handleBackToWorkflow = () => {
    setSelectedAgent(null);
  };

  // ── Report View ──
  if (selectedAgentId === '__report__') {
    return <DetailedReport />;
  }

  // ── Agent Artifact View ──
  if (selectedAgentId) {
    const normalizedId = normalizeAgentName(selectedAgentId);

    const agentData =
      agentResults[selectedAgentId] ||
      agentResults[normalizedId] ||
      Object.entries(agentResults).find(([key]) =>
        normalizeAgentName(key) === normalizedId
      )?.[1];

    console.log('🔍 Agent Data Lookup:', {
      selectedAgentId,
      normalizedId,
      availableKeys: Object.keys(agentResults),
      foundData: !!agentData,
      dataPreview: agentData ? Object.keys(agentData.data || {}) : []
    });

    return (
      <div className="h-full flex flex-col bg-light-elevated dark:bg-dark-elevated animate-slide-in">
        <div className="h-16 px-6 border-b border-light-border dark:border-dark-border flex items-center justify-between flex-shrink-0">
          <button
            onClick={handleBackToWorkflow}
            className="flex items-center gap-2 text-sm font-medium text-slate-600 dark:text-zinc-400 hover:text-primary-500 dark:hover:text-primary-400 transition-colors"
          >
            <ArrowLeft size={16} />
            Back to Workflow
          </button>

          <button
            onClick={() => setRightPanelOpen(false)}
            className="p-2 text-slate-400 dark:text-zinc-500 hover:text-slate-600 dark:hover:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
            aria-label="Close panel"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
          <div className="mb-6">
            <h2 className="text-xl font-heading font-bold text-slate-800 dark:text-zinc-100">
              {selectedAgentId}
            </h2>
            <span className="text-xs text-slate-500 dark:text-zinc-500">
              Agent execution artifact
            </span>
          </div>

          {!agentData ? (
            <div className="p-6 bg-yellow-50 dark:bg-yellow-900/10 border border-yellow-200 dark:border-yellow-800 rounded-xl">
              <h3 className="text-sm font-semibold text-yellow-800 dark:text-yellow-300 mb-2">
                ⚠️ No Data Available
              </h3>
              <div className="text-xs text-yellow-700 dark:text-yellow-400 space-y-2">
                <p>Agent data not found. This could mean:</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>Agent is still processing</li>
                  <li>Agent execution failed</li>
                  <li>Data hasn't been stored yet</li>
                </ul>
                <div className="mt-3 pt-3 border-t border-yellow-200 dark:border-yellow-800">
                  <p className="font-mono text-[10px]">
                    <strong>Looking for:</strong> {selectedAgentId}<br />
                    <strong>Normalized:</strong> {normalizedId}<br />
                    <strong>Available:</strong> {Object.keys(agentResults).join(', ') || 'none'}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <ArtifactRenderer
              agentType={selectedAgentId}
              data={agentData?.data || {}}
            />
          )}
        </div>
      </div>
    );
  }

  // ── Workflow Overview ──
  const agentsList = currentPlan?.agents || [];
  const executionLevels = currentPlan?.execution_levels || [];
  const allCompleted = agentsList.length > 0 && agentsList.every(a => agentStatuses.get(normalizeAgentName(a)) === 'completed');

  return (
    <div className="h-full flex flex-col bg-light-surface dark:bg-dark-surface">
      <div className="h-16 px-6 border-b border-light-border dark:border-dark-border flex items-center justify-between flex-shrink-0 bg-light-elevated dark:bg-dark-elevated">
        <div>
          <h2 className="font-heading font-semibold text-slate-800 dark:text-zinc-100">
            Agent Workflow
          </h2>
          <p className="text-xs text-slate-500 dark:text-zinc-500">
            {agentsList.length > 0 ? `${agentsList.length} Agents Assigned` : 'Waiting for plan...'}
          </p>
        </div>

        <button
          onClick={() => setRightPanelOpen(false)}
          className="p-2 -mr-2 text-slate-400 dark:text-zinc-500 hover:text-slate-600 dark:hover:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
          aria-label="Close panel"
        >
          <X size={20} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">

        {/* ── Local DAG Visualization ── */}
        {executionLevels.length > 1 && (
          <div className="bg-light-elevated dark:bg-dark-elevated border border-slate-200 dark:border-zinc-700 rounded-xl p-4 mb-2">
            <div className="text-[10px] uppercase font-bold text-slate-400 dark:text-zinc-600 tracking-wider mb-3">
              Execution Graph
            </div>
            <div className="flex flex-col items-center gap-2">
              {executionLevels.map((level, levelIdx) => (
                <React.Fragment key={levelIdx}>
                  {/* Level nodes */}
                  <div className="flex gap-2 justify-center flex-wrap">
                    {level.map((agentName) => {
                      const norm = normalizeAgentName(agentName);
                      const status = agentStatuses.get(norm) || 'queued';
                      const bgColor = status === 'completed'
                        ? 'bg-accent-teal/15 border-accent-teal/30 text-accent-teal'
                        : status === 'processing'
                          ? 'bg-accent-amber/15 border-accent-amber/30 text-accent-amber animate-pulse'
                          : status === 'failed'
                            ? 'bg-red-500/15 border-red-500/30 text-red-500'
                            : 'bg-slate-100 dark:bg-zinc-800 border-slate-200 dark:border-zinc-700 text-slate-500 dark:text-zinc-400';

                      return (
                        <button
                          key={agentName}
                          onClick={() => setSelectedAgent(agentName)}
                          className={`px-3 py-1.5 rounded-lg border text-[10px] font-bold uppercase tracking-wider transition-all hover:scale-105 cursor-pointer ${bgColor}`}
                        >
                          {agentName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                        </button>
                      );
                    })}
                  </div>
                  {/* Arrow between levels */}
                  {levelIdx < executionLevels.length - 1 && (
                    <div className="flex flex-col items-center">
                      <div className="w-0.5 h-3 bg-slate-300 dark:bg-zinc-600" />
                      <div className="w-0 h-0 border-l-[4px] border-r-[4px] border-t-[5px] border-l-transparent border-r-transparent border-t-slate-300 dark:border-t-zinc-600" />
                    </div>
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>
        )}

        {agentsList.length === 0 && (
          <div className="text-center text-slate-400 dark:text-zinc-600 mt-10 text-sm">
            No active workflow. Start a chat to trigger agents.
          </div>
        )}

        {/* Agent Cards */}
        <div className="grid grid-cols-1 gap-4">
          {agentsList.map((agentName, idx) => {
            const normalizedName = normalizeAgentName(agentName);
            const status = agentStatuses.get(normalizedName) || 'queued';
            const progress = agentProgress.get(normalizedName) || 0;

            let type: 'harvester' | 'analyst' | 'forecaster' | 'visualizer' | 'optimizer' | 'order_manager' | 'notifier' = 'analyst';
            if (normalizedName.includes('harvest')) type = 'harvester';
            if (normalizedName.includes('forecast')) type = 'forecaster';
            if (normalizedName.includes('visual')) type = 'visualizer';
            if (normalizedName.includes('optim')) type = 'optimizer';
            if (normalizedName.includes('order')) type = 'order_manager';
            if (normalizedName.includes('notif')) type = 'notifier';

            return (
              <div key={idx} onClick={() => setSelectedAgent(agentName)} className="cursor-pointer">
                <AgentCard agent={{
                  id: agentName,
                  name: agentName,
                  type: type,
                  status: status,
                  progress: progress,
                  summary: status === 'completed' ? "View generated artifact" : undefined
                }} />
              </div>
            );
          })}
        </div>

        {/* ── View Report Button ── */}
        {allCompleted && currentWorkflowId && (
          <button
            onClick={() => {
              fetchReport(currentWorkflowId);
              setSelectedAgent('__report__');
            }}
            className="w-full group flex items-center justify-between bg-primary-50 dark:bg-primary-900/20 border border-primary-200 dark:border-primary-800 rounded-xl p-4 hover:border-primary-400 dark:hover:border-primary-600 transition-all"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary-100 dark:bg-primary-900/40 text-primary-600 dark:text-primary-400 rounded-lg">
                <FileBarChart size={20} />
              </div>
              <div className="text-left">
                <div className="text-sm font-semibold text-primary-700 dark:text-primary-300">
                  View Executive Report
                </div>
                <div className="text-[11px] text-primary-500 dark:text-primary-500/80">
                  Full multi-agent analysis with recommendations
                </div>
              </div>
            </div>
            <ChevronRight size={16} className="text-primary-500 group-hover:translate-x-1 transition-transform" />
          </button>
        )}
      </div>
    </div>
  );
};

export default AgentDashboard;