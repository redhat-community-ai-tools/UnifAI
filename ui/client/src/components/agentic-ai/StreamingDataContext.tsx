// StreamingDataContext.tsx
import React, { createContext, useContext, useRef } from 'react';
import { NodeEntry } from './chat/types'

type StreamingContextType = {
  nodeListRef: React.MutableRefObject<Map<string, NodeEntry>>;
  forceUpdate: () => void;
  clearStream: () => void;
};

const StreamingDataContext = createContext<StreamingContextType | null>(null);

export const StreamingDataProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const nodeListRef = useRef<Map<string, NodeEntry>>(new Map());
  const [, setTick] = React.useState(0);

  const forceUpdate = () => setTick(t => t + 1);

  const clearStream = () => {
    nodeListRef.current.clear(); // Clears the stream
    forceUpdate();               // Triggers re-render if needed
  };

  return (
    <StreamingDataContext.Provider value={{ nodeListRef, forceUpdate, clearStream }}>
      {children}
    </StreamingDataContext.Provider>
  );
};

export const useStreamingData = () => {
  const context = useContext(StreamingDataContext);
  if (!context) throw new Error('useStreamingData must be used within a StreamingDataProvider');
  return context;
};