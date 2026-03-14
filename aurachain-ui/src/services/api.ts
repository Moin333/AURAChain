// src/services/api.ts

import type {
  ReportResponse,
  SummaryResponse,
  DecisionRecord,
  AccuracyStats,
  OutcomeRequest,
  ExperimentRecord,
  ComparisonResult,
  VisualizationResult,
  HealthStatus,
} from '../types/api';

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
  execution_levels?: string[][];
}

export interface AgentResponseData {
  agent: string;
  success: boolean;
  data: any;
  error?: string;
}

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
  // ── Session & Query ──

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

  // ── Data Upload ──

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

  // ── Reports ──

  getReport: async (workflowId: string): Promise<ReportResponse> => {
    const response = await fetch(`${API_URL}/reports/${workflowId}`);
    if (!response.ok) {
      throw new Error(`Report not found: ${response.statusText}`);
    }
    return response.json();
  },

  getReportSummary: async (workflowId: string): Promise<SummaryResponse> => {
    const response = await fetch(`${API_URL}/reports/${workflowId}/summary`);
    if (!response.ok) {
      throw new Error(`Summary not found: ${response.statusText}`);
    }
    return response.json();
  },

  // ── Experiments ──

  getExperiments: async (limit: number = 20): Promise<{ count: number; experiments: ExperimentRecord[] }> => {
    const response = await fetch(`${API_URL}/experiments/?limit=${limit}`);
    if (!response.ok) throw new Error('Failed to fetch experiments');
    return response.json();
  },

  compareExperiments: async (idA: string, idB: string): Promise<ComparisonResult> => {
    const response = await fetch(`${API_URL}/experiments/compare?experiment_a=${idA}&experiment_b=${idB}`);
    if (!response.ok) throw new Error('Failed to compare experiments');
    return response.json();
  },

  // ── Decisions ──

  getDecisions: async (limit: number = 20, decisionType?: string): Promise<{ count: number; decisions: DecisionRecord[] }> => {
    let url = `${API_URL}/decisions/?limit=${limit}`;
    if (decisionType) url += `&decision_type=${decisionType}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch decisions');
    return response.json();
  },

  getDecisionStats: async (): Promise<AccuracyStats> => {
    const response = await fetch(`${API_URL}/decisions/stats`);
    if (!response.ok) throw new Error('Failed to fetch decision stats');
    return response.json();
  },

  recordOutcome: async (decisionId: string, body: OutcomeRequest): Promise<{ status: string; decision: DecisionRecord }> => {
    const response = await fetch(`${API_URL}/decisions/${decisionId}/outcome`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!response.ok) throw new Error('Failed to record outcome');
    return response.json();
  },

  // ── Visualization ──

  visualizeWorkflow: async (plan: any): Promise<VisualizationResult> => {
    const response = await fetch(`${API_URL}/workflows/visualize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan })
    });
    if (!response.ok) throw new Error('Failed to visualize workflow');
    return response.json();
  },

  // ── Health ──

  getHealth: async (): Promise<HealthStatus> => {
    const response = await fetch(`${API_URL}/health/detailed`);
    if (!response.ok) throw new Error('Health check failed');
    return response.json();
  },

  // ── Human-in-the-Loop ──

  approveOrder: async (orderId: string, sessionId: string) => {
    console.log(`Approving order ${orderId} for session ${sessionId}`);
    return { success: true, message: "Order approved and sent to vendor." };
  }
};