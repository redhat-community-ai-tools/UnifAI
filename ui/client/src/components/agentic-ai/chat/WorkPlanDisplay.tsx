import React, { memo, useCallback, useState } from 'react';
import { motion } from 'framer-motion';
import { 
  CheckCircle2, 
  Circle, 
  Clock, 
  AlertCircle, 
  ChevronDown, 
  ChevronRight,
  User,
  Timer,
  ArrowRight,
  MessageSquare,
  Bot
} from 'lucide-react';
import { WorkPlanSnapshot, WorkItem, WorkPlan, DelegationExchange } from './types';
import { getStatusConfig, formatTimestamp } from './WorkPlanDisplayHelpers';

interface WorkPlanDisplayProps {
  workPlanSnapshot: WorkPlanSnapshot;
  messageId: string;
  onToggleExpansion: (messageId: string, planId: string) => void;
}

interface WorkPlanItemProps {
  workPlan: WorkPlan;
  planId: string;
  action: string;
  isExpanded: boolean;
  onToggleExpansion: () => void;
}


// Individual delegation Q&A component
const DelegationItem: React.FC<{ delegation: DelegationExchange; index: number }> = memo(({ delegation, index }) => {
  const [isHovered, setIsHovered] = useState(false);
  
  const truncateText = (text: string, maxLength: number = 50) => {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.1 }}
      className="bg-gray-700/30 rounded-md p-3 border border-gray-600/50"
    >
      {/* Question */}
      <div className="flex items-start gap-2 mb-2">
        <div className="flex-shrink-0 mt-0.5">
          <MessageSquare className="h-3 w-3 text-blue-400" />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-xs font-medium text-blue-300">Q:</span>
          <p className="text-xs text-gray-200 mt-1 leading-relaxed">
            {delegation.query}
          </p>
        </div>
      </div>

      {/* Answer */}
      {delegation.response_content && (
        <div className="flex items-start gap-2">
          <div className="flex-shrink-0 mt-0.5">
            <Bot className="h-3 w-3 text-green-400" />
          </div>
          <div className="flex-1 min-w-0">
            <span className="text-xs font-medium text-green-300">A:</span>
            <div 
              className="text-xs text-gray-200 mt-1 leading-relaxed cursor-help relative"
              onMouseEnter={() => setIsHovered(true)}
              onMouseLeave={() => setIsHovered(false)}
            >
              <p>
                {isHovered ? delegation.response_content : truncateText(delegation.response_content)}
              </p>
              
              {/* Tooltip for full content */}
              {/* {isHovered && delegation.response_content.length > 50 && (
                <div className="absolute z-10 top-full left-0 mt-1 p-3 bg-gray-900 border border-gray-600 rounded-lg shadow-lg max-w-md text-xs text-gray-200 leading-relaxed">
                  {delegation.response_content}
                  <div className="absolute -top-1 left-3 w-2 h-2 bg-gray-900 border-l border-t border-gray-600 rotate-45"></div>
                </div>
              )} */}
            </div>
          </div>
        </div>
      )}

      {/* Metadata */}
      <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-2">
          <span>→ {delegation.delegated_to}</span>
          {delegation.sequence > 0 && (
            <span className="px-1.5 py-0.5 bg-purple-500/20 text-purple-300 rounded">
              Turn {delegation.sequence + 1}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {delegation.delegated_at && (
            <span>Asked: {formatTimestamp(delegation.delegated_at)}</span>
          )}
          {delegation.responded_at && (
            <span>Replied: {formatTimestamp(delegation.responded_at)}</span>
          )}
        </div>
      </div>
    </motion.div>
  );
});

