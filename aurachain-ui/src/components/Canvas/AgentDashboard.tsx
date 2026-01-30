// aurachain-ui/src/components/Canvas/AgentDashboard.tsx
import React from 'react';
import AgentCard from './AgentCard';
import ArtifactRenderer from './ArtifactRenderer';
import { useUIStore } from '../../store/uiStore'; 
import { X, ArrowLeft } from 'lucide-react'; 

const AgentDashboard: React.FC = () => {
  const { 
    selectedAgentId, 
    setSelectedAgent, 
    setRightPanelOpen, 
    currentPlan, 
    agentStatuses,
    messages
  } = useUIStore();

  // 🔑 CRITICAL FIX: Get agent results from the Plan message metadata
  const planMessage = messages.find(m => m.type === 'analysis' && m.metadata?.agents);
  const agentResults = planMessage?.metadata?.agentResults || {};

  // 1. DETAIL VIEW: If an agent is selected, show its artifact
  if (selectedAgentId) {
    const agentData = agentResults[selectedAgentId];

    return (
        <div className="h-full flex flex-col bg-white dark:bg-dark-elevated animate-slide-in">
            {/* Header */}
            <div className="h-16 px-6 border-b border-light-border dark:border-dark-border flex items-center justify-between flex-shrink-0">
                <button 
                    onClick={() => setSelectedAgent(null)}
                    className="flex items-center text-sm text-slate-500 hover:text-primary-500 transition-colors"
                >
                    <ArrowLeft size={16} className="mr-2" />
                    Back to Workflow
                </button>
            </div>

            {/* Dynamic Artifact Content */}
            <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
                <div className="mb-6">
                    <h2 className="text-xl font-heading font-bold text-slate-800 dark:text-white">{selectedAgentId}</h2>
                    <span className="text-xs text-slate-500">Agent execution artifact</span>
                </div>
                
                {/* THE RENDERER */}
                <ArtifactRenderer 
                  agentType={selectedAgentId} 
                  data={agentData?.data || {}} 
                />
            </div>
        </div>
    );
  }

  // 2. OVERVIEW VIEW: Show the list of agents from the Plan
  const agentsList = currentPlan?.agents || [];

  return (
    <div className="h-full flex flex-col bg-light-surface dark:bg-dark-surface">
      {/* Header */}
      <div className="h-16 px-6 border-b border-light-border dark:border-dark-border flex items-center justify-between flex-shrink-0 bg-white dark:bg-dark-elevated">
        <div>
          <h2 className="font-heading font-semibold text-slate-800 dark:text-white">Agent Workflow</h2>
          <p className="text-xs text-slate-500">
            {agentsList.length > 0 ? `${agentsList.length} Agents Assigned` : 'Waiting for plan...'}
          </p>
        </div>
        
        <button 
          onClick={() => setRightPanelOpen(false)}
          className="p-2 -mr-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
        >
          <X size={20} />
        </button>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
        {agentsList.length === 0 && (
            <div className="text-center text-slate-400 mt-10 text-sm">
                No active workflow. Start a chat to trigger agents.
            </div>
        )}

        {/* Grid of Cards */}
        <div className="grid grid-cols-1 gap-4">
          {agentsList.map((agentName, idx) => {
            // Get status from store map
            const status = agentStatuses.get(agentName) || 'queued';
            
            // Map generic name to specific type for Icon logic in AgentCard
            let type: 'harvester' | 'analyst' | 'forecaster' = 'analyst';
            if(agentName.toLowerCase().includes('harvest')) type = 'harvester';
            if(agentName.toLowerCase().includes('forecast')) type = 'forecaster';

            // Calculate progress based on status for visual effect
            const progress = status === 'completed' ? 100 : status === 'processing' ? 50 : 0;

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