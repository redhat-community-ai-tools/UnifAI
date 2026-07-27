/**
 * Hook for managing Redis-backed session stream subscription.
 * 
 * Implements the streaming pattern:
 * 1. POST /user.session.submit  ← fire & forget (returns 202 immediately)
 * 2. GET /session.stream.subscribe ← real-time events (NDJSON stream)
 * 
 * Features:
 * - Subscribes to Redis stream for live events + historical replay
 * - Automatically reconnects when user returns to an active session
 * - Handles stream lifecycle (heartbeat, stream_end, stream_error)
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { 
  getSessionStreamStatus, 
  subscribeToSessionStream, 
  submitSession,
  cancelSession,
  SubmitSessionParams,
  StreamStatusResponse 
} from '@/api/sessions';

/**
 * Stream event format from the subscribe API.
 * 
 * Events are returned directly as emitted by the node - no wrapper.
 * Format: {"node": "...", "display_name": "...", "type": "...", ...}
 * 
 * Special control events:
 * - {"type": "heartbeat"} - keep-alive signal
 * - {"type": "stream_end"} - session completed
 * - {"type": "stream_error", "error": "..."} - session failed
 */
export interface StreamEvent {
  node?: string;
  display_name?: string;
  type?: string;
  chunk?: string;
  state?: Record<string, any>;
  [key: string]: any;
}

export interface UseSessionStreamOptions {
  onChunk: (chunkData: any) => void;
  onStreamEnd?: () => void;
  onError?: (error: string) => void;
}

export interface UseSessionStreamReturn {
  isStreaming: boolean;
  isReconnecting: boolean;
  isSubmitting: boolean;
  streamStatus: StreamStatusResponse | null;
  lastEventId: string | null;
  /** Submit session for background execution and immediately subscribe to stream */
  submitAndSubscribe: (params: SubmitSessionParams) => Promise<void>;
  /** Check if session is active and reconnect if so */
  checkAndReconnect: (sessionId: string) => Promise<boolean>;
  /** Subscribe to an existing session's stream (replays all events from beginning) */
  subscribeToStream: (sessionId: string) => void;
  /** Cancel the current stream subscription (client-side only) */
  cancelStream: () => void;
  /** Cancel a session's backend execution via POST /session.cancel */
  cancelSessionExecution: (sessionId: string) => Promise<void>;
}

/**
 * Hook for managing Redis-backed session stream subscription.
 */
