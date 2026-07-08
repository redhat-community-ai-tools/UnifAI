export interface SessionError extends Error {
  sessionStatus?: string;
}

export function createSessionError(message: string, sessionStatus: string): SessionError {
  const error = new Error(message) as SessionError;
  error.sessionStatus = sessionStatus;
  return error;
}

export function isSessionCancellation(error: unknown): boolean {
  return (error as SessionError)?.sessionStatus === 'CANCELLED';
}

export interface Message {
  id: string;
  content: string;
  sender: 'user' | 'ai';
  senderName?: string;
  finalAnswer?: string;
  isCancelled?: boolean;
  streamLogs?: StreamLogEntry[];
  workPlans?: WorkPlanSnapshot[];
}

export interface StreamLogEntry {
  nodeId: string;
  nodeName: string;
  message: string;
  tools?: ToolEntry[];
  approvals?: ApprovalEntry[];
  status: 'processing' | 'complete' | 'error';
  isExpanded: boolean;
}

export interface ToolEntry {
  id: string;
  name: string;
  args?: Record<string, any>;
  output?: string;
}

// ─── HITL Approval Types ────────────────────────────────────────────────────

export type ApprovalDecision = 'approve' | 'reject' | 'modify' | 'redirect';
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'modified' | 'redirected' | 'timed_out';
export type AutoRuleAction = 'auto_approve' | 'auto_reject';

export interface ApprovalEntry {
  requestId: string;
  toolName: string;
  toolArgs: Record<string, any>;
  toolDescription: string;
  accessMode: string;
  originNodeUid: string;
  originNodeName: string;
  status: ApprovalStatus;
  feedback?: string;
}

// ─── Node Entry (shape used by StreamingDataContext nodeListRef) ─────────────

export interface NodeEntry {
  node_name: string;
  node_uid: string;
  stream: 'PROGRESS' | 'DONE' | 'ERROR';
  text: string;
  tools: ToolEntry[];
  workplans: WorkPlanSnapshot[];
  approvals: ApprovalEntry[];
}

// WorkPlan Types based on the streaming guide
export interface WorkPlanSnapshot {
  type: 'workplan_snapshot';
  action: 'loaded' | 'saved' | 'deleted';
  plan_id: string;
  thread_id: string;
  owner_uid: string;
  node?: string;
  display_name?: string;
  workplan: WorkPlan;
  isExpanded: boolean; // Add expansion state for performance optimization
}

export interface WorkPlan {
  summary: string;
  owner_uid: string;
  thread_id: string;
  items: Record<string, WorkItem>;
  created_at: string;
  updated_at: string;
}

export interface WorkItem {
  id: string;
  title: string;
  description: string;
  kind: 'local' | 'remote';
  status: 'pending' | 'in_progress' | 'done' | 'failed';
  dependencies: string[];
  assigned_uid: string | null;
  tool: string | null;
  args: Record<string, any>;
  result: WorkItemResult | null;
  error: string | null;
  child_thread_id: string | null;
  retry_count: number;
  max_retries: number;
  created_at: string;
  updated_at: string;
}

export interface WorkItemResult {
  delegations: DelegationExchange[];
  local_execution: LocalExecution | null;
  success: boolean;
  final_summary: string | null;
  data: any | null;
  metadata: Record<string, any>;
  artifacts: string[];
}

export interface DelegationExchange {
  sequence: number;
  task_id: string;
  query: string;
  delegated_to: string;
  delegated_at: string;
  response_content: string | null;
  response_data: any | null;
  responded_by: string | null;
  responded_at: string | null;
  processed: boolean;
}

export interface LocalExecution {
  outcome: string;
  executed_at: string;
}