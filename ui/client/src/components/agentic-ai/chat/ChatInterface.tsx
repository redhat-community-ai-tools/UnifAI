import React, {
  useState,
  useRef,
  useEffect,
  useCallback,
  useMemo,
} from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Trash2, ChevronLeft, ChevronRight, Loader2, Sparkles, Info, Copy, RotateCcw, ThumbsUp, ThumbsDown, Check } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import axios from "../../../http/axiosAgentConfig";
import { MarkdownComponents, preprocessText } from "./helpers/TextComponents";
import { SessionPayload } from "../ExecutionTab";
import { useStreamingData } from "../StreamingDataContext";
import { Message, StreamLogEntry, WorkPlanSnapshot } from "./types";
import { StreamLogDisplay } from "./StreamLogDisplay";
import { useToast } from "@/hooks/use-toast";
import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';
import WorkflowStatusBanner, { WorkflowBannerMessages } from '@/components/shared/WorkflowStatusBanner';


// Backend message format
interface BackendMessage {
  content: string;
  role: "user" | "assistant";
}

interface ChatInterfaceProps {
  runId?: string;
  triggerExecution: (sessionPayload: SessionPayload) => Promise<string>;
  initialMessages?: BackendMessage[];
  blueprintExists?: boolean;
  isSharingDisabled?: boolean; // If true, sharing is disabled for this blueprint
  blueprintValid?: boolean;
  isValidatingBlueprint?: boolean;
  onToggleBlueprintGraph?: () => void;
  isBlueprintGraphHidden?: boolean;
  isChatOnlyMode?: boolean; // If true, hide agent thinking and workflow details
}

