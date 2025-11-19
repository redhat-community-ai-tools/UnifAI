import React, { memo, useCallback } from 'react';
import { Cpu } from 'lucide-react';
import { Message } from './types';
import { StreamLogItem } from './StreamLogItem';
import { WorkPlanDisplay } from './WorkPlanDisplay';

interface StreamLogDisplayProps {
  message: Message;
  onToggleExpansion: (messageId: string, nodeId: string) => void;
  onToggleWorkPlanExpansion: (messageId: string, planId: string) => void;
}

export const StreamLogDisplay = memo(({ message, onToggleExpansion, onToggleWorkPlanExpansion }: StreamLogDisplayProps) => {
  const memoizedToggleExpansion = useCallback((messageId: string, nodeId: string) => {
    onToggleExpansion(messageId, nodeId);
  }, [onToggleExpansion]);

  const memoizedToggleWorkPlanExpansion = useCallback((messageId: string, planId: string) => {
    onToggleWorkPlanExpansion(messageId, planId);
  }, [onToggleWorkPlanExpansion]);

  const hasWorkPlans = message.workPlans && message.workPlans.length > 0;
  const hasStreamLogs = message.streamLogs && message.streamLogs.length > 0;

  if (!hasWorkPlans && !hasStreamLogs) {
    return null;
  }

  return (
    <div className="mt-3 space-y-3 w-full">
      {/* WorkPlans appear at the top - each treated as individual unit */}
      {hasWorkPlans && (
        <div className="space-y-3 mb-4">
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Cpu className="h-4 w-4" />
            <span>Execution Timeline</span>
          </div>
          {message.workPlans!.map((workPlanSnapshot) => (
            <WorkPlanDisplay
              key={workPlanSnapshot.plan_id}
              workPlanSnapshot={workPlanSnapshot}
              messageId={message.id}
              onToggleExpansion={memoizedToggleWorkPlanExpansion}
            />
          ))}
        </div>
      )}
      
      {/* Stream logs appear below workplans */}
      {hasStreamLogs && (
        <div className="space-y-2">
          {message.streamLogs!.map((log) => (
            <StreamLogItem
              key={log.nodeId}
              log={log}
              messageId={message.id}
              onToggleExpansion={memoizedToggleExpansion}
            />
          ))}
        </div>
      )}
    </div>
  );
}, (prevProps, nextProps) => {
  // Optimized comparison for memo
  const prevLogs = prevProps.message.streamLogs || [];
  const nextLogs = nextProps.message.streamLogs || [];
  const prevWorkPlans = prevProps.message.workPlans || [];
  const nextWorkPlans = nextProps.message.workPlans || [];
  
  // Check if message ID changed
  if (prevProps.message.id !== nextProps.message.id) {
    return false;
  }
  
  // Check if callback functions changed
  if (prevProps.onToggleExpansion !== nextProps.onToggleExpansion ||
      prevProps.onToggleWorkPlanExpansion !== nextProps.onToggleWorkPlanExpansion) {
    return false;
  }
  
  // Check for structural changes in stream logs (updated more frequently at 100ms)
  if (prevLogs.length !== nextLogs.length) {
    return false;
  }
  
  // Optimized comparison of streamLogs - focus on structural changes
  for (let i = 0; i < prevLogs.length; i++) {
    const prevLog = prevLogs[i];
    const nextLog = nextLogs[i];
    
    // Check critical properties that require re-render
    if (
      prevLog.nodeId !== nextLog.nodeId ||
      prevLog.status !== nextLog.status ||
      prevLog.isExpanded !== nextLog.isExpanded ||
      prevLog.nodeName !== nextLog.nodeName
    ) {
      return false;
    }
    
    // For message content, only re-render if it's not a streaming append
    if (prevLog.message !== nextLog.message) {
      // If the new message doesn't start with the old message, it's a replacement
      if (!nextLog.message.startsWith(prevLog.message)) {
        return false;
      }
    }
    
    // Check tools length (tools being added/removed)
    const prevTools = prevLog.tools || [];
    const nextTools = nextLog.tools || [];
    if (prevTools.length !== nextTools.length) {
      return false;
    }
  }
  
  // Check for workplan changes (now updated at 500ms intervals via separate state)
  if (prevWorkPlans.length !== nextWorkPlans.length) {
    return false;
  }
  
  // More conservative workplan comparison since updates are less frequent (500ms)
  for (let i = 0; i < prevWorkPlans.length; i++) {
    const prevPlan = prevWorkPlans[i];
    const nextPlan = nextWorkPlans[i];
    
    // Check essential structural changes that affect this container
    if (
      prevPlan.plan_id !== nextPlan.plan_id ||
      prevPlan.isExpanded !== nextPlan.isExpanded ||
      prevPlan.action !== nextPlan.action
    ) {
      return false;
    }
    
    // Quick check for workplan summary changes (affects header display)
    if (prevPlan.workplan.summary !== nextPlan.workplan.summary) {
      return false;
    }
    
    // Detailed work item comparison
    const prevItems = Object.values(prevPlan.workplan.items);
    const nextItems = Object.values(nextPlan.workplan.items);
    
    if (prevItems.length !== nextItems.length) {
      return false;
    }
    
    // Check each work item for meaningful changes to avoid unnecessary re-renders
    for (const nextItem of nextItems) {
      const prevItem = prevItems.find(item => item.id === nextItem.id);
      
      if (!prevItem) {
        return false;
      }
      
      // Check for meaningful changes in work item properties
      if (
        prevItem.status !== nextItem.status ||
        prevItem.title !== nextItem.title ||
        prevItem.description !== nextItem.description ||
        prevItem.error !== nextItem.error ||
        prevItem.retry_count !== nextItem.retry_count ||
        prevItem.kind !== nextItem.kind ||
        prevItem.assigned_uid !== nextItem.assigned_uid
      ) {
        return false;
      }
      
      // Check dependencies array changes
      if (prevItem.dependencies.length !== nextItem.dependencies.length ||
          !prevItem.dependencies.every((dep, idx) => dep === nextItem.dependencies[idx])) {
        return false;
      }
    }
  }
  
  return true;
});