// aurachain-ui/src/store/uiStore.ts
import { create } from 'zustand';
import { api, type OrchestrationPlan } from '../services/api';
import { type Message } from '../components/Chat/MessageBubble';

interface DatasetContext {
  dataset_id: string;
  filename: string;
  shape: [number, number];
  columns: string[];
}

interface UIState {
  // --- Layout State ---
  isSidebarOpen: boolean;
  isRightPanelOpen: boolean;
  rightPanelWidth: number;
  isDarkMode: boolean;
  
  // --- Session Data ---
  sessionId: string | null;
  userId: string;
  messages: Message[];
  
  // --- Agentic State ---
  isThinking: boolean; 
  processingStep: string | null;
  
  // --- Context ---
  activeDataset: DatasetContext | null;
  selectedAgentId: string | null; 
  
  // --- Orchestration Data ---
  currentPlan: OrchestrationPlan | null;
  agentStatuses: Map<string, 'queued' | 'processing' | 'completed' | 'failed'>;

  // Agent streaming state
  agentProgress: Map<string, number>;
  agentActivities: Map<string, string>;
  agentMetrics: Map<string, Record<string, any>>;
  
  // --- Actions ---
  toggleSidebar: () => void;
  toggleRightPanel: () => void;
  setRightPanelOpen: (isOpen: boolean) => void;
  setRightPanelWidth: (width: number) => void;
  setSelectedAgent: (id: string | null) => void;
  toggleTheme: () => void;
  
  // 🔥 NEW: Ensure session is initialized
  ensureSession: () => Promise<string>;
  initializeSession: () => Promise<void>;
  uploadDataset: (file: File) => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
  resetSession: () => void;

  // Methods for SSE updates
  updateAgentStatus: (agentId: string, status: 'queued' | 'processing' | 'completed' | 'failed') => void;
  updateAgentProgress: (agentId: string, progress: number, activity: string, metrics?: Record<string, any>) => void;
  updateAgentData: (agentId: string, data: any) => void;
}