// Delegations list component
const DelegationsList: React.FC<{ delegations: DelegationExchange[] }> = memo(({ delegations }) => {
  if (!delegations || delegations.length === 0) {
    return null;
  }

  // Sort by sequence to maintain conversation order
  const sortedDelegations = [...delegations].sort((a, b) => a.sequence - b.sequence);

  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-center gap-2">
        <MessageSquare className="h-3 w-3 text-gray-400" />
        <span className="text-xs font-medium text-gray-400">
          Agent Conversation ({delegations.length} exchange{delegations.length !== 1 ? 's' : ''})
        </span>
      </div>
      
      <div className="space-y-2">
        {sortedDelegations.map((delegation, index) => (
          <DelegationItem 
            key={delegation.task_id || `${delegation.sequence}-${index}`} 
            delegation={delegation} 
            index={index}
          />
        ))}
      </div>
    </div>
  );
});

// Individual work item component
const WorkItemCard: React.FC<{ item: WorkItem; isLast: boolean }> = memo(({ item, isLast }) => {
  const statusConfig = getStatusConfig(item.status);
  const StatusIcon = statusConfig.icon;
  const isCompleted = item.status === 'done';
  const isActive = item.status === 'in_progress';
  const hasFailed = item.status === 'failed';

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
      className={`relative flex items-start gap-3 p-3 rounded-lg border transition-all duration-200 ${statusConfig.bgColor} ${statusConfig.borderColor} ${
        isActive ? 'ring-1 ring-blue-400/50' : ''
      }`}
    >
      {/* Connection line to next item */}
      {!isLast && (
        <div 
          className="absolute left-6 top-10 w-0.5 h-6 bg-gray-600"
          style={{ transform: 'translateX(-50%)' }}
        />
      )}
      
      {/* Status icon */}
      <div className={`flex-shrink-0 mt-0.5 ${statusConfig.color}`}>
        <StatusIcon className="h-5 w-5" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <h4 className={`text-sm font-medium ${isCompleted ? 'line-through text-gray-400' : 'text-gray-100'}`}>
              {item.title}
            </h4>
            <p className="text-xs text-gray-400 mt-1 line-clamp-2">
              {item.description}
            </p>
          </div>
          
          {/* Item type and assignment badge */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* {item.kind === 'remote' && item.assigned_uid && (
              <div className="flex items-center gap-1 px-2 py-1 bg-purple-500/20 rounded-full">
                <User className="h-3 w-3 text-purple-400" />
                <span className="text-xs text-purple-300">{item.assigned_uid}</span>
              </div>
            )} */}
            {item.kind === 'local' && (
              <div className="flex items-center gap-1 px-2 py-1 bg-green-500/20 rounded-full">
                <Circle className="h-3 w-3 text-green-400" />
                <span className="text-xs text-green-300">local</span>
              </div>
            )}
          </div>
        </div>

        {/* Dependencies */}
        {item.dependencies.length > 0 && (
          <div className="mt-2 flex items-center gap-1 text-xs text-gray-500">
            <ArrowRight className="h-3 w-3" />
            <span>Depends on: {item.dependencies.join(', ')}</span>
          </div>
        )}

        {/* Error message */}
        {hasFailed && item.error && (
          <div className="mt-2 text-xs text-red-400 bg-red-900/20 rounded px-2 py-1">
            {item.error}
          </div>
        )}

        {/* Timing info */}
        <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
          <div className="flex items-center gap-1">
            <Timer className="h-3 w-3" />
            <span>Created: {formatTimestamp(item.created_at)}</span>
          </div>
          {item.updated_at !== item.created_at && (
            <span>Updated: {formatTimestamp(item.updated_at)}</span>
          )}
          {item.retry_count > 0 && (
            <span className="text-yellow-400">Retries: {item.retry_count}/{item.max_retries}</span>
          )}
        </div>

        {/* Delegations Q&A - Only show for REMOTE items with delegations */}
        {item.kind === 'remote' && item.result?.delegations && item.result.delegations.length > 0 && (
          <DelegationsList delegations={item.result.delegations} />
        )}
      </div>
    </motion.div>
  );
}, (prevProps, nextProps) => {
  const prevItem = prevProps.item;
  const nextItem = nextProps.item;
  
  // Focus on critical visual changes
  if (
    prevItem.id !== nextItem.id ||
    prevItem.status !== nextItem.status ||
    prevItem.title !== nextItem.title ||
    prevItem.description !== nextItem.description ||
    prevItem.error !== nextItem.error
  ) {
    return false;
  }
  
  // Check for delegation changes (for REMOTE items)
  if (prevItem.kind === 'remote' || nextItem.kind === 'remote') {
    const prevDelegationsLength = prevItem.result?.delegations?.length || 0;
    const nextDelegationsLength = nextItem.result?.delegations?.length || 0;
    
    // Re-render if delegation count changed or content changed
    if (prevDelegationsLength !== nextDelegationsLength) {
      return false;
    }
    
    // Check if any delegation content changed
    if (prevItem.result?.delegations && nextItem.result?.delegations) {
      const prevLastDelegation = prevItem.result.delegations[prevItem.result.delegations.length - 1];
      const nextLastDelegation = nextItem.result.delegations[nextItem.result.delegations.length - 1];
      
      if (prevLastDelegation?.response_content !== nextLastDelegation?.response_content
        //  || prevLastDelegation?.processed !== nextLastDelegation?.processed
        ) {
        return false;
      }
    }
  }
  
  return true; // Minimize re-renders for smoother 500ms updates
});

