/**
 * Shared utilities for blueprint operations
 */

import React from 'react';
import { FlowObject } from '@/components/agentic-ai/graphs/interfaces';
import {
  Activity,
  Database,
  FileText,
  Zap,
  Filter,
  GitBranch,
  MessageSquare,
  BookOpen,
} from 'lucide-react';

/**
 * Minimal flow metadata required to create a FlowObject
 */
export interface FlowMetadata {
  name?: string;
  description?: string;
  contributedBy?: string;
}

/**
 * Icon options for flows
 */
export const FLOW_ICON_OPTIONS: React.FC<{ className?: string }>[] = [
  Activity,
  Database,
  FileText,
  Zap,
  Filter,
  GitBranch,
  MessageSquare,
  BookOpen,
];

/**
 * Convert flow metadata to FlowObject.
 * Accepts any object with name/description (GraphFlow, BlueprintSummary, etc.)
 */
export const convertGraphFlowToFlowObject = (
  flowData: FlowMetadata,
  index: number,
  blueprintId?: string
): FlowObject | null => {
  if (!flowData) return null;

  // Extract metadata
  const name = flowData.name || `Flow ${index + 1}`;
  const description = flowData.description || 'No description available';

  // Generate a random icon for the flow
  const IconComponent = FLOW_ICON_OPTIONS[index % FLOW_ICON_OPTIONS.length];

  return {
    id: blueprintId || index.toString(),
    name,
    description,
    icon: <IconComponent className="h-4 w-4 mr-2" />,
    contributedBy: flowData.contributedBy,
  };
};

/**
 * Construct share link for a blueprint
 */
export const constructShareLink = (blueprintId: string): string => {
  return `${window.location.origin}/chat/${blueprintId}`;
};

/**
 * Node types that do not support file attachments in chat.
 * These agents have no file-attachment consumption code on the backend.
 */
const FILE_UPLOAD_UNSUPPORTED_NODE_TYPES = [
  'deep_agent_node',
  'claude_agent_node',
  'a2a_agent_node',
] as const;

/**
 * Determine whether a blueprint supports file upload based on its node types.
 * Returns false if any node in the blueprint uses an unsupported agent type.
 */
export function blueprintSupportsFileUpload(specDict: any): boolean {
  const raw = specDict?.nodes;
  const nodes: any[] = Array.isArray(raw) ? raw : [];
  return !nodes.some(
    (n) => FILE_UPLOAD_UNSUPPORTED_NODE_TYPES.includes(n.type ?? n.config?.type)
  );
}