export const useUIStore = create<UIState>((set, get) => ({
  // --- Initial State ---
  isSidebarOpen: true,
  isRightPanelOpen: false,
  rightPanelWidth: 450,
  isDarkMode: false,
  
  sessionId: null,
  userId: 'demo_user_01', 
  messages: [],
  
  isThinking: false,
  processingStep: null,
  
  activeDataset: null,
  selectedAgentId: null,
  currentPlan: null,
  agentStatuses: new Map(),

  agentProgress: new Map(),
  agentActivities: new Map(),
  agentMetrics: new Map(),

  // --- Layout Actions ---
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  toggleRightPanel: () => set((state) => ({ isRightPanelOpen: !state.isRightPanelOpen })),
  setRightPanelOpen: (isOpen) => set({ isRightPanelOpen: isOpen }),
  setRightPanelWidth: (width) => set({ rightPanelWidth: width }),
  setSelectedAgent: (id) => set({ selectedAgentId: id }),
  
  toggleTheme: () => set((state) => {
    const newMode = !state.isDarkMode;
    if (newMode) document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
    return { isDarkMode: newMode };
  }),

  // --- Functional Actions ---

  // 🔥 NEW: Ensures session exists and returns the session ID
  ensureSession: async (): Promise<string> => {
    const currentSessionId = get().sessionId;
    
    if (currentSessionId) {
      return currentSessionId;
    }
    
    // No session - create one
    await get().initializeSession();
    const newSessionId = get().sessionId;
    
    if (!newSessionId) {
      throw new Error('Failed to create session');
    }
    
    return newSessionId;
  },

  initializeSession: async () => {
    const { userId } = get();
    try {
      console.log('🔄 Creating new session...');
      const res = await api.createSession(userId);
      
      // 🔥 CRITICAL: Use ONLY the backend's session_id (UUID)
      const backendSessionId = res.session_id;
      
      if (!backendSessionId) {
        throw new Error('Backend did not return session_id');
      }
      
      console.log(`✅ Session created: ${backendSessionId}`);
      set({ sessionId: backendSessionId });
      
    } catch (e) {
      console.error("❌ Session Init Failed", e);
      // 🔥 CHANGED: Don't create fallback session - let it fail
      throw e;
    }
  },

  uploadDataset: async (file: File) => {
    try {
      const res = await api.uploadDataset(file);
      set({ 
        activeDataset: {
          dataset_id: res.dataset_id,
          filename: res.filename,
          shape: res.shape,
          columns: res.columns
        }
      });

      const sysMsg: Message = {
        id: Date.now().toString(),
        sender: 'ai',
        text: `dataset_uploaded`, 
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        type: 'text', 
        metadata: {
            displayText: `✅ Ingested **${res.filename}** (${res.shape[0]} rows). Ready for analysis.` 
        }
      };
      
      set(state => ({ messages: [...state.messages, { ...sysMsg, text: sysMsg.metadata?.displayText || "" }] }));

    } catch (e) {
      console.error("Upload failed", e);
    }
  },

  // Update agent status
  updateAgentStatus: (agentId, status) => set((state) => {
    const newStatuses = new Map(state.agentStatuses);
    newStatuses.set(agentId, status);
    
    console.log(`🔄 Agent ${agentId} status: ${status}`);
    
    return { agentStatuses: newStatuses };
  }),

  // Update agent progress
  updateAgentProgress: (agentId, progress, activity, metrics = {}) => set((state) => {
    const newProgress = new Map(state.agentProgress);
    const newActivities = new Map(state.agentActivities);
    const newMetrics = new Map(state.agentMetrics);
    
    newProgress.set(agentId, progress);
    newActivities.set(agentId, activity);
    
    if (Object.keys(metrics).length > 0) {
      newMetrics.set(agentId, metrics);
    }
    
    // Also update plan message progress if it exists
    const updatedMessages = state.messages.map(m => {
      if (m.type === 'analysis' && m.metadata?.agents?.includes(agentId)) {
        return {
          ...m,
          metadata: {
            ...m.metadata,
            progress: Math.round(
              Array.from(newProgress.values()).reduce((a, b) => a + b, 0) / 
              (m.metadata.agents?.length || 1)
            )
          }
        };
      }
      return m;
    });

    return {
      agentProgress: newProgress,
      agentActivities: newActivities,
      agentMetrics: newMetrics,
      messages: updatedMessages
    };
  }),

  // Update agent result data
  updateAgentData: (agentId, data) => set((state) => {
    const updatedMessages = state.messages.map(m => {
      if (m.type === 'analysis' && m.metadata?.agents) {
        const agentResults = m.metadata.agentResults || {};
        
        return {
          ...m,
          metadata: {
            ...m.metadata,
            agentResults: {
              ...agentResults,
              [agentId]: {
                success: true,
                data: data
              }
            }
          }
        };
      }
      return m;
    });
    
    return { messages: updatedMessages };
  }),

  sendMessage: async (text: string) => {
    // 🔥 CRITICAL: Ensure session exists BEFORE sending
    let currentSessionId: string;
    try {
      currentSessionId = await get().ensureSession();
    } catch (e) {
      console.error('❌ Failed to get session:', e);
      set({
        messages: [...get().messages, {
          id: Date.now().toString(),
          sender: 'ai',
          text: '❌ Session initialization failed. Please refresh the page.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          type: 'text'
        }]
      });
      return;
    }

    const { userId, activeDataset } = get();
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text,
      timestamp,
      type: 'text'
    };

    set(state => ({ 
      messages: [...state.messages, userMsg],
      isThinking: true, 
      processingStep: "Orchestrator is analyzing request..."
    }));

    try {
      const context = activeDataset ? { dataset_id: activeDataset.dataset_id } : {};
      
      // 🔥 CRITICAL: Pass the backend session ID
      console.log(`📤 Sending query with session: ${currentSessionId}`);
      const response = await api.sendQuery(text, currentSessionId, userId, context);

      // 1. Add "Thinking" Reasoning
      const reasoningMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: response.orchestration_plan.reasoning,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        type: 'text'
      };
      set(state => ({ messages: [...state.messages, reasoningMsg] }));

      // 2. Add the "Plan Artifact"
      const planMsg: Message = {
        id: (Date.now() + 2).toString(),
        sender: 'ai',
        text: 'Agent Execution Strategy', 
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        type: 'analysis', 
        status: 'processing',
        metadata: {
          progress: 0,
          agents: response.orchestration_plan.agents,
          agentResults: {}
        }
      };

      set(state => ({ 
        messages: [...state.messages, planMsg],
        currentPlan: response.orchestration_plan,
        isRightPanelOpen: true, 
        selectedAgentId: null 
      }));

      // --- STREAMING SIMULATION (will be replaced by real SSE) ---
      const agents = response.agent_responses;
      const totalAgents = agents.length;
      let completedCount = 0;

      for (const agentRes of agents) {
        set(state => ({
          processingStep: `Activating ${agentRes.agent}...`,
          agentStatuses: new Map(state.agentStatuses).set(agentRes.agent, 'processing')
        }));

        await new Promise(r => setTimeout(r, 800));

        set(state => ({
          agentStatuses: new Map(state.agentStatuses).set(agentRes.agent, agentRes.success ? 'completed' : 'failed'),
          selectedAgentId: agentRes.agent,
          
          messages: state.messages.map(m => 
            m.id === planMsg.id 
              ? { 
                  ...m, 
                  metadata: { 
                    ...m.metadata, 
                    progress: Math.round(((completedCount + 1) / totalAgents) * 100),
                    agentResults: {
                      ...m.metadata?.agentResults,
                      [agentRes.agent]: {
                        success: agentRes.success,
                        data: agentRes.data,
                        error: agentRes.error
                      }
                    }
                  } 
                } 
              : m
          )
        }));

        completedCount++;
        await new Promise(r => setTimeout(r, 1200));
      }

      set(state => ({
        isThinking: false,
        processingStep: null,
        selectedAgentId: null, 
        messages: state.messages.map(m => 
            m.id === planMsg.id 
              ? { ...m, status: 'completed', metadata: { ...m.metadata, progress: 100 } } 
              : m
          )
      }));

    } catch (error: any) {
      console.error("❌ Interaction failed", error);
      set(state => ({
        isThinking: false,
        processingStep: null,
        messages: [...state.messages, {
          id: Date.now().toString(),
          sender: 'ai',
          text: `System Error: ${error.message || "Unknown error"}`,
          timestamp,
          type: 'text'
        }]
      }));
    }
  },

  resetSession: () => set({
    messages: [],
    activeDataset: null,
    currentPlan: null,
    agentStatuses: new Map(),
    isRightPanelOpen: false,
    sessionId: null, // 🔥 ADDED: Clear session on reset
  })
}));