// Individual work plan component
const WorkPlanItem: React.FC<WorkPlanItemProps> = memo(({ 
  workPlan, 
  planId, 
  action, 
  isExpanded, 
  onToggleExpansion 
}) => {
  const workItems = Object.values(workPlan.items);
  const completedItems = workItems.filter(item => item.status === 'done').length;
  const failedItems = workItems.filter(item => item.status === 'failed').length;
  const inProgressItems = workItems.filter(item => item.status === 'in_progress').length;
  const totalItems = workItems.length;
  
  const progress = totalItems > 0 ? (completedItems / totalItems) * 100 : 0;
  const isComplete = completedItems === totalItems;
  const hasFailures = failedItems > 0;

  // Sort items by creation time for display
  const sortedItems = [...workItems].sort((a, b) => 
    new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  return (
    <div className="border border-gray-700 rounded-lg bg-gray-800/50 overflow-hidden">
      {/* Header */}
      <div 
        className="p-4 cursor-pointer hover:bg-gray-700/30 transition-colors"
        onClick={onToggleExpansion}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {isExpanded ? (
              <ChevronDown className="h-4 w-4 text-gray-400" />
            ) : (
              <ChevronRight className="h-4 w-4 text-gray-400" />
            )}
            <div>
              <h3 className="text-sm font-semibold text-gray-100">
                Orchestrator Plan
              </h3>
              <p className="text-xs text-gray-400 mt-1 line-clamp-2">
                {workPlan.summary}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Status badges */}
            <div className="flex items-center gap-2 text-xs">
              {inProgressItems > 0 && (
                <span className="flex items-center gap-1 text-blue-400">
                  <Clock className="h-3 w-3" />
                  {inProgressItems}
                </span>
              )}
              <span className="flex items-center gap-1 text-green-400">
                <CheckCircle2 className="h-3 w-3" />
                {completedItems}
              </span>
              {hasFailures && (
                <span className="flex items-center gap-1 text-red-400">
                  <AlertCircle className="h-3 w-3" />
                  {failedItems}
                </span>
              )}
            </div>
            
            {/* Progress bar */}
            <div className="w-16 h-2 bg-gray-600 rounded-full overflow-hidden">
              <div 
                className={`h-full transition-all duration-300 ${
                  isComplete ? 'bg-green-400' : hasFailures ? 'bg-red-400' : 'bg-blue-400'
                }`}
                style={{ width: `${progress}%` }}
              />
            </div>
            
            <span className="text-xs text-gray-400 min-w-fit">
              {completedItems}/{totalItems}
            </span>
          </div>
        </div>
      </div>

      {/* Expandable content - always rendered but controlled via CSS like StreamLogItem */}
      <div 
        className="border-t border-gray-700"
        style={{ 
          display: isExpanded ? 'block' : 'none',
          opacity: isExpanded ? 1 : 0
        }}
      >
        <div className="p-4 space-y-3">
          {sortedItems.map((item, index) => (
            <WorkItemCard 
              key={item.id} 
              item={item} 
              isLast={index === sortedItems.length - 1}
            />
          ))}
        </div>
      </div>
    </div>
  );
}, (prevProps, nextProps) => {
  // OPTIMIZED FOR 500ms WORKPLAN UPDATES: More conservative since updates are less frequent
  
  // Check expansion state change
  if (prevProps.isExpanded !== nextProps.isExpanded) {
    return false;
  }

  // Only re-render if plan summary changed (affects header display)
  if (prevProps.workPlan.summary !== nextProps.workPlan.summary) {
    return false;
  }
    
  const prevItems = Object.values(prevProps.workPlan.items);
  const nextItems = Object.values(nextProps.workPlan.items);
  
  // Check if item count changed (new items added/removed)
  if (prevItems.length !== nextItems.length) {
    return false;
  }
  
  // Check for critical status changes that affect visual state
  const prevCompleted = prevItems.filter(item => item.status === 'done').length;
  const nextCompleted = nextItems.filter(item => item.status === 'done').length;
  const prevFailed = prevItems.filter(item => item.status === 'failed').length;
  const nextFailed = nextItems.filter(item => item.status === 'failed').length;
  const prevInProgress = prevItems.filter(item => item.status === 'in_progress').length;
  const nextInProgress = nextItems.filter(item => item.status === 'in_progress').length;

  // Re-render if status counts changed (affects progress bar and badges)
  if (prevCompleted !== nextCompleted || prevFailed !== nextFailed || prevInProgress !== nextInProgress) {
    return false; 
  }
  
  // Otherwise, minimize re-renders for smoother 500ms update cycle
  return true; 
});

