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
  
  // NEW: Session initialization state
  sessionInitPromise: Promise<string> | null;
  
  // --- Actions ---
  toggleSidebar: () => void;
  toggleRightPanel: () => void;
  setRightPanelOpen: (isOpen: boolean) => void;
  setRightPanelWidth: (width: number) => void;
  setSelectedAgent: (id: string | null) => void;
  toggleTheme: () => void;
  
  ensureSession: () => Promise<string>;
  initializeSession: () => Promise<void>;
  uploadDataset: (file: File) => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
  resetSession: () => void;

  // SSE update methods
  updateAgentStatus: (agentId: string, status: 'queued' | 'processing' | 'completed' | 'failed') => void;
  updateAgentProgress: (agentId: string, progress: number, activity: string, metrics?: Record<string, any>) => void;
  updateAgentData: (agentId: string, data: any) => void;
  
  // NEW: Workflow event handlers
  handleWorkflowStarted: (agents: string[]) => void;
  handleWorkflowCompleted: () => void;
}

// NEW: Helper to normalize agent names
export const normalizeAgentName = (name: string): string => {
  return name.toLowerCase().replace(/[_\s-]/g, '');
};

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
  
  sessionInitPromise: null,

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

  // FIXED: Thread-safe session initialization
  ensureSession: async (): Promise<string> => {
    const currentSessionId = get().sessionId;
    
    if (currentSessionId) {
      return currentSessionId;
    }
    
    // Check if initialization is already in progress
    const existingPromise = get().sessionInitPromise;
    if (existingPromise) {
      console.log('⏳ Reusing in-flight session creation...');
      return existingPromise;
    }
    
    // Create new initialization promise
    const promise = (async () => {
      try {
        console.log('🔄 Creating new session...');
        const res = await api.createSession(get().userId);
        
        const backendSessionId = res.session_id;
        
        if (!backendSessionId) {
          throw new Error('Backend did not return session_id');
        }
        
        console.log(`✅ Session created: ${backendSessionId}`);
        set({ sessionId: backendSessionId, sessionInitPromise: null });
        
        return backendSessionId;
      } catch (e) {
        console.error('❌ Session creation failed:', e);
        set({ sessionInitPromise: null });
        throw e;
      }
    })();
    
    set({ sessionInitPromise: promise });
    return promise;
  },

  initializeSession: async () => {
    await get().ensureSession();
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
        text: `✅ Ingested **${res.filename}** (${res.shape[0]} rows). Ready for analysis.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        type: 'text'
      };
      
      set(state => ({ messages: [...state.messages, sysMsg] }));

    } catch (e) {
      console.error("Upload failed", e);
    }
  },

  // FIXED: Optimistic updates, no fake delays
  sendMessage: async (text: string) => {
    // Ensure session exists
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

    // 1. Show user message immediately (optimistic)
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
      processingStep: "Creating orchestration plan..."
    }));

    try {
      const context = activeDataset ? { dataset_id: activeDataset.dataset_id } : {};
      
      console.log(`📤 Sending query with session: ${currentSessionId}`);
      
      // 2. Send query (returns plan immediately - <200ms)
      const response = await api.sendQuery(text, currentSessionId, userId, context);

      // 3. Show reasoning
      const reasoningMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: response.orchestration_plan.reasoning || 'Analyzing request...',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        type: 'text'
      };
      set(state => ({ messages: [...state.messages, reasoningMsg] }));

      // 4. Show plan artifact (SSE will update this)
      const planMsg: Message = {
        id: (Date.now() + 2).toString(),
        sender: 'ai',
        text: 'Agent Execution Strategy', 
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        type: 'analysis', 
        status: 'processing', // Will be updated by SSE
        metadata: {
          progress: 0,
          agents: response.orchestration_plan.agents || [],
          agentResults: {}
        }
      };

      set(state => ({ 
        messages: [...state.messages, planMsg],
        currentPlan: response.orchestration_plan,
        isRightPanelOpen: true, 
        selectedAgentId: null,
        isThinking: false, // Plan received, now waiting for SSE
        processingStep: "Agents executing..." // SSE will update this
      }));
      
      // 5. Initialize agent statuses
      const newStatuses = new Map<string, 'queued' | 'processing' | 'completed' | 'failed'>();
      (response.orchestration_plan.agents || []).forEach(agent => {
        newStatuses.set(normalizeAgentName(agent), 'queued');
      });
      set({ agentStatuses: newStatuses });

      console.log('✅ Plan received, waiting for SSE updates...');

    } catch (error: any) {
      console.error("❌ Query failed", error);
      set(state => ({
        isThinking: false,
        processingStep: null,
        messages: [...state.messages, {
          id: Date.now().toString(),
          sender: 'ai',
          text: `❌ Error: ${error.message || "Unknown error"}`,
          timestamp,
          type: 'text'
        }]
      }));
    }
  },

  // UPDATED: Normalize agent names
  updateAgentStatus: (agentId, status) => set((state) => {
    const normalized = normalizeAgentName(agentId);
    const newStatuses = new Map(state.agentStatuses);
    newStatuses.set(normalized, status);
    
    console.log(`🔄 Agent ${agentId} (${normalized}) status: ${status}`);
    
    return { agentStatuses: newStatuses };
  }),

  // UPDATED: Normalize agent names + update plan message
  updateAgentProgress: (agentId, progress, activity, metrics = {}) => set((state) => {
    const normalized = normalizeAgentName(agentId);
    const newProgress = new Map(state.agentProgress);
    const newActivities = new Map(state.agentActivities);
    const newMetrics = new Map(state.agentMetrics);
    
    newProgress.set(normalized, progress);
    newActivities.set(normalized, activity);
    
    if (Object.keys(metrics).length > 0) {
      newMetrics.set(normalized, metrics);
    }
    
    // Update the plan message's overall progress
    const updatedMessages = state.messages.map(m => {
      if (m.type === 'analysis' && m.metadata?.agents) {
        const agentCount = m.metadata.agents.length;
        const totalProgress = Array.from(newProgress.values()).reduce((a, b) => a + b, 0);
        const avgProgress = agentCount > 0 ? Math.round(totalProgress / agentCount) : 0;
        
        return {
          ...m,
          metadata: {
            ...m.metadata,
            progress: avgProgress
          }
        };
      }
      return m;
    });

    return {
      agentProgress: newProgress,
      agentActivities: newActivities,
      agentMetrics: newMetrics,
      messages: updatedMessages,
      processingStep: `${agentId}: ${activity}` // Update global status
    };
  }),

  // UPDATED: Store agent results
  updateAgentData: (agentId, data) => set((state) => {
    const normalized = normalizeAgentName(agentId);
    
    const updatedMessages = state.messages.map(m => {
      if (m.type === 'analysis' && m.metadata?.agents) {
        const agentResults = m.metadata.agentResults || {};
        
        return {
          ...m,
          metadata: {
            ...m.metadata,
            agentResults: {
              ...agentResults,
              [normalized]: {
                success: true,
                data: data,
                originalName: agentId
              },
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
    
    console.log(`📦 Stored result for ${agentId} (normalized: ${normalized})`);
    
    return { messages: updatedMessages };
  }),

  // NEW: Handle workflow started event
  handleWorkflowStarted: (agents: string[]) => {
    console.log('🎬 Workflow started:', agents);
    
    // Initialize all agents as queued
    const newStatuses = new Map<string, 'queued' | 'processing' | 'completed' | 'failed'>();
    agents.forEach(agent => {
      newStatuses.set(normalizeAgentName(agent), 'queued');
    });
    
    set({
      agentStatuses: newStatuses,
      processingStep: "Workflow executing..."
    });
  },

  // NEW: Handle workflow completed event
  handleWorkflowCompleted: () => set((state) => {
    console.log('✅ Workflow completed');
    
    // Mark plan message as completed
    const updatedMessages = state.messages.map(m => {
      if (m.type === 'analysis' && m.status === 'processing') {
        return { 
          ...m, 
          status: 'completed' as const,
          metadata: { 
            ...m.metadata, 
            progress: 100 
          } 
        };
      }
      return m;
    });
    
    return {
      messages: updatedMessages,
      isThinking: false,
      processingStep: null,
      selectedAgentId: null
    };
  }),

  resetSession: () => set({
    messages: [],
    activeDataset: null,
    currentPlan: null,
    agentStatuses: new Map(),
    agentProgress: new Map(),
    agentActivities: new Map(),
    agentMetrics: new Map(),
    isRightPanelOpen: false,
    sessionId: null,
    sessionInitPromise: null
  })
}));