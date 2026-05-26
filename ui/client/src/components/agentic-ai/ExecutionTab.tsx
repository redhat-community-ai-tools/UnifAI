import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { motion } from "framer-motion";
import { MessageSquare, Users, Clock, Trash2, Plus, Columns3, Network } from "lucide-react";
import ChatInterface from "./chat/ChatInterface";
import ExecutionStream from "./ExecutionStream";
import GraphDisplay from "./graphs/GraphDisplay";
import WorkflowsPanel from "./WorkflowsPanel";
import {
  Dialog,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  CustomDialogContent,
} from "@/components/ui/dialog";
import { FlowObject } from "./graphs/interfaces";
import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';
import { useSessionHub } from "@/hooks/use-session-hub";

/**
 * Session execution payload (fire-and-forget submit + stream subscribe pattern)
 */
export type SessionPayload = {
  sessionId: string;
  inputs: { user_prompt: string };
  scope?: 'public' | 'private';
  loggedInUser?: string;
};

type ExecutionTabProps = {
  runId: string | null;
};

/**
 * Loader component displayed while session messages are being fetched.
 * Prevents showing stale messages from the previous session.
 */
const SessionMessagesLoader: React.FC = () => (
  <div className="flex flex-col items-center justify-center h-full min-h-[400px]">
    <div className="flex flex-col items-center gap-4">
      <div className="w-8 h-8 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
      <p className="text-gray-400 text-sm">Loading session messages...</p>
    </div>
  </div>
);

