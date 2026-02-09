// aurachain-ui/src/components/Canvas/AgentDashboard.tsx
import React from 'react';
import AgentCard from './AgentCard';
import ArtifactRenderer from './ArtifactRenderer';
import { useUIStore, normalizeAgentName } from '../../store/uiStore'; 
import { X, ArrowLeft } from 'lucide-react'; 

const AgentDashboard: React.FC = () => {
  const { 
    selectedAgentId, 
    setSelectedAgent, 
    setRightPanelOpen, 
    currentPlan, 
    agentStatuses,
    agentProgress,
    messages
  } = useUIStore();

  const planMessage = messages.find(m => m.type === 'analysis' && m.metadata?.agents);
  const agentResults = planMessage?.metadata?.agentResults || {};

  const handleBackToWorkflow = () => {
    setSelectedAgent(null);
  };

  if (selectedAgentId) {

    const normalizedId = normalizeAgentName(selectedAgentId);

    const agentData = 
      agentResults[selectedAgentId] ||
      agentResults[normalizedId] ||
      Object.entries(agentResults).find(([key]) => 
        normalizeAgentName(key) === normalizedId
      )?.[1];

    console.log('🔍 Looking up agent data:', {
      selectedAgentId,
      normalizedId,
      availableKeys: Object.keys(agentResults),
      foundData: !!agentData
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
                    <h2 className="text-xl font-heading font-bold text-slate-800 dark:text-zinc-100">{selectedAgentId}</h2>
                    <span className="text-xs text-slate-500 dark:text-zinc-500">Agent execution artifact</span>
                </div>

                {/* DEBUG: Show what we found */}
                {!agentData && (
                  <div className="mb-4 p-3 bg-yellow-50 dark:bg-yellow-900/10 border border-yellow-200 dark:border-yellow-800 rounded-lg text-xs">
                    <div className="font-semibold text-yellow-800 dark:text-yellow-300 mb-1">
                      ⚠️ Debug: Agent data not found
                    </div>
                    <div className="text-yellow-700 dark:text-yellow-400 space-y-1 font-mono">
                      <div>Looking for: {selectedAgentId}</div>
                      <div>Normalized: {normalizedId}</div>
                      <div>Available: {Object.keys(agentResults).join(', ') || 'none'}</div>
                    </div>
                  </div>
                )}
                
                <ArtifactRenderer 
                  agentType={selectedAgentId} 
                  data={agentData?.data || {}} 
                />
            </div>
        </div>
    );
  }

  const agentsList = currentPlan?.agents || [];

  return (
    <div className="h-full flex flex-col bg-light-surface dark:bg-dark-surface">
      <div className="h-16 px-6 border-b border-light-border dark:border-dark-border flex items-center justify-between flex-shrink-0 bg-light-elevated dark:bg-dark-elevated">
        <div>
          <h2 className="font-heading font-semibold text-slate-800 dark:text-zinc-100">Agent Workflow</h2>
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
        {agentsList.length === 0 && (
            <div className="text-center text-slate-400 dark:text-zinc-600 mt-10 text-sm">
                No active workflow. Start a chat to trigger agents.
            </div>
        )}

        <div className="grid grid-cols-1 gap-4">
          {agentsList.map((agentName, idx) => {
            const status = agentStatuses.get(agentName) || 'queued';
            const progress = agentProgress.get(agentName) || 0;
            
            let type: 'harvester' | 'analyst' | 'forecaster' = 'analyst';
            if(agentName.toLowerCase().includes('harvest')) type = 'harvester';
            if(agentName.toLowerCase().includes('forecast')) type = 'forecaster';

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
      </div>
    </div>
  );
};

export default AgentDashboard;