export function useSessionStream(options: UseSessionStreamOptions): UseSessionStreamReturn {
  const { onChunk, onStreamEnd, onError } = options;
  
  const [isStreaming, setIsStreaming] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [streamStatus, setStreamStatus] = useState<StreamStatusResponse | null>(null);
  const [lastEventId, setLastEventId] = useState<string | null>(null);
  
  const abortControllerRef = useRef<AbortController | null>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);
  const currentSessionIdRef = useRef<string | null>(null);
  
  // Store callbacks in refs to avoid dependency issues
  const onChunkRef = useRef(onChunk);
  const onStreamEndRef = useRef(onStreamEnd);
  const onErrorRef = useRef(onError);
  
  // Keep refs updated
  useEffect(() => {
    onChunkRef.current = onChunk;
    onStreamEndRef.current = onStreamEnd;
    onErrorRef.current = onError;
  }, [onChunk, onStreamEnd, onError]);
  
  /**
   * Cancel any active stream subscription.
   */
  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (readerRef.current) {
      readerRef.current.cancel().catch(() => {});
      readerRef.current = null;
    }
    setIsStreaming(false);
    currentSessionIdRef.current = null;
  }, []);
  
  /**
   * Subscribe to a session's Redis stream.
   * This runs asynchronously in the background - does not block.
   * 
   * The stream replays all events from the beginning, so clients that
   * connect late (or reconnect) receive the full history.
   */
  const subscribeToStream = useCallback((sessionId: string): void => {
    // Cancel any existing stream
    cancelStream();
    
    currentSessionIdRef.current = sessionId;
    abortControllerRef.current = new AbortController();
    
    // Run the subscription asynchronously
    (async () => {
      try {
        const response = await subscribeToSessionStream(sessionId);
        
        if (!response || !response.body) {
          console.warn('Stream subscription not available');
          return;
        }
        
        setIsStreaming(true);
        readerRef.current = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        while (true) {
          // Check if we've been cancelled
          if (currentSessionIdRef.current !== sessionId) {
            break;
          }
          
          const { value, done } = await readerRef.current.read();
          
          if (done) {
            break;
          }
          
          // Decode and process the chunk
          buffer += decoder.decode(value, { stream: true });
          
          // Process complete NDJSON lines
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer
          
          for (const line of lines) {
            if (!line.trim()) continue;
            
            try {
              const event = JSON.parse(line) as StreamEvent;
              
              // Handle heartbeat - now returned directly as {type: "heartbeat"}
              if (event.type === 'heartbeat') {
                continue;
              }
              
              // Handle stream end - now returned directly as {type: "stream_end"}
              if (event.type === 'stream_end') {
                setIsStreaming(false);
                onStreamEndRef.current?.();
                return;
              }
              
              // Handle stream error - now returned directly as {type: "stream_error", error: "..."}
              if (event.type === 'stream_error') {
                onErrorRef.current?.(event.error || 'Unknown stream error');
                setIsStreaming(false);
                return;
              }
              
              // Process the event data through the callback
              // Events are now returned directly in same format as execute API
              processEventData(event, onChunkRef.current);
            } catch (parseError) {
              console.warn('Failed to parse stream event:', line, parseError);
            }
          }
        }
        
        setIsStreaming(false);
        onStreamEndRef.current?.();
      } catch (err: any) {
        if (err.name === 'AbortError') {
          // Stream was cancelled - this is expected
          return;
        }
        console.error('Stream error:', err);
        onErrorRef.current?.(err.message || 'Stream error');
        setIsStreaming(false);
      } finally {
        if (currentSessionIdRef.current === sessionId) {
          setIsStreaming(false);
          readerRef.current = null;
        }
      }
    })();
  }, [cancelStream]);
  
  /**
   * Submit a session for background execution and immediately subscribe to the stream.
   * 
   * This is the primary method for new executions:
   * 1. POST /user.session.submit (fire & forget, returns 202)
   * 2. GET /session.stream.subscribe (real-time events)
   * 
   * @param params - Session submission parameters (sessionId, inputs, scope, userId)
   */
  const submitAndSubscribe = useCallback(async (params: SubmitSessionParams): Promise<void> => {
    // Cancel any existing stream
    cancelStream();
    setIsSubmitting(true);
    
    try {
      // Step 1: Submit session for background execution (fire & forget)
      await submitSession(params);
      
      // Step 2: Immediately subscribe to the stream
      // The backend starts writing to Redis, we start reading
      // Stream replays all events from the beginning automatically
      subscribeToStream(params.sessionId);
    } catch (err: any) {
      console.error('Error submitting session:', err);
      onErrorRef.current?.(err.message || 'Failed to submit session');
      throw err;
    } finally {
      setIsSubmitting(false);
    }
  }, [cancelStream, subscribeToStream]);
  
  /**
   * Check if a session has an active stream and reconnect if so.
   * Returns true if reconnection was initiated.
   * 
   * Note: This does NOT block on stream reading - the subscription runs
   * in the background. This allows the caller to continue without blocking.
   */
  const checkAndReconnect = useCallback(async (sessionId: string): Promise<boolean> => {
    // Cancel any existing stream subscription for the UI
    // (does not cancel backend execution - just switches which stream we're listening to)
    cancelStream();
    
    setIsReconnecting(true);
    
    try {
      const status = await getSessionStreamStatus(sessionId);
      setStreamStatus(status);
      
      if (status && status.is_active) {
        // Session is actively streaming - start subscription in background
        // Stream replays all events from the beginning automatically
        subscribeToStream(sessionId);
        setIsReconnecting(false);
        return true;
      }
      
      return false;
    } catch (err) {
      console.error('Error checking stream status:', err);
      return false;
    } finally {
      setIsReconnecting(false);
    }
  }, [cancelStream, subscribeToStream]);
  
  /**
   * Cancel a session's backend execution via POST /session.cancel.
   */
  const cancelSessionExecution = useCallback(async (sessionId: string): Promise<void> => {
    await cancelSession(sessionId);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cancelStream();
    };
  }, [cancelStream]);
  
  return {
    isStreaming,
    isReconnecting,
    isSubmitting,
    streamStatus,
    lastEventId,
    submitAndSubscribe,
    checkAndReconnect,
    subscribeToStream,
    cancelStream,
    cancelSessionExecution,
  };
}

/**
 * Process event data from Redis stream into the format expected by updateNodeList.
 * 
 * Per background-session-streaming.md, events are returned directly as emitted:
 * {"node": "orchestrator", "display_name": "Orchestrator Agent", "type": "progress", ...}
 * 
 * The format is transparent - exactly what the node emitted, no modification.
 */
function processEventData(data: any, onChunk: (chunkData: any) => void): void {
  if (!data) return;
  
  // Handle ["custom", {...}] format (LangGraph wrapper - for backwards compatibility)
  if (Array.isArray(data) && data[0] === 'custom' && data[1]) {
    onChunk(data[1]);
    return;
  }
  
  // Direct object format - the standard format per README
  // Events are returned exactly as emitted by the node
  if (typeof data === 'object') {
    // Skip terminal/control events - these are handled separately
    if (data.type === 'stream_end' || data.type === 'stream_error' || data.type === 'heartbeat') {
      return;
    }
    
    // Pass the event directly to the chunk handler
    // Expected fields: node, display_name, type (llm_token, complete, tool_calling, etc.)
    onChunk(data);
  }
}