export default function ExecutionTab({ runId }: ExecutionTabProps): React.ReactElement {
  const hub = useSessionHub({ runId });

  const [showExecutionStream, setShowExecutionStream] = useState(false);
  const [chatSidebarWidth, setChatSidebarWidth] = useState(15);
  const [chatInterfaceWidth, setChatInterfaceWidth] = useState(55);
  const [blueprintGraphWidth, setBlueprintGraphWidth] = useState(30);
  const [isResizing, setIsResizing] = useState(false);
  const [activeResizer, setActiveResizer] = useState<'left' | 'right' | null>(null);
  const [carouselMode, setCarouselMode] = useState<'normal' | 'chat' | 'graph'>('normal');

  const isChatOnlyMode = hub.selectedSession?.fromSharedLink ?? false;

  // ── Carousel mode ──────────────────────────────────────────────────────
  const handleSetCarouselMode = useCallback((mode: 'normal' | 'chat' | 'graph') => {
    if (isChatOnlyMode) return;
    const availableWidth = 100 - chatSidebarWidth;
    switch (mode) {
      case 'normal':
        setCarouselMode('normal');
        setChatInterfaceWidth(55);
        setBlueprintGraphWidth(availableWidth - 55);
        break;
      case 'chat':
        setCarouselMode('chat');
        setChatInterfaceWidth(availableWidth);
        setBlueprintGraphWidth(0);
        break;
      case 'graph':
        setCarouselMode('graph');
        setChatInterfaceWidth(0);
        setBlueprintGraphWidth(availableWidth);
        break;
    }
  }, [isChatOnlyMode, chatSidebarWidth]);

  // ── Resizable panels ──────────────────────────────────────────────────
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
      const availableWidth = 100 - chatSidebarWidth;
      const relativePosition = ((mousePosition - chatSidebarWidth) / availableWidth) * 100;
      const minChatInterface = 25;
      const maxChatInterface = 100;
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

  // Adjust layout for chat-only sessions
  useEffect(() => {
    if (isChatOnlyMode) {
      setCarouselMode('normal');
      setBlueprintGraphWidth(30);
      const remainingWidth = 100 - chatSidebarWidth - 30;
      setChatInterfaceWidth(remainingWidth);
    }
  }, [isChatOnlyMode, chatSidebarWidth]);

  // ── Loading / error states ─────────────────────────────────────────────
  if (hub.isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex justify-center items-center h-64">
          <div className="text-gray-400">Loading chat sessions...</div>
        </div>
      </div>
    );
  }

  if (hub.error) {
    return (
      <div className="space-y-6">
        <div className="flex justify-center items-center h-64">
          <div className="text-red-400">{hub.error}</div>
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
      </div>

      <div className="flex resizable-container gap-0" style={{ height: "calc(100vh - 230px)" }}>
        {/* Available Chats Sidebar */}
        <div className="flex-shrink-0" style={{ width: `${chatSidebarWidth}%` }}>
          <Card className="bg-background-card shadow-card border-gray-800 h-full flex flex-col mr-0">
            <div className="py-3 px-4 border-b border-gray-800 overflow-hidden flex-shrink-0">
              <div className="flex justify-between items-center min-w-0 w-full max-w-full">
                <span className="text-sm font-medium truncate flex-1 min-w-0 mr-2">
                  Available Chats ({hub.chatSessions.length})
                </span>
                <div className="flex items-center gap-1 flex-shrink-0 max-w-fit">
                  <Button variant="ghost" size="sm" className="h-6 w-6 p-0 flex-shrink-0">
                    <Users className="h-3 w-3" />
                  </Button>
                  <UmamiTrack event={UmamiEvents.AGENT_CHAT_ADD_FLOW_BUTTON} includeUserData={false}>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0 text-[#03DAC6] hover:bg-[#03DAC6] hover:bg-opacity-20 flex-shrink-0"
                      onClick={() => hub.setShowAddFlowModal(true)}
                      title="Add new chat from flow"
                    >
                      <Plus className="h-3 w-3" />
                    </Button>
                  </UmamiTrack>
                </div>
              </div>
            </div>
            <div className="p-0 flex-grow min-h-0 overflow-hidden">
              {hub.chatSessions.length === 0 ? (
                <div className="p-4 text-center text-gray-400 text-sm">
                  No chat sessions available
                </div>
              ) : (
                <div className="h-full overflow-y-auto py-2">
                  {hub.chatSessions.map((session) => (
                    <motion.div
                      key={session.id}
                      className={`group px-4 py-3 border-l-2 cursor-pointer ${
                        hub.selectedSession?.id === session.id
                          ? "border-[hsl(var(--primary))] bg-primary/20"
                          : "border-transparent hover:bg-background-surface"
                      } ${
                        !session.blueprintExists || session.isSharingDisabled
                          ? "opacity-50 bg-gray-800/30"
                          : ""
                      }`}
                      onClick={() => hub.handleSessionSelect(session)}
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
                        <UmamiTrack event={UmamiEvents.AGENT_CHAT_DELETE_CHAT_BUTTON} includeUserData={false}>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 w-6 p-0 text-gray-400 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={(e) => hub.handleDeleteChat(session, e)}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </UmamiTrack>
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
            </div>
          </Card>
        </div>

        {/* First Resizable divider */}
        <div
          className={`w-1 cursor-col-resize transition-colors duration-200 flex-shrink-0 ${
            isResizing && activeResizer === 'left' ? 'opacity-100' : 'opacity-50'
          }`}
          style={{ backgroundColor: 'hsl(var(--primary))' }}
          onMouseDown={handleMouseDown('left')}
          title="Drag to resize panels"
        />

        {/* ChatInterface Area */}
        <motion.div
          key="chat-panel"
          initial={false}
          animate={{
            opacity: carouselMode === 'graph' ? 0 : 1,
            x: carouselMode === 'graph' ? -30 : 0,
            scale: carouselMode === 'graph' ? 0.98 : 1
          }}
          transition={{ type: "spring", stiffness: 300, damping: 30, duration: 0.4 }}
          className="flex-shrink-0 flex flex-col"
          style={{
            width: carouselMode === 'graph' ? 0 : `${chatInterfaceWidth}%`,
            overflow: carouselMode === 'graph' ? 'hidden' : 'visible',
            pointerEvents: carouselMode === 'graph' ? 'none' : 'auto',
            transition: carouselMode === 'chat'
              ? 'width 0.7s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.3s ease-out'
              : 'width 0.4s ease-out, opacity 0.3s ease-out'
          }}
        >
          <div className="flex-grow">
            {hub.isLoadingSessionMessages ? (
              <SessionMessagesLoader />
            ) : (
              <ChatInterface
                key={hub.selectedSession?.id || 'no-session'}
                runId={hub.selectedSession?.id || ''}
                triggerExecution={hub.triggerExecution}
                onCancelSession={hub.handleCancelSession}
                initialMessages={hub.currentSessionMessages}
                sessionStatus={hub.selectedSession?.status}
                statusMessage={hub.selectedSession?.statusMessage}
                blueprintExists={hub.selectedSession?.blueprintExists ?? true}
                isSharingDisabled={hub.isSharingDisabled}
                blueprintValid={hub.isBlueprintValid}
                isValidatingBlueprint={hub.isValidatingBlueprint}
                isBlueprintGraphHidden={carouselMode === 'chat'}
                isChatOnlyMode={isChatOnlyMode}
                onSetCarouselMode={handleSetCarouselMode}
                carouselMode={carouselMode}
                isLiveRequest={hub.isLiveRequest}
                isSubmitting={hub.sessionStream.isSubmitting}
              />
            )}
          </div>

          {hub.selectedSession && showExecutionStream && (
            <div className="h-1/3 border-t border-gray-800 mt-2">
              <ExecutionStream
                blueprintId={hub.selectedSession.blueprintId}
                isLiveRequest={hub.isLiveRequest}
              />
            </div>
          )}
        </motion.div>

        {/* Second Resizable divider */}
        {(isChatOnlyMode || carouselMode === 'normal') && (
          <div
            className={`w-1 transition-colors duration-200 flex-shrink-0 ${
              isChatOnlyMode ? 'cursor-default' : 'cursor-col-resize'
            } ${
              isResizing && activeResizer === 'right' ? 'opacity-100' : 'opacity-50'
            }`}
            style={{ backgroundColor: 'hsl(var(--primary))' }}
            onMouseDown={isChatOnlyMode ? undefined : handleMouseDown('right')}
            title={isChatOnlyMode ? "Workflow not available for chat-only sessions" : "Drag to resize panels"}
          />
        )}

        {/* Blueprint Graph Visualization or Chat-Only Message */}
        <motion.div
          key="graph-panel"
          initial={false}
          animate={{
            opacity: (!isChatOnlyMode && carouselMode === 'chat') ? 0 : 1,
            x: (!isChatOnlyMode && carouselMode === 'chat') ? 30 : 0,
            scale: (!isChatOnlyMode && carouselMode === 'chat') ? 0.98 : 1
          }}
          transition={{ type: "spring", stiffness: 300, damping: 30, duration: 0.4 }}
          className="flex-shrink-0"
          style={{
            width: (!isChatOnlyMode && carouselMode === 'chat') ? 0 : `${blueprintGraphWidth}%`,
            overflow: (!isChatOnlyMode && carouselMode === 'chat') ? 'hidden' : 'visible',
            pointerEvents: (!isChatOnlyMode && carouselMode === 'chat') ? 'none' : 'auto',
            transition: carouselMode === 'graph'
              ? 'width 0.7s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.3s ease-out'
              : 'width 0.4s ease-out, opacity 0.3s ease-out'
          }}
        >
          <Card className="bg-background-card shadow-card border-gray-800 h-full flex flex-col ml-0 relative">
            {carouselMode === 'graph' && !isChatOnlyMode && (
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.3, duration: 0.2 }}
                className="absolute top-3 right-3 z-10"
              >
                <div className="flex items-center bg-background-surface border border-gray-700 rounded-lg p-0.5 shadow-lg">
                  <button
                    onClick={() => handleSetCarouselMode('normal')}
                    className="p-1.5 rounded-md transition-all duration-200 text-gray-400 hover:text-gray-200 hover:bg-gray-700/50"
                    title="Split View"
                  >
                    <Columns3 className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleSetCarouselMode('chat')}
                    className="p-1.5 rounded-md transition-all duration-200 text-gray-400 hover:text-gray-200 hover:bg-gray-700/50"
                    title="Full Chat View"
                  >
                    <MessageSquare className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleSetCarouselMode('graph')}
                    className="p-1.5 rounded-md transition-all duration-200 bg-primary text-white shadow-sm"
                    title="Full Graph View"
                  >
                    <Network className="h-4 w-4" />
                  </button>
                </div>
              </motion.div>
            )}
            <div className="p-0 flex-grow">
              {isChatOnlyMode ? (
                <div className="flex items-center justify-center h-full text-gray-400 text-sm flex-col p-6">
                  <p className="mb-2 text-base">This session was created from a shared chat link</p>
                  <p className="text-xs text-gray-500 mb-1">
                    Workflow: <span className="font-medium text-gray-300">
                      {hub.selectedSession?.blueprintName || "Unknown"}
                    </span>
                  </p>
                  <p className="text-xs text-gray-500">Workflow details are not available in shared link sessions</p>
                  {hub.selectedSession?.isSharingDisabled && (
                    <div className="mt-4 p-3 bg-red-900/20 border border-red-800 rounded-md">
                      <p className="text-xs text-red-400">Chat sharing has been disabled for this workflow</p>
                    </div>
                  )}
                </div>
              ) : hub.selectedSession?.blueprintId ? (
                <GraphDisplay
                  key={`main-graph-${hub.selectedSession.id}`}
                  blueprintId={hub.selectedSession.blueprintId}
                  specDict={hub.blueprintSpecCache.get(hub.selectedSession.blueprintId)}
                  height="100%"
                  showBackground={true}
                  interactive={true}
                  centerInView={true}
                  animated={true}
                  validationResults={hub.blueprintValidationResults}
                  isValidating={hub.isValidatingBlueprint}
                  isLiveRequest={hub.isLiveRequest}
                  isCancelled={hub.isCancelled}
                  isGraphVisible={carouselMode !== 'chat'}
                />
              ) : (
                <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                  {hub.selectedSession ? 'No blueprint available for this session' : 'Select a chat session to view blueprint'}
                </div>
              )}
            </div>
          </Card>
        </motion.div>
      </div>

      {/* Add Flow Modal */}
      <Dialog open={hub.showAddFlowModal} onOpenChange={hub.setShowAddFlowModal}>
        <CustomDialogContent
          className="bg-background-card border-gray-800 max-w-[95vw] w-[95vw] h-[85vh] max-h-[85vh] flex flex-col overflow-hidden"
        >
          <DialogHeader className="flex-shrink-0 pb-4">
            <DialogTitle className="text-lg">Add New Chat from Flow</DialogTitle>
          </DialogHeader>
          <div className="flex-1 min-h-0 overflow-hidden">
            <div key={`new-chat-graph-${hub.showAddFlowModal}`} className="h-full">
              <WorkflowsPanel
                selectedFlow={hub.selectedFlowForModal}
                onFlowSelect={(flow: FlowObject | null) => hub.setSelectedFlowForModal(flow)}
                showActiveStatus={false}
                showDeleteButton={false}
                height="100%"
                graphProps={{ showBackground: true, interactive: true }}
              />
            </div>
          </div>
          <DialogFooter className="flex-shrink-0 pt-4 border-t border-gray-800">
            <Button
              variant="outline"
              onClick={hub.handleCancelAddFlow}
              disabled={hub.isCreatingSession}
              className="bg-background-dark border-gray-700 hover:bg-background-surface"
            >
              Cancel
            </Button>
            <Button
              onClick={hub.handleAddFlow}
              disabled={!hub.selectedFlowForModal || hub.isCreatingSession}
              className="bg-[#03DAC6] hover:bg-opacity-80 text-black"
            >
              {hub.isCreatingSession ? "Creating..." : "Add"}
            </Button>
          </DialogFooter>
        </CustomDialogContent>
      </Dialog>

      {/* Delete Chat Confirmation Modal */}
      <AlertDialog open={hub.showDeleteModal} onOpenChange={hub.setShowDeleteModal}>
        <AlertDialogContent className="bg-background-card border-gray-800">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Chat</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{hub.chatToDelete?.title}"?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={hub.cancelDeleteChat}
              className="bg-background-dark border-gray-700 hover:bg-background-surface"
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={hub.confirmDeleteChat}
              disabled={hub.isDeleting}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {hub.isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