// Main component - now handles a single workplan like StreamLogItem
export const WorkPlanDisplay: React.FC<WorkPlanDisplayProps> = memo(({ workPlanSnapshot, messageId, onToggleExpansion }) => {
  const handleToggleExpansion = useCallback(() => {
    onToggleExpansion(messageId, workPlanSnapshot.plan_id);
  }, [messageId, workPlanSnapshot.plan_id, onToggleExpansion]);

  if (!workPlanSnapshot) {
    return null;
  }

  return (
    <WorkPlanItem
      workPlan={workPlanSnapshot.workplan}
      planId={workPlanSnapshot.plan_id}
      action={workPlanSnapshot.action}
      isExpanded={workPlanSnapshot.isExpanded}
      onToggleExpansion={handleToggleExpansion}
    />
  );
}, (prevProps, nextProps) => {
  // OPTIMIZED for 500ms workplan updates - more conservative comparison
  const prevSnapshot = prevProps.workPlanSnapshot;
  const nextSnapshot = nextProps.workPlanSnapshot;
  
  // Quick checks for structural changes
  if (
    prevSnapshot.plan_id !== nextSnapshot.plan_id ||
    prevProps.messageId !== nextProps.messageId ||
    prevSnapshot.isExpanded !== nextSnapshot.isExpanded
  ) {
    return false;
  }
  
  return true; // Minimize unnecessary re-renders
});

DelegationItem.displayName = 'DelegationItem';
DelegationsList.displayName = 'DelegationsList';
WorkItemCard.displayName = 'WorkItemCard';
WorkPlanItem.displayName = 'WorkPlanItem';
WorkPlanDisplay.displayName = 'WorkPlanDisplay';
