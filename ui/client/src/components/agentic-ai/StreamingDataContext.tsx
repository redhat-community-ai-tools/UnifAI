// StreamingDataContext.tsx
import React, { createContext, useContext, useRef, useCallback } from 'react';
import type { NodeEntry, ApprovalStatus } from './chat/types';

export type { NodeEntry };

type StreamingContextType = {
  nodeListRef: React.MutableRefObject<Map<string, NodeEntry>>;
  forceUpdate: () => void;
  clearStream: () => void;
  updateApprovalStatus: (
    nodeUid: string,
    requestId: string,
    status: ApprovalStatus,
    feedback?: string,
  ) => void;
};

export const StreamingDataContext = createContext<StreamingContextType | null>(null);

export const StreamingDataProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const nodeListRef = useRef<Map<string, NodeEntry>>(new Map());
  const [, setTick] = React.useState(0);

  const forceUpdate = () => setTick(t => t + 1);

  const clearStream = () => {
    nodeListRef.current.clear();
    forceUpdate();
  };

  const updateApprovalStatus = useCallback(
    (nodeUid: string, requestId: string, status: ApprovalStatus, feedback?: string) => {
      for (const entry of nodeListRef.current.values()) {
        const approval = entry.approvals?.find((a) => a.requestId === requestId);
        if (approval) {
          approval.status = status;
          if (feedback) approval.feedback = feedback;
          forceUpdate();
          return;
        }
      }
    },
    [],
  );

  return (
    <StreamingDataContext.Provider
      value={{ nodeListRef, forceUpdate, clearStream, updateApprovalStatus }}
    >
      {children}
    </StreamingDataContext.Provider>
  );
};

export const useStreamingData = () => {
  const context = useContext(StreamingDataContext);
  if (!context) throw new Error('useStreamingData must be used within a StreamingDataProvider');
  return context;
};