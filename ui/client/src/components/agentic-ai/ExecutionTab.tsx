import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { motion } from "framer-motion";
import { MessageSquare, Users, Clock, Trash2, Plus } from "lucide-react";
import ChatInterface from "./chat/ChatInterface";
import ExecutionStream from "./ExecutionStream";
import GraphDisplay from "./graphs/GraphDisplay";
import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';
import { useSessionHub } from "@/hooks/use-session-hub";
import { useCarouselLayout } from "@/hooks/use-carousel-layout";
import { AnimatedPanelLayout } from "@/components/shared/AnimatedPanelLayout";
import { AddFlowModal, DeleteSessionModal } from "@/components/shared/SessionModals";
import { ViewModeToggle } from "@/components/shared/ViewModeToggle";

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
  const [isSidebarResizing, setIsSidebarResizing] = useState(false);

  const isChatOnlyMode = hub.selectedSession?.fromSharedLink ?? false;

  const carousel = useCarouselLayout({
    defaultChatPercent: 65,
    containerSelector: '.exec-panel-container',
    minPercent: 25,
    maxPercent: 80,
    disabled: isChatOnlyMode,
  });

  // ── Sidebar resizer (left divider between session list and panels) ────
  const handleSidebarMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsSidebarResizing(true);
  }, []);

  const handleSidebarMouseMove = useCallback((e: MouseEvent) => {
    if (!isSidebarResizing) return;
    const containerRect = document.querySelector('.resizable-container')?.getBoundingClientRect();
    if (!containerRect) return;
    const mousePosition = ((e.clientX - containerRect.left) / containerRect.width) * 100;
    setChatSidebarWidth(Math.min(Math.max(mousePosition, 15), 35));
  }, [isSidebarResizing]);

  const handleSidebarMouseUp = useCallback(() => {
    setIsSidebarResizing(false);
  }, []);

  useEffect(() => {
    if (isSidebarResizing) {
      document.addEventListener('mousemove', handleSidebarMouseMove);
      document.addEventListener('mouseup', handleSidebarMouseUp);
      document.body.style.cursor = 'col-resize';
    } else {
      document.removeEventListener('mousemove', handleSidebarMouseMove);
      document.removeEventListener('mouseup', handleSidebarMouseUp);
      document.body.style.cursor = '';
    }
    return () => {
      document.removeEventListener('mousemove', handleSidebarMouseMove);
      document.removeEventListener('mouseup', handleSidebarMouseUp);
      document.body.style.cursor = '';
    };
  }, [isSidebarResizing, handleSidebarMouseMove, handleSidebarMouseUp]);

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

  // ── Panel content ──────────────────────────────────────────────────────
  const chatPanelContent = (
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
          isBlueprintGraphHidden={carousel.carouselMode === 'chat'}
          isChatOnlyMode={isChatOnlyMode}
          onSetCarouselMode={carousel.setCarouselMode}
          carouselMode={carousel.carouselMode}
          isLiveRequest={hub.isLiveRequest}
          isSubmitting={hub.sessionStream.isSubmitting}
        />
      )}

      {hub.selectedSession && showExecutionStream && (
        <div className="h-1/3 border-t border-gray-800 mt-2">
          <ExecutionStream
            blueprintId={hub.selectedSession.blueprintId}
            isLiveRequest={hub.isLiveRequest}
          />
        </div>
      )}
    </div>
  );

  const graphPanelContent = (
    <Card className="bg-background-card shadow-card border-gray-800 h-full flex flex-col ml-0 relative">
      {carousel.carouselMode === 'graph' && !isChatOnlyMode && (
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3, duration: 0.2 }}
          className="absolute top-3 right-3 z-10"
        >
          <ViewModeToggle
            mode={carousel.carouselMode}
            onModeChange={carousel.setCarouselMode}
            className="shadow-lg"
          />
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
            isGraphVisible={carousel.carouselMode !== 'chat'}
            hitlEnabled={hub.selectedSession.hitlEnabled}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            {hub.selectedSession ? 'No blueprint available for this session' : 'Select a chat session to view blueprint'}
          </div>
        )}
      </div>
    </Card>
  );

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
        {/* Session list sidebar */}
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

        {/* Sidebar ↔ panels resizer */}
        <div
          className={`w-1 cursor-col-resize transition-colors duration-200 flex-shrink-0 ${
            isSidebarResizing ? 'opacity-100' : 'opacity-50'
          }`}
          style={{ backgroundColor: 'hsl(var(--primary))' }}
          onMouseDown={handleSidebarMouseDown}
          title="Drag to resize panels"
        />

        {/* Chat + Graph animated layout */}
        <AnimatedPanelLayout
          carouselMode={carousel.carouselMode}
          chatWidth={carousel.chatWidth}
          graphWidth={carousel.graphWidth}
          isResizing={carousel.isResizing}
          resizerProps={carousel.resizerProps}
          resizerDisabled={isChatOnlyMode}
          containerClassName="exec-panel-container"
          chatPanel={chatPanelContent}
          graphPanel={graphPanelContent}
        />
      </div>

      <AddFlowModal
        open={hub.showAddFlowModal}
        onOpenChange={hub.setShowAddFlowModal}
        selectedFlow={hub.selectedFlowForModal}
        onFlowSelect={hub.setSelectedFlowForModal}
        isCreating={hub.isCreatingSession}
        onConfirm={hub.handleAddFlow}
        onCancel={hub.handleCancelAddFlow}
        title="Add New Chat from Flow"
        confirmLabel="Add"
      />

      <DeleteSessionModal
        open={hub.showDeleteModal}
        onOpenChange={hub.setShowDeleteModal}
        session={hub.chatToDelete}
        isDeleting={hub.isDeleting}
        onConfirm={hub.confirmDeleteChat}
        onCancel={hub.cancelDeleteChat}
        title="Delete Chat"
      />
    </div>
  );
}
