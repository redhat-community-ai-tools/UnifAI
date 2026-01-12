/**
 * Shared utilities for blueprint operations
 */

import React from 'react';
import { GraphFlow, FlowObject } from '@/components/agentic-ai/graphs/interfaces';
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
 * Convert GraphFlow to FlowObject
 */
export const convertGraphFlowToFlowObject = (
  graphFlow: GraphFlow,
  index: number,
  blueprintId?: string
): FlowObject | null => {
  if (!graphFlow) return null;

  // Extract metadata
  const name = graphFlow.name || `Flow ${index + 1}`;
  const description = graphFlow.description || 'No description available';

  // Generate a random icon for the flow
  const IconComponent = FLOW_ICON_OPTIONS[index % FLOW_ICON_OPTIONS.length];

  return {
    id: blueprintId || index.toString(),
    name,
    description,
    icon: <IconComponent className="h-4 w-4 mr-2" />,
    flow: {
      nodes: [],
      edges: [],
    },
  };
};

/**
 * Construct share link for a blueprint
 */
export const constructShareLink = (blueprintId: string): string => {
  return `${window.location.origin}/chat/${blueprintId}`;
};

