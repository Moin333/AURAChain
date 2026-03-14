/* eslint-disable @typescript-eslint/no-explicit-any */
// src/types/api.ts
/**
 * TypeScript interfaces matching backend response shapes.
 * Used by api.ts and components that consume backend data.
 */

// ── Reports ──

export interface ReportSection {
  title: string;
  content: string;
  agent_source: string;
  confidence: number;
}

export interface ReportResponse {
  workflow_id: string;
  title: string;
  generated_at: string;
  sections: ReportSection[];
  overall_confidence: number;
  agents_contributing: string[];
  total_duration_ms: number;
}

export interface SummaryResponse {
  workflow_id: string;
  summary: string;
  key_insights: string[];
  agents_used: string[];
  generated_at: string;
}

// ── Decisions ──

export interface OutcomeRecord {
  expected_outcome: string;
  actual_outcome: string;
  accuracy_score: number;
  feedback: string;
  recorded_at: string;
}

export interface DecisionRecord {
  decision_id: string;
  workflow_id: string;
  decision_type: string;
  query: string;
  recommended_actions: string[];
  confidence: number;
  agent_metrics: Record<string, any>;
  timestamp: string;
  outcome: OutcomeRecord | null;
}

export interface OutcomeRequest {
  expected_outcome: string;
  actual_outcome: string;
  accuracy_score: number;
  feedback?: string;
}

export interface AccuracyStats {
  total_decisions: number;
  decisions_with_outcomes: number;
  average_accuracy: number | null;
  per_type?: Record<string, { count: number; average_accuracy: number }>;
}

// ── Experiments ──

export interface ExperimentRecord {
  experiment_id: string;
  workflow_id: string;
  dataset_hash: string;
  agent_config: Record<string, any>;
  agent_metrics: Record<string, Record<string, number>>;
  confidence_scores: Record<string, number>;
  overall_confidence: number;
  planner_reasoning: string;
  report_summary: string;
  execution_time_ms: number;
  created_at: string;
}

export interface ComparisonResult {
  experiment_a: string;
  experiment_b: string;
  metric_diffs: Record<string, Record<string, number>>;
  confidence_diffs: Record<string, number>;
  overall_confidence_diff: number;
  execution_time_diff_ms: number;
  improvements: number;
  regressions: number;
}

// ── Visualization ──

export interface GraphNode {
  id: string;
  level: number;
  parallel_group: number;
}

export interface GraphEdge {
  from: string;
  to: string;
}

export interface WorkflowGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  levels: string[][];
  total_agents: number;
  total_levels: number;
}

export interface VisualizationResult {
  graph: WorkflowGraph;
  mermaid: string;
  critical_path: string[];
  critical_path_length: number;
}

// ── Health ──

export interface HealthStatus {
  status: string;
  uptime_seconds: number;
  redis_connected: boolean;
  agents_registered: number;
  active_workflows: number;
}
