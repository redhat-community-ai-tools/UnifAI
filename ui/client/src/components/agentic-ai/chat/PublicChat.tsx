import React, { useState, useEffect, useCallback } from "react";
import { useRoute } from "wouter";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import ChatInterface from "@/components/agentic-ai/chat/ChatInterface";
import { SessionPayload } from "@/components/agentic-ai/ExecutionTab";
import { StreamingDataProvider } from "@/components/agentic-ai/StreamingDataContext";
import { Loader2, MessageSquare, Clock, Plus, Trash2, LogOut } from "lucide-react";
import WorkflowStatusBanner, { WorkflowBannerMessages } from "@/components/shared/WorkflowStatusBanner";
import { motion } from "framer-motion";
import SimpleTooltip from "@/components/shared/SimpleTooltip";
import { useTheme } from "@/contexts/ThemeContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
import { usePublicChat } from "@/hooks/use-public-chat";
import { getBlueprintInfo, validateBlueprint } from "@/api/blueprints";
import { UmamiTrack } from "@/components/ui/umamitrack";
import { UmamiEvents } from "@/config/umamiEvents";

export default function PublicChat() {
  const [, params] = useRoute("/chat/:token");
  const token = params?.token;
  const { user, isAuthenticated, isLoading: authLoading, logout } = useAuth();
  const { toast } = useToast();
  const { primaryHex } = useTheme();
  
  const [blueprintId, setBlueprintId] = useState<string | null>(null);
  const [blueprintName, setBlueprintName] = useState<string>("");
  const [blueprintOwner, setBlueprintOwner] = useState<string>("");
  const [isValidating, setIsValidating] = useState(true);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isSharingDisabled, setIsSharingDisabled] = useState<boolean>(false);
  const [isBlueprintValid, setIsBlueprintValid] = useState<boolean>(true);
  const [isValidatingBlueprint, setIsValidatingBlueprint] = useState<boolean>(false);

  // Use the custom hook for chat management
  const {
    sessions: chatSessions,
    selectedSession,
    isLoading: isLoadingSessions,
    isCreatingSession,
    isDeleting,
    chatHistory,
    runId,
    handleNewChat,
    handleSessionSelect,
    handleDeleteChat,
    confirmDeleteChat,
    cancelDeleteChat,
    triggerExecution,
    showDeleteModal,
    setShowDeleteModal,
    chatToDelete,
  } = usePublicChat(blueprintId);

  // Check sharing status for the blueprint using getBlueprintInfo (usageScope is part of metadata)
  const checkSharingStatus = useCallback(async (blueprintId: string) => {
    try {
      const blueprintInfo = await getBlueprintInfo(blueprintId);
      const isPublic = blueprintInfo.metadata?.usageScope === "public";
      setIsSharingDisabled(!isPublic);
    } catch (error: any) {
      // If status check fails, assume sharing is disabled
      setIsSharingDisabled(true);
    }
  }, []);

  // Check blueprint validity
  const checkBlueprintValidity = useCallback(async (blueprintId: string, showLoadingState: boolean = true) => {
    if (showLoadingState) {
      setIsValidatingBlueprint(true);
    }
    try {
      const result = await validateBlueprint({ blueprintId });
      setIsBlueprintValid(result.is_valid);
      if (!result.is_valid && showLoadingState) {
        // Only set validation error on initial load, not during polling
        setValidationError("Sorry, this workflow has validation errors and cannot be used. Please contact the workflow owner.");
      }
    } catch (error: any) {
      console.error("Error validating blueprint:", error);
      // If validation fails, allow the chat to proceed but mark as potentially invalid
      setIsBlueprintValid(true); // Don't block on validation errors
    } finally {
      if (showLoadingState) {
        setIsValidatingBlueprint(false);
      }
    }
  }, []);

  // Validate token and get blueprint info
  useEffect(() => {
    if (!token) {
      setIsValidating(false);
      return;
    }

    const validateToken = async () => {
      try {
        // Get blueprint info (includes usageScope in metadata)
        const blueprintInfo = await getBlueprintInfo(token);
        setBlueprintId(token);
        setBlueprintName(blueprintInfo.spec_dict?.name || "Unnamed Workflow");
        setBlueprintOwner(blueprintInfo.user_id || "");
        
        // Check sharing status from the same blueprintInfo response (no extra API call)
        const isPublic = blueprintInfo.metadata?.usageScope === "public";
        if (!isPublic) {
          setValidationError("Sorry, this workflow is not available for chats");
          setIsSharingDisabled(true);
        } else {
          setIsSharingDisabled(false);
          // Also check blueprint validity
          await checkBlueprintValidity(token);
        }
      } catch (error: any) {
        if (error.response?.status === 404) {
          const errorMsg = error.response?.data?.error || "This workflow doesn't exist";
          setValidationError(errorMsg);
        } else {
          setValidationError("Failed to validate chat link");
        }
      } finally {
        setIsValidating(false);
      }
    };

    validateToken();
  }, [token, checkSharingStatus, checkBlueprintValidity]);


  // Load chat sessions when authenticated and blueprint is available
  useEffect(() => {
    if (isAuthenticated && user && blueprintId) {
      // Check sharing status and blueprint validity initially and periodically (every 30 seconds)
      // This polling handles scenarios where:
      // 1. The workflow owner DISABLES sharing while another user has the chat open
      // 2. The workflow becomes invalid (e.g., missing credentials, broken connections)
      // Without polling, users would continue chatting but get confusing errors.
      // With polling, they'll see clear messages within 30 seconds of changes.
      checkSharingStatus(blueprintId);
      checkBlueprintValidity(blueprintId, false);
      const interval = setInterval(() => {
        checkSharingStatus(blueprintId);
        checkBlueprintValidity(blueprintId, false);
      }, 30000);
      
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, user, blueprintId, checkSharingStatus, checkBlueprintValidity]);

  // Show loading state
  if (authLoading || isValidating) {
    return (
      <div className="flex items-center justify-center h-screen bg-background-dark">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  // Show invalid link
  if (!blueprintId || validationError) {
    return (
      <div className="flex items-center justify-center h-screen bg-background-dark">
        <div className="text-center">
          <p className="text-white mb-2">Invalid Chat Link</p>
          <p className="text-gray-400 text-sm">
            {validationError || "This chat link is no longer valid or has been disabled"}
          </p>
        </div>
      </div>
    );
  }


  return (
    <div className="flex flex-col h-screen bg-background-dark">
      {/* Header with Unifai branding and user info */}
      <div className="bg-background-card border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-md bg-gradient-to-r from-primary to-gray-500 flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M3 12H7M17 12H21M12 3V7M12 17V21M5 19L8 16M16 8L19 5M19 19L16 16M5 5L8 8" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <h1 className="text-xl font-bold text-white">UnifAI</h1>
          </div>
          <div className="h-6 w-px bg-gray-700" />
          <div className="flex items-center">
            <p className="text-sm text-gray-400">{blueprintName}</p>
            {blueprintOwner && (
              <span className="text-xs text-gray-500 ml-2">(workflow shared by {blueprintOwner})</span>
            )}
          </div>
        </div>
        
        {/* User Profile with Logout - matching regular UnifAI header */}
        <div className="px-4 py-3 border-l border-gray-800">
          <div className="flex items-center space-x-3">
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
              style={{ background: `linear-gradient(90deg, #6B7280, ${primaryHex || '#8A2BE2'})` }}
            >
              <span className="text-sm font-medium text-white">
                {user?.name
                  ?.split(' ')
                  .filter(Boolean)
                  .map(part => part[0].toUpperCase())
                  .join('') || user?.username?.[0].toUpperCase() || 'U'}
              </span>
            </div>
            
            <motion.div
              initial={false}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
              className="flex-grow"
            >
              <h4 className="text-sm font-medium text-white">{user?.name || user?.username || "User"}</h4>
            </motion.div>
            
            <motion.div
              initial={false}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
            >
              <SimpleTooltip content={<p>Sign out</p>}>
                <button 
                  onClick={logout}
                  className="mt-2 text-gray-400 hover:text-white transition-colors"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </SimpleTooltip>
            </motion.div>
          </div>
        </div>
      </div>

      {/* Main Content Area with Sidebar */}
      <div className="flex-1 overflow-hidden flex">
        {/* Chat History Sidebar */}
        <div className="w-80 border-r border-gray-800 bg-background-card flex flex-col flex-shrink-0">
          <Card className="bg-background-card shadow-card border-0 h-full flex flex-col">
            <CardHeader className="py-3 px-4 border-b border-gray-800">
              <div className="flex justify-between items-center">
                <CardTitle className="text-sm font-medium">
                  Chat History ({chatSessions.length})
                </CardTitle>
                <UmamiTrack event={UmamiEvents.PUBLIC_CHAT_NEW_SESSION}>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 text-primary hover:bg-primary/20"
                    onClick={handleNewChat}
                    disabled={isCreatingSession}
                    title="Start new chat"
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </UmamiTrack>
              </div>
            </CardHeader>
            <CardContent className="p-0 flex-grow overflow-y-auto">
              {isLoadingSessions ? (
                <div className="p-4 text-center">
                  <Loader2 className="h-5 w-5 animate-spin mx-auto text-primary" />
                </div>
              ) : chatSessions.length === 0 ? (
                <div className="p-4 text-center text-gray-400 text-sm">
                  No chat sessions yet. Click + to start a new chat.
                </div>
              ) : (
                <div className="py-2">
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
                          <span className="text-sm font-medium truncate text-white">
                            {session.title}
                          </span>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0 text-gray-400 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
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

        {/* Chat Interface */}
        <div className="flex-1 overflow-hidden">
          {!runId ? (
            isLoadingSessions ? (
              <div className="flex items-center justify-center h-full bg-background-dark">
                <div className="text-center">
                  <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
                  <p className="text-gray-400">Loading chat sessions...</p>
                </div>
              </div>
            ) : !isBlueprintValid ? (
              <div className="flex items-center justify-center h-full bg-background-dark">
                <div className="max-w-md">
                  <WorkflowStatusBanner
                    variant={WorkflowBannerMessages.validationFailed.variant}
                    title={WorkflowBannerMessages.validationFailed.title}
                    message={WorkflowBannerMessages.validationFailed.message}
                  />
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full bg-background-dark">
                <div className="text-center">
                  <MessageSquare className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                  <p className="text-gray-400">Select a chat session or start a new one</p>
                </div>
              </div>
            )
          ) : (
            <StreamingDataProvider>
              <ChatInterface
                runId={runId}
                triggerExecution={triggerExecution}
                initialMessages={chatHistory}
                blueprintExists={true}
                isSharingDisabled={isSharingDisabled}
                blueprintValid={isBlueprintValid}
                isValidatingBlueprint={isValidatingBlueprint}
                isBlueprintGraphHidden={true}
                isChatOnlyMode={true}
              />
            </StreamingDataProvider>
          )}
        </div>
      </div>

      {/* Delete Chat Confirmation Modal */}
      <AlertDialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
        <AlertDialogContent className="bg-background-card border-gray-800">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Chat</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{chatToDelete?.title}"? This action cannot be undone.
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