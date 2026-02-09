// src/services/api.ts

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// --- Types based on Backend ---

export interface OrchestrationPlan {
  mode: string;
  reasoning: string;
  agents: string[];
  execution_plan: Array<{
    agent: string;
    task: string;
    parameters: Record<string, any>;
    depends_on: string[];
  }>;
}

export interface AgentResponseData {
  agent: string;
  success: boolean;
  data: any;
  error?: string;
}

// UPDATED: New response structure
export interface QueryResponse {
  request_id: string;
  session_id: string;
  orchestration_plan: OrchestrationPlan;
  message: string;
  status: 'planned' | 'executing' | 'completed' | 'failed';
}

export interface DatasetResponse {
  dataset_id: string;
  filename: string;
  shape: [number, number];
  columns: string[];
}

export const api = {
  // 1. Initialize a new Session
  createSession: async (userId: string) => {
    const response = await fetch(`${API_URL}/orchestrator/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: "SESSION_INIT",
        user_id: userId,
        context: {}
      })
    });
    
    if (!response.ok) {
      throw new Error(`Session creation failed: ${response.statusText}`);
    }
    
    return response.json();
  },

  // 2. Send Query (now returns immediately with plan)
  sendQuery: async (
    query: string, 
    sessionId: string, 
    userId: string,
    context: Record<string, any> = {}
  ): Promise<QueryResponse> => {
    const response = await fetch(`${API_URL}/orchestrator/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        session_id: sessionId,
        user_id: userId,
        context, 
        parameters: {}
      })
    });
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }
    return response.json();
  },

  // 3. File Upload
  uploadDataset: async (file: File): Promise<DatasetResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${API_URL}/data/upload`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) throw new Error('Upload failed');
    return response.json();
  },

  // 4. Human-in-the-Loop Approval
  approveOrder: async (orderId: string, sessionId: string) => {
    console.log(`Approving order ${orderId} for session ${sessionId}`);
    return { success: true, message: "Order approved and sent to vendor." };
  }
};