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

