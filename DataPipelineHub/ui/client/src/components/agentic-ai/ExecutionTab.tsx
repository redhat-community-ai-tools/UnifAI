import React, { useState, useEffect, useCallback } from "react";
import * as Switch from '@radix-ui/react-switch';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, Users, Clock, ArrowUpRight, SplitSquareVertical, Trash2, Plus, X } from "lucide-react";
import ChatInterface from "./chat/ChatInterface";
import ExecutionStream from "./ExecutionStream";
import ReactFlowGraph from "./graphs/ReactFlowGraph";
import { GraphNode } from "../../pages/AgenticAI"
import axios from '../../http/axiosAgentConfig'
import { useStreamingData } from './StreamingDataContext'
import { EnhancedStreamReader } from '@/components/shared/stream/StreamJsonParser'
import { useAuth } from "@/contexts/AuthContext";
import AvailableFlows from "./AvailableFlows";
import { ReactFlowProvider } from "reactflow";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  CustomDialogContent,
} from "@/components/ui/dialog";
import { GraphFlow, FlowObject } from "./graphs/interfaces";

// Types for the API response
interface ChatMessage {
  content: string;
  role: 'user' | 'assistant';
}

interface ChatSessionData {
  metadata: Record<string, any>;
  blueprint_id: string;
  session_id: string;
  started_at: string;
  blueprint_exists: boolean;
}

interface SessionStateData {
  final_output: string;
  messages: ChatMessage[];
}

interface ChatSession {
  id: string;
  blueprintId: string;
  title: string;
  lastActive: string;
  timestamp: Date;
  preview: string;
  messages: ChatMessage[];
  blueprintExists: boolean;
}

export type SessionPayload = {
  sessionId: string;
  inputs: {"user_prompt": string},
  stream: boolean,
  scope: 'public' | 'private';
  loggedInUser: string;
};

type ExecutionTabProps = {
  runId: string | null;
};


type ChunkData = {
  node: string;
  display_name: string;
  type: 'llm_token' | 'complete' | 'tool_calling' | 'tool_result' | 'workplan_snapshot';
  chunk?: string;
  tool?: string;
  output?: string;
  call_id?: string;
  args?: Record<string, any>;
  state?: {
    user_prompt?: string;
  };
  // WorkPlan specific fields
  action?: 'loaded' | 'saved' | 'deleted';
  plan_id?: string;
  thread_id?: string;
  owner_uid?: string;
  workplan?: any; // Will contain the full workplan data
};