export default function ChatInterface({
  runId,
  triggerExecution,
  initialMessages = [],
  blueprintExists = true,
  isSharingDisabled = false,
  blueprintValid = true,
  isValidatingBlueprint = false,
  onToggleBlueprintGraph,
  isBlueprintGraphHidden = false,
  isChatOnlyMode = false,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [currentStreamingMessageId, setCurrentStreamingMessageId] = useState<
    string | null
  >(null);
  const [workPlanData, setWorkPlanData] = useState<Record<string, WorkPlanSnapshot[]>>({});
  const [streamLogData, setStreamLogData] = useState<Record<string, StreamLogEntry[]>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const streamingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const workplanStreamingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const workPlanDataRef = useRef<Record<string, WorkPlanSnapshot[]>>({});
  const streamLogDataRef = useRef<Record<string, StreamLogEntry[]>>({});
  const { nodeListRef, clearStream } = useStreamingData();
  const { toast } = useToast();
  const [userPromptsMap, setUserPromptsMap] = useState<Record<string, string>>({});
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);

  // Transform backend messages to frontend format (streamLogs/workPlans, managed separately)
  const transformBackendMessagesToFrontend = useCallback(
    (backendMessages: BackendMessage[]): Message[] => {
      return backendMessages.map((msg, index) => ({
        id: `${Date.now()}-${index}`,
        content: msg.content,
        sender: msg.role === "user" ? "user" : "ai",
        // For AI messages, we might want to add finalAnswer if it's the last assistant message
        ...(msg.role === "assistant" && {
          finalAnswer: msg.content,
        }),
      }));
    },
    [],
  );

  // Initialize messages from props or default
  useEffect(() => {
    if (initialMessages && initialMessages.length > 0) {
      const transformedMessages =
        transformBackendMessagesToFrontend(initialMessages);
      setMessages(transformedMessages);
    } else {
      // Default welcome message when no initial messages
      setMessages([
        {
          id: "welcome",
          content:
            "Hello! I'm your AI assistant. How can I help you process your data today?",
          sender: "ai",
        },
      ]);
    }
  }, [initialMessages, transformBackendMessagesToFrontend]);

  // useEffect(() => {
  //   scrollToBottom();
  // }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Map stream type to status
  const mapStreamToStatus = (
    stream: string,
  ): "processing" | "complete" | "error" => {
    switch (stream) {
      case "PROGRESS":
        return "processing";
      case "ERROR":
        return "error";
      case "COMPLETE":
        return "complete";
      default:
        return "processing";
    }
  };

  // Optimized streaming logic for stream logs using separate state (no messages updates)
  const startStreamingLogs = (messageId: string) => {
    if (streamingIntervalRef.current) {
      clearInterval(streamingIntervalRef.current);
    }

    let lastUpdateTime = 0;
    const UPDATE_THROTTLE = 100; // Update frequency to 100ms

    streamingIntervalRef.current = setInterval(() => {
      const now = Date.now();
      if (now - lastUpdateTime < UPDATE_THROTTLE) {
        return;
      }

      const list = Array.from(nodeListRef.current.values());

      if (list.length > 0) {
        lastUpdateTime = now;

        const currentLogs = streamLogDataRef.current[messageId] || [];
        const updatedStreamLogs: StreamLogEntry[] = [];

        // Process each entry from nodeListRef for stream logs only
        list.forEach((entry) => {
          // Process stream logs
          const existingLog = currentLogs.find(
            (log) => log.nodeId === entry.node_name,
          );

          // Only update if there's actually a change
          const newStatus = mapStreamToStatus(entry.stream);
          const newMessage = entry.text;

          if (
            !existingLog ||
            existingLog.status !== newStatus ||
            existingLog.message !== newMessage
          ) {
            // Show stream log if there's text content OR if there are tool calls
            if (newMessage || (entry?.tools && entry.tools.length > 0)) {
              updatedStreamLogs.push({
                nodeId: entry.node_name,
                nodeName: entry.node_name
                  .replace(/_/g, " ")
                  .replace(/\b\w/g, (l: string) => l.toUpperCase()),
                message: newMessage || "", // Allow empty message when showing tools
                tools: entry?.tools || [],
                status: newStatus,
                isExpanded: existingLog?.isExpanded || false,
              });
            }
          } else {
            // Keep existing log unchanged
            updatedStreamLogs.push(existingLog);
          }
        });

        // Only update if there are actual changes
        const hasLogChanges =
          updatedStreamLogs.length !== currentLogs.length ||
          updatedStreamLogs.some((log, index) => {
            const currentLog = currentLogs[index];
            return (
              !currentLog ||
              log.status !== currentLog.status ||
              log.message !== currentLog.message
            );
          });

        if (hasLogChanges) {
          // Update the ref and state
          streamLogDataRef.current = {
            ...streamLogDataRef.current,
            [messageId]: updatedStreamLogs
          };
          
          setStreamLogData(prev => ({
            ...prev,
            [messageId]: updatedStreamLogs
          }));
        }
      }
    }, 100); // Check every 100ms but only update every 300ms
  };

  // Separate streaming logic for workplans with 500ms intervals using dedicated state
  const startStreamingWorkPlans = (messageId: string) => {
    if (workplanStreamingIntervalRef.current) {
      clearInterval(workplanStreamingIntervalRef.current);
    }

    workplanStreamingIntervalRef.current = setInterval(() => {
      const list = Array.from(nodeListRef.current.values());

      if (list.length > 0) {
        const currentWorkPlans = workPlanDataRef.current[messageId] || [];
        const updatedWorkPlans: WorkPlanSnapshot[] = [];

        // Process each entry from nodeListRef for workplans only
        list.forEach((entry) => {
          // Process workplan data
          if (entry.workplans && entry.workplans.length > 0) {
            entry.workplans.forEach((workplanSnapshot: WorkPlanSnapshot) => {
              const existingPlanIndex = updatedWorkPlans.findIndex(
                (wp) => wp.plan_id === workplanSnapshot.plan_id
              );

              if (existingPlanIndex !== -1) {
                // Update existing workplan while preserving expansion state
                const existingPlan = updatedWorkPlans[existingPlanIndex];
                updatedWorkPlans[existingPlanIndex] = {
                  ...workplanSnapshot,
                  isExpanded: existingPlan.isExpanded // Preserve expansion state
                };
              } else {
                // Add new workplan with default expansion state
                updatedWorkPlans.push({
                  ...workplanSnapshot,
                  isExpanded: false // Default to collapsed
                });
              }
            });
          }
        });

        // Also preserve existing workplans that weren't updated
        currentWorkPlans.forEach((existingPlan) => {
          if (!updatedWorkPlans.find(wp => wp.plan_id === existingPlan.plan_id)) {
            updatedWorkPlans.push(existingPlan);
          }
        });

        // More precise workplan change detection to reduce flickering
        const hasPlanChanges = (() => {
          if (updatedWorkPlans.length !== currentWorkPlans.length) {
            return true; // Number of plans changed
          }

          for (const updatedPlan of updatedWorkPlans) {
            const currentPlan = currentWorkPlans.find(p => p.plan_id === updatedPlan.plan_id);
            
            if (!currentPlan) {
              return true; // New plan
            }

            // Check if plan-level properties changed
            if (updatedPlan.action !== currentPlan.action ||
                updatedPlan.workplan.summary !== currentPlan.workplan.summary) {
              return true;
            }

            // Check work items for meaningful changes
            const updatedItems = Object.values(updatedPlan.workplan.items);
            const currentItems = Object.values(currentPlan.workplan.items);

            if (updatedItems.length !== currentItems.length) {
              return true; // Number of items changed
            }

            // Check each item for status or content changes
            for (const updatedItem of updatedItems) {
              const currentItem = currentItems.find(item => item.id === updatedItem.id);
              
              if (!currentItem) {
                return true; // New item
              }

              // Only trigger update for meaningful changes
              if (
                currentItem.status !== updatedItem.status ||
                currentItem.title !== updatedItem.title ||
                currentItem.description !== updatedItem.description ||
                currentItem.error !== updatedItem.error ||
                currentItem.retry_count !== updatedItem.retry_count
              ) {
                return true;
              }
            }
          }

          return false; // No meaningful changes
        })();

        if (hasPlanChanges) {
          // Update the ref and state
          workPlanDataRef.current = {
            ...workPlanDataRef.current,
            [messageId]: updatedWorkPlans
          };
          
          setWorkPlanData(prev => ({
            ...prev,
            [messageId]: updatedWorkPlans
          }));
        }
      }
    }, 500); // Check every 500ms for workplans
  };

  // Stop streaming logs and workplans and mark all as complete
  const stopStreamingLogs = (messageId?: string) => {
    // Clear stream logs interval
    if (streamingIntervalRef.current) {
      clearInterval(streamingIntervalRef.current);
      streamingIntervalRef.current = null;
    }

    // Clear workplan streaming interval
    if (workplanStreamingIntervalRef.current) {
      clearInterval(workplanStreamingIntervalRef.current);
      workplanStreamingIntervalRef.current = null;
    }

    // Mark all processing nodes as complete when streaming stops
    const targetMessageId = messageId || currentStreamingMessageId;
    if (targetMessageId) {
      const currentLogs = streamLogDataRef.current[targetMessageId] || [];
      const updatedLogs = currentLogs.map((log) => ({
        ...log,
        status: log.status === "processing" ? "complete" : log.status,
      }));
      
      if (updatedLogs.length > 0) {
        streamLogDataRef.current = {
          ...streamLogDataRef.current,
          [targetMessageId]: updatedLogs
        };
        
        setStreamLogData(prev => ({
          ...prev,
          [targetMessageId]: updatedLogs
        }));
      }
    }
  };

  // Toggle expansion of a specific node log in separate state
  const toggleNodeExpansion = useCallback((messageId: string, nodeId: string) => {
    const currentLogs = streamLogDataRef.current[messageId] || [];
    const updatedLogs = currentLogs.map((log) =>
      log.nodeId === nodeId
        ? { ...log, isExpanded: !log.isExpanded }
        : log,
    );
    
    streamLogDataRef.current = {
      ...streamLogDataRef.current,
      [messageId]: updatedLogs
    };
    
    setStreamLogData(prev => ({
      ...prev,
      [messageId]: updatedLogs
    }));
  }, []);

  // Toggle expansion of a specific workplan in separate state
  const toggleWorkPlanExpansion = useCallback((messageId: string, planId: string) => {
    const currentPlans = workPlanDataRef.current[messageId] || [];
    const updatedPlans = currentPlans.map((plan) =>
      plan.plan_id === planId
        ? { ...plan, isExpanded: !plan.isExpanded }
        : plan,
    );
    
    workPlanDataRef.current = {
      ...workPlanDataRef.current,
      [messageId]: updatedPlans
    };
    
    setWorkPlanData(prev => ({
      ...prev,
      [messageId]: updatedPlans
    }));
  }, []);

  const getSessionState = async (sid: string) => {
    try {
      // Make API call to get the session state
      const response = await axios.get(
        `/session.state.get?sessionId=${sid}`,
      );
      const data = response.data;

      if (data && data.response) {
        return data.response;
      }

      return "I'm sorry, I couldn't retrieve a response for your query.";
    } catch (error) {
      console.error("Failed to get session state:", error);
      return "I'm sorry, I couldn't retrieve a response for your query.";
    }
  };

  // User sends message → Creates an AI message with empty streamLogs
  // Streaming starts → Interval polls for node updates and updates the message
  // Live updates → Each node appears/updates as data becomes available
  // User interaction → Can expand/collapse individual node logs
  // Completion → Final answer appears and streaming stops
  // Cleanup → All intervals are properly cleared
  const handleSendMessage = async (messageToSend?: string) => {
    const messageContent = messageToSend || inputMessage;
    if (messageContent.trim() === "") return;

    // Check if flow is loaded (runId should not be empty or null)
    if (!runId || runId.trim() === "") {
      toast({
        title: "No Flow Loaded",
        description: "You must load an existing flow before you can start chatting with the AI assistant.",
        variant: "destructive",
      });
      return;
    }

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      content: messageContent,
      sender: "user",
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage("");
    setIsTyping(true);

    // Reset textarea cursor to start position after clearing
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(0, 0);
      }
    }, 0);

    // Create initial AI message for streaming (no streamLogs, managed separately)
    const streamingMessageId = (Date.now() + 1).toString();
    const initialAiMessage: Message = {
      id: streamingMessageId,
      content: "",
      sender: "ai",
    };

    setMessages((prev) => [...prev, initialAiMessage]);
    clearStream();
    setCurrentStreamingMessageId(streamingMessageId);

    setUserPromptsMap(prev => ({
      ...prev,
      [streamingMessageId]: messageContent
    }));

    // Start streaming logs and workplans
    startStreamingLogs(streamingMessageId);
    startStreamingWorkPlans(streamingMessageId);

    try {
      const sessionPayload: SessionPayload = {
        sessionId: runId || "",
        inputs: { user_prompt: messageContent },
        stream: true,
        scope: "public",
        loggedInUser: "default",
      };

      const response = await triggerExecution(sessionPayload);

      // Update the message with final answer
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.id === streamingMessageId) {
            return {
              ...msg,
              finalAnswer: response,
            };
          }
          return msg;
        }),
      );
    } catch (error) {
      console.error("Error in chat interaction:", error);

      // Update with error message
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.id === streamingMessageId) {
            return {
              ...msg,
              finalAnswer:
                "I'm sorry, there was an error processing your request.",
            };
          }
          return msg;
        }),
      );
    } finally {
      setIsTyping(false);
      stopStreamingLogs(streamingMessageId);
      setCurrentStreamingMessageId(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { // Allow Shift+Enter for new lines
      e.preventDefault(); // Prevent default Enter behavior (new line)
      handleSendMessage();
    }
  };

  const clearChat = () => {
    setMessages([
      {
        id: "cleared",
        content: "Chat cleared. How can I help you with your data pipeline?",
        sender: "ai",
      },
    ]);
    // Clear both workplan and stream log data
    setWorkPlanData({});
    workPlanDataRef.current = {};
    setStreamLogData({});
    streamLogDataRef.current = {};
    setUserPromptsMap({});
    setCopiedMessageId(null);
    stopStreamingLogs();
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  // Clean up interval on unmount
  useEffect(() => {
    return () => {
      stopStreamingLogs();
    };
  }, []);

  // Memoized typing indicator
  const TypingIndicator = useMemo(
    () => (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex justify-start"
      >
        <div className="bg-background-dark border border-gray-800 rounded-2xl rounded-tl-none p-3 max-w-[80%]">
          {/* AI-generated indicator for typing state */}
          <div 
            className="mb-2.5 pb-2 border-b border-gray-700/30"
            role="status"
            aria-label="AI-generated content"
          >
            <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border" style={{ borderColor: `hsl(var(--primary) / 0.3)` }}>
              <Sparkles 
                className="h-3.5 w-3.5" 
                style={{ color: `hsl(var(--primary) / 0.85)` }}
                aria-hidden="true" 
              />
              <span className="text-xs font-medium text-gray-300/90 tracking-wide">
                AI Generated
              </span>
            </div>
          </div>
          <div className="flex space-x-1">
            <motion.div
              className="w-2 h-2 bg-gray-400 rounded-full"
              animate={{ y: [0, -5, 0] }}
              transition={{
                repeat: Infinity,
                duration: 0.5,
                ease: "easeInOut",
              }}
            />
            <motion.div
              className="w-2 h-2 bg-gray-400 rounded-full"
              animate={{ y: [0, -5, 0] }}
              transition={{
                repeat: Infinity,
                duration: 0.5,
                ease: "easeInOut",
                delay: 0.1,
              }}
            />
            <motion.div
              className="w-2 h-2 bg-gray-400 rounded-full"
              animate={{ y: [0, -5, 0] }}
              transition={{
                repeat: Infinity,
                duration: 0.5,
                ease: "easeInOut",
                delay: 0.2,
              }}
            />
          </div>
        </div>
      </motion.div>
    ),
    [],
  );

  // Loader for chat-only mode (simpler, cleaner loader)
  const ChatOnlyLoader = useMemo(
    () => (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex justify-start"
      >
        <div className="bg-background-dark border border-gray-800 rounded-2xl rounded-tl-none p-4 max-w-[80%]">
          <div className="flex items-center space-x-3">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <span className="text-sm text-gray-400">Processing your request...</span>
          </div>
        </div>
      </motion.div>
    ),
    [],
  );

  // Component for AI message action buttons
  const MessageActions = ({ message }: { message: Message }) => {
    const handleCopy = async () => {
      if (message.finalAnswer) {
        try {
          await navigator.clipboard.writeText(message.finalAnswer);
          setCopiedMessageId(message.id);
          setTimeout(() => setCopiedMessageId(null), 2000);
        } catch (error) {
          console.error("Failed to copy:", error);
          toast({
            title: "Copy failed",
            description: "Failed to copy to clipboard",
            variant: "destructive",
          });
        }
      }
    };

    const handleTryAgain = async () => {
      const originalPrompt = userPromptsMap[message.id];
      if (!originalPrompt) {
        toast({
          title: "Error",
          description: "Could not find original prompt",
          variant: "destructive",
        });
        return;
      }

      // Directly send the message with the original prompt
      await handleSendMessage(originalPrompt);
    };

    const isCopied = copiedMessageId === message.id;

    return (
      <div className="flex items-center gap-1 mt-2 pt-2 border-t border-gray-700/30">
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          disabled={!message.finalAnswer}
          className="h-7 px-2 text-gray-400 hover:text-gray-100 hover:bg-gray-800/50"
          title="Copy response"
        >
          {isCopied ? (
            <Check className="h-3.5 w-3.5 mr-1.5" />
          ) : (
            <Copy className="h-3.5 w-3.5 mr-1.5" />
          )}
          <span className="text-xs">{isCopied ? "Copied!" : "Copy"}</span>
        </Button>

        <Button
          variant="ghost"
          size="sm"
          onClick={handleTryAgain}
          disabled={!userPromptsMap[message.id] || isTyping}
          className="h-7 px-2 text-gray-400 hover:text-gray-100 hover:bg-gray-800/50"
          title="Try again with the same prompt"
        >
          <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
          <span className="text-xs">Try Again</span>
        </Button>

        <div className="flex-1" />

        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-gray-400 hover:text-green-400 hover:bg-gray-800/50"
          title="Good response"
        >
          <ThumbsUp className="h-3.5 w-3.5 mr-1.5" />
          <span className="text-xs">Good</span>
        </Button>

        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-gray-400 hover:text-red-400 hover:bg-gray-800/50"
          title="Bad response"
        >
          <ThumbsDown className="h-3.5 w-3.5 mr-1.5" />
          <span className="text-xs">Bad</span>
        </Button>
      </div>
    );
  };

  // Component for rendering message content with markdown support
  const MessageContent = ({ message }: { message: Message }) => {
    // Get stream logs and workplans from separate states
    const streamLogs = streamLogData[message.id] || [];
    const workPlans = workPlanData[message.id] || [];

    // Memoize the complete message object with separate data
    const messageWithStreamingData = useMemo(() => {
      // Create enhanced message object only when needed
      if (streamLogs.length > 0 || workPlans.length > 0) {
        return {
          ...message,
          streamLogs: streamLogs,
          workPlans: workPlans
        };
      }
      
      return message;
    }, [message, streamLogs, workPlans]);

    if (message.sender === "user") {
      return (
        <div className="text-sm whitespace-pre-line">{message.content}</div>
      );
    }

    if (
      message.sender === "ai" &&
      (streamLogs.length > 0 || workPlans.length > 0 || message.finalAnswer)
    ) {
      return (
        <div className="space-y-3 w-full">
          {/* Stream logs display - hidden in chat-only mode */}
          {!isChatOnlyMode && (
            <StreamLogDisplay
              message={messageWithStreamingData}
              onToggleExpansion={toggleNodeExpansion}
              onToggleWorkPlanExpansion={toggleWorkPlanExpansion}
            />
          )}

          {/* Final answer with markdown rendering */}
          {message.finalAnswer && (
            <div
              className="mt-3 p-3 rounded-lg"
              style={{
                // backgroundColor: `hsl(var(--primary) / 0.1)`,
                border: `1px solid hsl(var(--primary) / 0.3)`,
              }}
            >
              <div className="text-sm text-gray-100">
                <ReactMarkdown
                  components={MarkdownComponents}
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                >
                  {preprocessText(message.finalAnswer)}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      );
    }

    // Default AI message without streaming
    return (
      <div className="text-sm">
        <ReactMarkdown
          components={MarkdownComponents}
          remarkPlugins={[remarkGfm, remarkBreaks]}
        >
          {preprocessText(message.content)}
        </ReactMarkdown>
      </div>
    );
  };

  return (
    <Card className="bg-background-card shadow-card border-gray-800 flex flex-col h-full max-h-[82.5vh]">
      <CardHeader className="py-4 px-6 flex flex-row justify-between items-center flex-shrink-0">
        <CardTitle className="text-lg font-heading">AI Assistant</CardTitle>
        <div className="flex space-x-2">
          {!isChatOnlyMode && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={clearChat}
                className="text-gray-400 hover:text-gray-100"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
              {onToggleBlueprintGraph && !isChatOnlyMode && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onToggleBlueprintGraph}
                  className="text-gray-400 hover:text-gray-100"
                  title={isBlueprintGraphHidden ? "Show Blueprint Graph" : "Hide Blueprint Graph"}
                >
                  {isBlueprintGraphHidden ? (
                    <ChevronLeft className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </Button>
              )}
            </>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden p-0 flex flex-col min-h-0">
        <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
          <AnimatePresence>
            {messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className={`flex ${message.sender === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[90%] rounded-2xl p-3 ${
                    message.sender === "user"
                      ? "bg-primary text-white rounded-tr-none"
                      : "bg-background-dark border border-gray-800 rounded-tl-none"
                  }`}
                >
                  {/* AI-generated indicator inside message bubble */}
                  {message.sender === "ai" && (
                    <div 
                      className="mb-2.5 pb-2 border-b border-gray-700/30"
                      role="status"
                      aria-label="AI-generated content"
                    >
                      <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border" style={{ borderColor: `hsl(var(--primary) / 0.3)` }}>
                        <Sparkles 
                          className="h-3.5 w-3.5" 
                          style={{ color: `hsl(var(--primary) / 0.85)` }}
                          aria-hidden="true" 
                        />
                        <span className="text-xs font-medium text-gray-300/90 tracking-wide">
                          AI Generated
                        </span>
                      </div>
                    </div>
                  )}
                  <MessageContent message={message} />
                  {/* Action buttons for AI messages */}
                  {message.sender === "ai" && message.finalAnswer && (
                    <MessageActions message={message} />
                  )}
                </div>
              </motion.div>
            ))}
            {isTyping && (isChatOnlyMode ? ChatOnlyLoader : TypingIndicator)}
          </AnimatePresence>
          <div ref={messagesEndRef} />
        </div>
        <div className="p-4 border-t border-gray-800 flex-shrink-0">
          {/* Status banners - priority order: deleted > sharing disabled > invalid > validating */}
          {!blueprintExists && (
            <WorkflowStatusBanner {...WorkflowBannerMessages.deleted} />
          )}
          {blueprintExists && isSharingDisabled && (
            <WorkflowStatusBanner {...WorkflowBannerMessages.sharingDisabled} />
          )}
          {blueprintExists && !isSharingDisabled && !blueprintValid && !isValidatingBlueprint && (
            <WorkflowStatusBanner {...WorkflowBannerMessages.validationFailed} />
          )}
          {blueprintExists && !isSharingDisabled && isValidatingBlueprint && (
            <WorkflowStatusBanner {...WorkflowBannerMessages.validating} />
          )}
          
          {/* Input area */}
          <div className="flex space-x-2 items-end">
            <Textarea
              ref={textareaRef}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                !blueprintExists 
                  ? "This chat cannot be continued - workflow was deleted" 
                  : isSharingDisabled
                    ? "Chat sharing has been disabled for this workflow"
                    : isValidatingBlueprint
                      ? "Validating workflow..."
                      : !blueprintValid 
                        ? "This chat cannot be continued - workflow validation failed" 
                        : "Ask a question about your data..."
              }
              className={`bg-background-dark min-h-[80px] resize-none ${(!blueprintExists || isSharingDisabled || !blueprintValid || isValidatingBlueprint) ? 'opacity-50 cursor-not-allowed' : ''}`}
              rows={3}
              disabled={!blueprintExists || isSharingDisabled || !blueprintValid || isValidatingBlueprint}
            />
            <UmamiTrack 
              event={UmamiEvents.AGENT_CHAT_SEND_MESSAGE_BUTTON}
            >
              <Button
                onClick={() => handleSendMessage()}
                disabled={inputMessage.trim() === "" || isTyping || !blueprintExists || isSharingDisabled || !blueprintValid || isValidatingBlueprint}
                className="bg-primary hover:bg-[#7525c9] mb-0"
              >
                <Send className="h-4 w-4" />
              </Button>
            </UmamiTrack>
          </div>
          <div className="flex items-start gap-2 mt-2 px-1">
            <Info className="h-3.5 w-3.5 text-gray-400 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-gray-500">
              AI agent responses may be inaccurate or incomplete. Verify important information.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}