export default function ExecutionTab({
  runId
}: ExecutionTabProps): React.ReactElement {
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<ChatSession | null>(null);
  const [currentSessionMessages, setCurrentSessionMessages] = useState<ChatMessage[]>([]);
  const [showExecutionStream, setShowExecutionStream] = useState(false);
  const [isActiveChatSession, setIsActiveChatSession] = useState(true);
  const [isLiveRequest, setIsLiveRequest] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [globalScope, setGlobalScope] = useState<'public' | 'private'>('public');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [chatToDelete, setChatToDelete] = useState<ChatSession | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showAddFlowModal, setShowAddFlowModal] = useState(false);
  const [selectedFlowForModal, setSelectedFlowForModal] = useState<FlowObject | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [isLoadingFlowsForModal, setIsLoadingFlowsForModal] = useState(false);
  // Three panel widths: Available Chats, ChatInterface, Blueprint Graph
  const [chatSidebarWidth, setChatSidebarWidth] = useState(20);
  const [chatInterfaceWidth, setChatInterfaceWidth] = useState(50);
  const [blueprintGraphWidth, setBlueprintGraphWidth] = useState(30);
  const [isResizing, setIsResizing] = useState(false);
  const [activeResizer, setActiveResizer] = useState<'left' | 'right' | null>(null);

  const { nodeListRef, forceUpdate } = useStreamingData();
  const { user } = useAuth();

  // Resizable panel handlers
  const handleMouseDown = (resizer: 'left' | 'right') => (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    setActiveResizer(resizer);
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing || !activeResizer) return;
    
    const containerRect = document.querySelector('.resizable-container')?.getBoundingClientRect();
    if (!containerRect) return;

    const mousePosition = ((e.clientX - containerRect.left) / containerRect.width) * 100;
    
    if (activeResizer === 'left') {
      // Resizing between Available Chats and ChatInterface
      const minChatSidebar = 15;
      const maxChatSidebar = 35;
      const newChatSidebarWidth = Math.min(Math.max(mousePosition, minChatSidebar), maxChatSidebar);
      const remainingWidth = 100 - newChatSidebarWidth;
      const newChatInterfaceWidth = (chatInterfaceWidth / (chatInterfaceWidth + blueprintGraphWidth)) * remainingWidth;
      const newBlueprintGraphWidth = remainingWidth - newChatInterfaceWidth;
      
      setChatSidebarWidth(newChatSidebarWidth);
      setChatInterfaceWidth(newChatInterfaceWidth);
      setBlueprintGraphWidth(newBlueprintGraphWidth);
    } else if (activeResizer === 'right') {
      // Resizing between ChatInterface and Blueprint Graph
      const availableWidth = 100 - chatSidebarWidth;
      const relativePosition = ((mousePosition - chatSidebarWidth) / availableWidth) * 100;
      const minChatInterface = 25;
      const maxChatInterface = 100; // Allow Blueprint Graph to collapse to 0%
      const newChatInterfaceRatio = Math.min(Math.max(relativePosition, minChatInterface), maxChatInterface);
      
      const newChatInterfaceWidth = (availableWidth * newChatInterfaceRatio) / 100;
      const newBlueprintGraphWidth = availableWidth - newChatInterfaceWidth;
      
      setChatInterfaceWidth(newChatInterfaceWidth);
      setBlueprintGraphWidth(newBlueprintGraphWidth);
    }
  }, [isResizing, activeResizer, chatSidebarWidth, chatInterfaceWidth, blueprintGraphWidth]);

  const handleMouseUp = useCallback(() => {
    setIsResizing(false);
    setActiveResizer(null);
  }, []);

  // Add event listeners for mouse move and up
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
    } else {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
    };
  }, [isResizing, handleMouseMove, handleMouseUp]);

  // Utility functions
  const generateRandomId = (): string => {
    return `chat-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  };

  const generateRandomTitle = (index: number): string => {
    return `Chat ${index + 1}`;
  };

  const formatTimestamp = (timestamp: string): string => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInMs = now.getTime() - date.getTime();
    const diffInMinutes = Math.floor(diffInMs / (1000 * 60));
    const diffInHours = Math.floor(diffInMinutes / 60);
    const diffInDays = Math.floor(diffInHours / 24);

    if (diffInMinutes < 60) {
      return `${diffInMinutes} min ago`;
    } else if (diffInHours < 24) {
      return `${diffInHours} hour${diffInHours > 1 ? 's' : ''} ago`;
    } else if (diffInDays < 7) {
      return `${diffInDays} day${diffInDays > 1 ? 's' : ''} ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  const handleGlobalScopeToggle = () => {
    setGlobalScope(prevScope => prevScope === 'public' ? 'private' : 'public');
  };

  const getPreviewText = (messages: ChatMessage[]): string => {
    const userMessage = messages.find(msg => msg.role === 'user');
    if (userMessage && userMessage.content) {
      return userMessage.content.length > 50
        ? `${userMessage.content.substring(0, 50)}...`
        : userMessage.content;
    }
    return 'No message content available';
  };

  const transformApiDataToSessions = (apiData: ChatSessionData[]): ChatSession[] => {
    return apiData.map((sessionData, index) => {
      const title = sessionData.metadata?.title || generateRandomTitle(index);
      const id = sessionData.session_id || generateRandomId();
      const blueprintId = sessionData.blueprint_id;
      const blueprintExists = sessionData.blueprint_exists;
      const timestamp = new Date(sessionData.started_at);
      const lastActive = formatTimestamp(sessionData.started_at);
      const preview = 'Click to load messages...';
      
      return {
        id,
        blueprintId,
        title,
        lastActive,
        timestamp,
        preview,
        messages: [], // Messages will be loaded separately when session is selected
        blueprintExists,  
      };
    });
  };

  // Fetch session state (messages) for a specific session
  const fetchSessionState = async (sessionId: string): Promise<SessionStateData | null> => {
    try {
      const response = await axios.get(`/sessions/session.state.get?sessionId=${sessionId}`);
      return response.data;
    } catch (err) {
      console.error('Error fetching session state:', err);
      return null;
    }
  };

  // Fetch chat sessions from API
  const fetchChatSessions = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const userId = user?.username || "default";
      const response = await axios.get(`/sessions/session.user.chat.get?userId=${userId}`);
      const transformedSessions = transformApiDataToSessions(response.data);

      // sort chat sessions based on the latest date
      const sortedSessions = transformedSessions.sort((firstSession, secondSession) => secondSession.timestamp.getTime() - firstSession.timestamp.getTime());
      setChatSessions(sortedSessions);

      // Auto-select the first session if available and fetch its state
      if (sortedSessions.length > 0 && !selectedSession) {
        const firstSession = sortedSessions[0];
        setSelectedSession(firstSession);
        
        // Fetch the state for the first session
        const stateData = await fetchSessionState(firstSession.id);
        if (stateData && stateData.messages) {
          setCurrentSessionMessages(stateData.messages);
          
          // Update the session's preview with actual message content
          const updatedSession = {
            ...firstSession,
            messages: stateData.messages,
            preview: getPreviewText(stateData.messages)
          };
          setSelectedSession(updatedSession);
          
          // Update the session in the list as well
          setChatSessions(prevSessions => 
            prevSessions.map(s => s.id === firstSession.id ? updatedSession : s)
          );
        }
      }
    } catch (err) {
      console.error('Error fetching chat sessions:', err);
      setError('Failed to load chat sessions');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle session selection
  const handleSessionSelect = async (session: ChatSession) => {
    setSelectedSession(session);
    
    // If messages are already loaded for this session, use them
    if (session.messages && session.messages.length > 0) {
      setCurrentSessionMessages(session.messages);
    } else {
      // Otherwise, fetch the session state
      const stateData = await fetchSessionState(session.id);
      if (stateData && stateData.messages) {
        setCurrentSessionMessages(stateData.messages);
        
        // Update the session with loaded messages and preview
        const updatedSession = {
          ...session,
          messages: stateData.messages,
          preview: getPreviewText(stateData.messages)
        };
        setSelectedSession(updatedSession);
        
        // Update the session in the list as well
        setChatSessions(prevSessions => 
          prevSessions.map(s => s.id === session.id ? updatedSession : s)
        );
      }
    }
  };

  // Handle delete chat
  const handleDeleteChat = (session: ChatSession, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent session selection when clicking delete
    setChatToDelete(session);
    setShowDeleteModal(true);
  };

  const confirmDeleteChat = async () => {
    if (!chatToDelete) return;

    setIsDeleting(true);
    try {
      const userId = user?.username || "default";
      await axios.delete(`/sessions/session.delete?sessionId=${chatToDelete.id}`);

      // Remove the deleted session from the list
      setChatSessions(prevSessions => prevSessions.filter(session => session.id !== chatToDelete.id));

      // If the deleted session was selected, clear the selection
      if (selectedSession?.id === chatToDelete.id) {
        setSelectedSession(null);
        setCurrentSessionMessages([]);
      }

      setShowDeleteModal(false);
      setChatToDelete(null);
    } catch (error) {
      console.error('Error deleting chat session:', error);
      // Handle error (you might want to show a toast notification here)
    } finally {
      setIsDeleting(false);
    }
  };

  const cancelDeleteChat = () => {
    setShowDeleteModal(false);
    setChatToDelete(null);
  };

  // Handle add flow modal
  const handleAddFlowClick = () => {
    setShowAddFlowModal(true);
  };

  const handleFlowSelect = (flow: FlowObject | null): void => {
    setSelectedFlowForModal(flow);
  };

  const handleAddFlow = async () => {
    if (!selectedFlowForModal) return;

    setIsCreatingSession(true);
    try {
      const graphId = selectedFlowForModal.id || `graph-${Date.now()}`;

      const selectedBlueprint = {
        blueprintId: graphId,
        userId: user?.username || "default",
      };

      const response = await axios.post(
        "/sessions/user.session.create",
        selectedBlueprint,
      );

      await fetchChatSessions();

      // Auto-select the newly created session
      // Wait a bit for state to update, then find the newest session with matching blueprintId
      setTimeout(() => {
        setChatSessions(prevSessions => {
          const newestSession = prevSessions.find(session => session.blueprintId === graphId);
          if (newestSession) {
            setSelectedSession(newestSession);
            setCurrentSessionMessages(newestSession.messages);
          }
          return prevSessions; // Return unchanged sessions
        });
      }, 100);

      setShowAddFlowModal(false);
      setSelectedFlowForModal(null);
    } catch (error) {
      console.error("Error creating new graph session:", error);
    } finally {
      setIsCreatingSession(false);
    }
  };

  const handleCancelAddFlow = () => {
    setShowAddFlowModal(false);
    setSelectedFlowForModal(null);
    // Force a small delay to ensure proper cleanup of ReactFlow state
    setTimeout(() => {
      // This timeout helps ensure the modal ReactFlow instance is properly unmounted
      // before potentially affecting other ReactFlow instances
    }, 100);
  };

  // Initialize component with API call
  useEffect(() => {
    fetchChatSessions();
  }, []);

  // Cleanup effect when modal closes to prevent ReactFlow state interference
  useEffect(() => {
    if (!showAddFlowModal && selectedFlowForModal) {
      // Reset selected flow when modal closes to ensure clean state
      setSelectedFlowForModal(null);
    }
  }, [showAddFlowModal]);

  // Tracks each node's streaming state.
  // Aggregates chunks per node.
  // Marks a node as DONE when a type: "complete" event is received for it.
  // Cleanly handles streaming via ReadableStream.
  // This follows clean architecture, maintains readability, and ensures correctness even in noisy or unpredictable stream outputs.
  // Extracts multiple well-formed ["custom", {...}] chunks from the stream text.
  const parseStreamChunk = (chunk: string): any[] => {
    const parsedChunks: any[] = [];
    const pattern = /\["custom",\s*(\{.*?\})\]/g;
    let match: RegExpExecArray | null;

    while ((match = pattern.exec(chunk)) !== null) {
      try {
        const json = JSON.parse(match[1]);
        parsedChunks.push(json);
      } catch (e) {
        console.warn("Failed to parse stream JSON chunk:", match[1]);
      }
    }

    return parsedChunks;
  };

  // Maintains and updates a list of nodes and their stream state (PROGRESS or DONE) while aggregating text.
  const updateNodeList = (chunkData: ChunkData) => {
    const { node, display_name, type, chunk, state, tool, output, call_id, args, action, plan_id, thread_id, owner_uid, workplan } = chunkData;
    const currentText = chunk ?? state?.user_prompt ?? '';
    const map = nodeListRef.current;

    let existing = map.get(node);

    // Initialize the node entry if it doesn't exist
    if (!existing) {
      existing = {
        node_name: display_name,
        node_uid: node,
        stream: type === 'complete' ? 'DONE' : 'PROGRESS',
        text: '',
        tools: [],
        workplans: [],
      };
      map.set(node, existing);
    }

    switch (type) {
      case 'llm_token':
        if (chunk) {
          existing.text += chunk;
        }
        break;

      // case 'complete':
      //   existing.stream = 'DONE';
      //   if (state?.user_prompt && existing.text.trim() === '') {
      //     existing.text = state.user_prompt;
      //   }
      //   break;

      case 'tool_calling':
        if (call_id && tool) {
          const existingTool = existing.tools?.find((t: any) => t.id === call_id);
          if (!existingTool) {
            existing.tools?.push({ id: call_id, name: tool, args });
          }
        }
        break;

      case 'tool_result':
        if (call_id && tool && output) {
          const toolEntry = existing.tools?.find((t: any) => t.id === call_id);
          if (toolEntry) {
            toolEntry.output = output;
          } else {
            existing.tools?.push({ id: call_id, name: tool, output });
          }
        }
        break;

      case 'workplan_snapshot':
        if (plan_id && workplan && action) {
          // Initialize workplans array if it doesn't exist
          if (!existing.workplans) {
            existing.workplans = [];
          }

          // Create the workplan snapshot
          const workplanSnapshot = {
            type: 'workplan_snapshot' as const,
            action: action as 'loaded' | 'saved' | 'deleted',
            plan_id: plan_id,
            thread_id: thread_id || '',
            owner_uid: owner_uid || node,
            node: node,
            display_name: display_name,
            workplan: workplan
          };

          // Find existing workplan or add new one
          const existingPlanIndex = existing.workplans.findIndex(
            (wp: any) => wp.plan_id === plan_id
          );

          if (existingPlanIndex !== -1) {
            // Update existing workplan
            existing.workplans[existingPlanIndex] = workplanSnapshot;
          } else {
            // Add new workplan
            existing.workplans.push(workplanSnapshot);
          }
        }
        break;

      default:
        break;
    }

    // forceUpdate(); // Uncomment if needed to trigger a re-render
  };

  // Reads the stream, decodes it, parses chunks, and updates state cleanly.
  const triggerExecution = async (sessionPayload: SessionPayload) => {
    let streamReader: EnhancedStreamReader | null = null;

    try {
      setIsLiveRequest(true);
      const payloadWithScope = {
        ...sessionPayload,
        scope: globalScope,
        loggedInUser: user?.username || "default",
      };

      const response = await fetch(`/api2/sessions/user.session.execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payloadWithScope),
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      if (!response.body) throw new Error('ReadableStream not supported!');

      // Create stream reader with chunk processing callback
      streamReader = new EnhancedStreamReader((chunkData: any) => {
        updateNodeList(chunkData);
        // console.log(JSON.stringify(Array.from(nodeListRef.current.entries()), null, 2));
      });

      // Read the entire stream
      await streamReader.readStream(response);

      console.log('Streaming completed.');
      console.log('Final Node List:', nodeListRef.current);
    } catch (error) {
      console.error('Error communicating with chat API', error);

      // Cancel stream reading if there was an error
      if (streamReader) {
        await streamReader.cancel();
      }
    } finally {
      setIsLiveRequest(false);

      try {
        const session_response = await axios.get(
          `/sessions/session.state.get?sessionId=${sessionPayload.sessionId}`
        );
        return session_response.data.output;
      } catch (error) {
        console.error('Error fetching session state:', error);
        throw error;
      }
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex justify-center items-center h-64">
          <div className="text-gray-400">Loading chat sessions...</div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex justify-center items-center h-64">
          <div className="text-red-400">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-heading font-semibold">AI Assistant</h2>
          <p className="text-sm text-gray-400 mt-1">
            Interact with your AI assistant and monitor execution details
          </p>
        </div>
        <Button
          className={`flex items-center gap-2 ${isActiveChatSession ? "bg-[#03DAC6] hover:bg-opacity-80" : "bg-gray-700 text-gray-300 cursor-not-allowed"}`}
          onClick={() => setShowExecutionStream(!showExecutionStream)}
          disabled={!isActiveChatSession}
        >
          <SplitSquareVertical className="h-4 w-4" />
          {showExecutionStream ? "Hide" : "Open"} Execution Stream
        </Button>
      </div>

      <div className="flex resizable-container gap-0" style={{ height: "calc(100vh - 230px)" }}>
        {/* Available Chats Sidebar - Dynamic width */}
        <div className="flex-shrink-0" style={{ width: `${chatSidebarWidth}%` }}>
          <Card className="bg-background-card shadow-card border-gray-800 h-full flex flex-col mr-0">
            <CardHeader className="py-3 px-4 border-b border-gray-800 overflow-hidden">
              <div className="flex justify-between items-center min-w-0 w-full max-w-full">
                <CardTitle className="text-sm font-medium truncate flex-1 min-w-0 mr-2">
                  Available Chats ({chatSessions.length})
                </CardTitle>
                <div className="flex items-center gap-1 flex-shrink-0 max-w-fit">
                  {/* Global Scope Toggle */}
                  <Switch.Root
                    className="relative w-20 h-5 rounded-full bg-gray-600 data-[state=checked]:bg-[#03DAC6] transition-colors cursor-pointer flex-shrink-0"
                    checked={globalScope === 'public'}
                    onCheckedChange={handleGlobalScopeToggle}
                    id="scope-switch"
                    title={`Current scope: ${globalScope}`}
                  >
                    {/* Background label */}
                    <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-white pointer-events-none select-none">
                      {globalScope === 'public' ? 'Public' : 'Private'}
                    </span>

                    {/* Switch thumb */}
                    <Switch.Thumb
                      className="absolute top-[1px] left-[1px] h-4 w-4 rounded-full bg-white transition-transform duration-300 z-10 transform data-[state=checked]:translate-x-[60px]"
                    />
                  </Switch.Root>
                  <Button variant="ghost" size="sm" className="h-6 w-6 p-0 flex-shrink-0">
                    <Users className="h-3 w-3" />
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="h-6 w-6 p-0 text-[#03DAC6] hover:bg-[#03DAC6] hover:bg-opacity-20 flex-shrink-0" 
                    onClick={handleAddFlowClick}
                    title="Add new chat from flow"
                  >
                    <Plus className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0 flex-grow">
              {chatSessions.length === 0 ? (
                <div className="p-4 text-center text-gray-400 text-sm">
                  No chat sessions availableﬂ
                </div>
              ) : (
                <div className="h-full max-h-[75vh] overflow-y-auto py-2">
                  {chatSessions.map((session) => (
                    <motion.div
                      key={session.id}
                      className={`group px-4 py-3 border-l-2 cursor-pointer ${
                        selectedSession?.id === session.id
                          ? "border-[hsl(var(--primary))] bg-primary/20"
                          : "border-transparent hover:bg-background-surface"
                      } ${
                        !session.blueprintExists 
                          ? "opacity-50 bg-gray-800/30" 
                          : ""
                      }`}
                      onClick={() => handleSessionSelect(session)}
                      whileHover={{ x: 2 }}
                      transition={{ duration: 0.1 }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center min-w-0 flex-1">
                          <MessageSquare className="h-4 w-4 mr-2 text-gray-400 flex-shrink-0" />
                          <span className="text-sm font-medium truncate">
                            {session.title}
                          </span>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0 text-gray-400 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => handleDeleteChat(session, e)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                      <div className="mt-1 flex items-center text-xs text-gray-400">
                        <Clock className="h-3 w-3 mr-1" />
                        <span>{session.lastActive}</span>
                      </div>
                      <p className="mt-1 text-xs text-gray-500 truncate">
                        {session.preview}
                      </p>
                    </motion.div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* First Resizable divider */}
        <div
          className={`w-1 cursor-col-resize transition-colors duration-200 flex-shrink-0 ${
            isResizing && activeResizer === 'left' ? 'opacity-100' : 'opacity-50'
          }`}
          style={{
            backgroundColor: 'hsl(var(--primary))',
          }}
          onMouseDown={handleMouseDown('left')}
          title="Drag to resize panels"
        />

        {/* ChatInterface Area - Dynamic width */}
        <div className="flex-shrink-0 flex flex-col" style={{ width: `${chatInterfaceWidth}%` }}>
          <div className="flex-grow">
            <ChatInterface
              runId={selectedSession?.id || ''}
              triggerExecution={triggerExecution}
              initialMessages={currentSessionMessages}
              blueprintExists={selectedSession?.blueprintExists ?? true}
            />
          </div>
          
          {/* ExecutionStream - conditionally rendered within ChatInterface area */}
          {selectedSession && showExecutionStream && (
            <div className="h-1/3 border-t border-gray-800 mt-2">
              <ExecutionStream
                blueprintId={selectedSession.blueprintId}
                isLiveRequest={isLiveRequest}
              />
            </div>
          )}
        </div>

        {/* Second Resizable divider */}
        <div
          className={`w-1 cursor-col-resize transition-colors duration-200 flex-shrink-0 ${
            isResizing && activeResizer === 'right' ? 'opacity-100' : 'opacity-50'
          }`}
          style={{
            backgroundColor: 'hsl(var(--primary))',
          }}
          onMouseDown={handleMouseDown('right')}
          title="Drag to resize panels"
        />

        {/* Blueprint Graph Visualization - Dynamic width */}
        <div className="flex-shrink-0" style={{ width: `${blueprintGraphWidth}%` }}>
          <Card className="bg-background-card shadow-card border-gray-800 h-full flex flex-col ml-0">
            {/* TODO: Add below general component that gets 'blueprintId' and showing his title and uid - can be called from multiple places */}
            {/* <CardHeader className="py-3 px-4 border-b border-gray-800">
              {selectedSession && (
                  <div className="mb-4 px-4 py-3 bg-[#8A2BE2] bg-opacity-10 border border-[hsl(var(--primary))] rounded-md">
                    <p className="text-sm">
                      <span className="font-medium">Active Graph:</span> {''} <span className="text-xs text-gray-400 ml-2">(ID: {selectedSession.blueprintId || 'N/A'})</span>
                    </p>
                  </div>
                )}
              {selectedSession && (
                <p className="text-xs text-gray-400 mt-1">
                  Blueprint ID: {selectedSession.blueprintId || 'N/A'}
                </p>
              )}
            </CardHeader> */}
            <CardContent className="p-0 flex-grow">
              {selectedSession?.blueprintId ? (
                <ReactFlowProvider key={`main-graph-${selectedSession.blueprintId}`}>
                  <ReactFlowGraph
                    blueprintId={selectedSession.blueprintId}
                    height="100%"
                    showControls={true}
                    showMiniMap={false}
                    showBackground={true}
                    interactive={true}
                    isLiveRequest={isLiveRequest}
                  />
                </ReactFlowProvider>
              ) : (
                <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                  {selectedSession ? 'No blueprint available for this session' : 'Select a chat session to view blueprint'}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Add Flow Modal */}
      <Dialog open={showAddFlowModal} onOpenChange={setShowAddFlowModal}>
        <CustomDialogContent 
          className="bg-background-card border-gray-800 max-w-[95vw] w-[95vw] h-[85vh] max-h-[85vh] flex flex-col overflow-hidden"
        >
          <DialogHeader className="flex-shrink-0 pb-4">
            <DialogTitle className="text-lg">Add New Chat from Flow</DialogTitle>
          </DialogHeader>
          <div className="flex-1 min-h-0 overflow-hidden">
            <ReactFlowProvider key={`new-chat-graph-${showAddFlowModal}`}>
              <AvailableFlows
                selectedFlow={selectedFlowForModal}
                onFlowSelect={handleFlowSelect}
                showActiveStatus={false}
                showDeleteButton={false}
                height="100%"
                graphProps={{
                  showControls: true,
                  showMiniMap: true,
                  showBackground: true,
                  interactive: true,
                  isLiveRequest: false,
                }}
              />
            </ReactFlowProvider>
          </div>
          <DialogFooter className="flex-shrink-0 pt-4 border-t border-gray-800">
            <Button
              variant="outline"
              onClick={handleCancelAddFlow}
              disabled={isCreatingSession}
              className="bg-background-dark border-gray-700 hover:bg-background-surface"
            >
              Cancel
            </Button>
            <Button
              onClick={handleAddFlow}
              disabled={!selectedFlowForModal || isCreatingSession}
              className="bg-[#03DAC6] hover:bg-opacity-80 text-black"
            >
              {isCreatingSession ? "Creating..." : "Add"}
            </Button>
          </DialogFooter>
        </CustomDialogContent>
      </Dialog>

      {/* Delete Chat Confirmation Modal */}
      <AlertDialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
        <AlertDialogContent className="bg-background-card border-gray-800">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Chat</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{chatToDelete?.title}"?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel 
              onClick={cancelDeleteChat}
              className="bg-background-dark border-gray-700 hover:bg-background-surface"
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDeleteChat}
              disabled={isDeleting}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}