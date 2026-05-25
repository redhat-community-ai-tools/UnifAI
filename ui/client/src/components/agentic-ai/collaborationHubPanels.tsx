import React from "react";
import { motion } from "framer-motion";
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
import {
  Dialog,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  CustomDialogContent,
} from "@/components/ui/dialog";
import { Users, Trash2, Plus, MessageSquare, Network } from "lucide-react";
import ChatInterface from "./chat/ChatInterface";
import GraphDisplay from "./graphs/GraphDisplay";
import WorkflowsPanel from "./WorkflowsPanel";
import { CollabAvatar } from "@/components/shared/CollabAvatar";
import type { MemberDisplay } from "@/utils/memberDisplay";
import type { ChatSession, ChatMessage } from "@/types/session";
import type { FlowObject } from "./graphs/interfaces";
import type { SessionPayload } from "./ExecutionTab";
import type { ElementValidationResult } from "@/types/validation";

export interface CollaborationHubSessionSidebarProps {
  chatSessions: ChatSession[];
  selectedSession: ChatSession | null;
  isLiveRequest: boolean;
  onSelectSession: (session: ChatSession) => void;
  onDeleteChat: (session: ChatSession, event: React.MouseEvent) => void;
  onOpenAddFlow: () => void;
  getSessionParticipantMembers: (sessionId: string) => MemberDisplay[];
}

export function CollaborationHubSessionSidebar({
  chatSessions,
  selectedSession,
  isLiveRequest,
  onSelectSession,
  onDeleteChat,
  onOpenAddFlow,
  getSessionParticipantMembers,
}: CollaborationHubSessionSidebarProps) {
  return (
    <div className="w-[280px] border-r border-gray-800 bg-background-card flex flex-col flex-shrink-0">
      <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <span className="font-semibold text-sm text-white">
          Sessions ({chatSessions.length})
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0 text-primary hover:bg-primary/20"
          onClick={onOpenAddFlow}
          title="New session from workflow"
        >
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {chatSessions.length === 0 ? (
          <div className="p-4 text-center text-gray-500 text-xs">
            No sessions yet. Load a workflow to get started.
          </div>
        ) : (
          chatSessions.map((session) => (
            <div
              key={session.id}
              onClick={() => onSelectSession(session)}
              className={`group px-4 py-3 border-b border-gray-800/50 cursor-pointer transition-colors ${
                selectedSession?.id === session.id
                  ? "bg-primary/10 border-l-2 border-l-primary"
                  : "hover:bg-white/[.02]"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="font-semibold text-xs text-white truncate flex-1">
                  {session.blueprintName || session.title}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-5 w-5 p-0 text-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                  onClick={(e) => onDeleteChat(session, e)}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
              <div className="flex items-center gap-1.5 mt-1">
                <motion.div
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0 bg-emerald-400"
                  animate={
                    selectedSession?.id === session.id && isLiveRequest
                      ? { opacity: [1, 0.4, 1] }
                      : {}
                  }
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
                <span className="text-[11px] text-gray-500">{session.lastActive}</span>
              </div>
              {session.blueprintName && session.blueprintName !== session.title && (
                <div className="flex items-center gap-1 mt-1.5">
                  <MessageSquare className="h-2.5 w-2.5 text-gray-600" />
                  <span className="text-[10px] text-gray-600 truncate">{session.title}</span>
                </div>
              )}
              {(() => {
                const participants = getSessionParticipantMembers(session.id);
                if (participants.length === 0) return null;
                return (
                  <div className="flex items-center mt-2 -space-x-1">
                    {participants.slice(0, 3).map((m) => (
                      <div
                        key={m.id}
                        className="ring-2 ring-background-card rounded-full"
                      >
                        <CollabAvatar member={m} size="xs" />
                      </div>
                    ))}
                    {participants.length > 3 && (
                      <span className="text-[10px] text-gray-600 ml-2">
                        +{participants.length - 3}
                      </span>
                    )}
                  </div>
                );
              })()}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export interface CollaborationHubMainColumnProps {
  selectedSession: ChatSession | null;
  isLiveRequest: boolean;
  isSessionBusy: boolean;
  isSubmitting: boolean;
  currentSessionMessages: ChatMessage[];
  isSharingDisabled: boolean;
  isBlueprintValid: boolean;
  isValidatingBlueprint: boolean;
  typingUsers: string[];
  teamMembers: MemberDisplay[];
  triggerExecution: (payload: SessionPayload) => Promise<unknown>;
  onCancelSession: () => Promise<void>;
  getSessionParticipantMembers: (sessionId: string) => MemberDisplay[];
}

export function CollaborationHubMainColumn({
  selectedSession,
  isLiveRequest,
  isSessionBusy,
  isSubmitting,
  currentSessionMessages,
  isSharingDisabled,
  isBlueprintValid,
  isValidatingBlueprint,
  typingUsers,
  teamMembers,
  triggerExecution,
  onCancelSession,
  getSessionParticipantMembers,
}: CollaborationHubMainColumnProps) {
  return (
    <div className="flex-1 flex flex-col min-w-0">
      <div className="px-5 py-3 border-b border-gray-800 bg-background-surface flex items-center gap-3 flex-shrink-0">
        {selectedSession ? (
          <>
            <motion.div
              className={`w-2 h-2 rounded-full flex-shrink-0 ${isLiveRequest || isSessionBusy ? "bg-emerald-400" : "bg-gray-500"}`}
              animate={isLiveRequest || isSessionBusy ? { opacity: [1, 0.4, 1] } : {}}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <span className="font-bold text-sm text-white flex-1 truncate">
              {selectedSession.blueprintName || selectedSession.title}
            </span>
            {(() => {
              const participants = getSessionParticipantMembers(selectedSession.id);
              return (
                <div className="flex items-center -space-x-1.5">
                  {participants.slice(0, 4).map((m) => (
                    <div
                      key={m.id}
                      className="ring-2 ring-background-surface rounded-full"
                    >
                      <CollabAvatar member={m} size="xs" />
                    </div>
                  ))}
                  {participants.length > 0 && (
                    <span className="text-xs text-gray-500 ml-2">
                      {participants.length} active
                    </span>
                  )}
                </div>
              );
            })()}
          </>
        ) : (
          <span className="text-sm text-gray-500">Select a session to start</span>
        )}
      </div>

      <div className="flex-1 min-h-0">
        {selectedSession ? (
          <ChatInterface
            key={selectedSession.id}
            runId={selectedSession.id}
            triggerExecution={triggerExecution}
            onCancelSession={onCancelSession}
            initialMessages={currentSessionMessages}
            blueprintExists={selectedSession.blueprintExists}
            isSharingDisabled={isSharingDisabled}
            blueprintValid={isBlueprintValid}
            isValidatingBlueprint={isValidatingBlueprint}
            isLiveRequest={isLiveRequest || isSessionBusy}
            isSubmitting={isSubmitting}
            collaborationMode={true}
            teamMembers={teamMembers}
            typingUsers={typingUsers}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            <div className="text-center">
              <Users className="h-10 w-10 mx-auto mb-3 text-gray-600" />
              <p className="font-medium text-gray-400">No session selected</p>
              <p className="text-xs mt-1">Choose a session from the sidebar or load a workflow</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export interface CollaborationHubRightPanelProps {
  selectedSession: ChatSession | null;
  isLiveRequest: boolean;
  isCancelled: boolean;
  isSessionBusy: boolean;
  teamName: string;
  chatSessionsLength: number;
  blueprintSpecCache: Map<string, unknown>;
  blueprintValidationResults?: Record<string, ElementValidationResult>;
  isValidatingBlueprint: boolean;
  getSessionParticipantMembers: (sessionId: string) => MemberDisplay[];
}

export function CollaborationHubRightPanel({
  selectedSession,
  isLiveRequest,
  isCancelled,
  isSessionBusy,
  teamName,
  chatSessionsLength,
  blueprintSpecCache,
  blueprintValidationResults,
  isValidatingBlueprint,
  getSessionParticipantMembers,
}: CollaborationHubRightPanelProps) {
  return (
    <div className="w-[340px] border-l border-gray-800 bg-background-card flex flex-col flex-shrink-0 hidden xl:flex">
      <div className="flex-1 min-h-0 flex flex-col border-b border-gray-800">
        <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2">
            <Network className="w-3.5 h-3.5 text-primary" />
            <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
              Live Workflow
            </span>
          </div>
          {(isLiveRequest || isSessionBusy) && (
            <div className="flex items-center gap-1.5">
              <motion.div
                className="w-1.5 h-1.5 rounded-full bg-emerald-400"
                animate={{ opacity: [1, 0.4, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />
              <span className="text-[10px] text-emerald-400 font-medium">Running</span>
            </div>
          )}
        </div>
        <div className="flex-1 min-h-0 bg-background-dark">
          {selectedSession?.blueprintId ? (
            <GraphDisplay
              key={`collab-live-${selectedSession.id}`}
              blueprintId={selectedSession.blueprintId}
              specDict={blueprintSpecCache.get(selectedSession.blueprintId)}
              height="100%"
              showBackground={true}
              interactive={false}
              centerInView={true}
              animated={true}
              validationResults={blueprintValidationResults}
              isValidating={isValidatingBlueprint}
              isLiveRequest={isLiveRequest}
              isCancelled={isCancelled}
              isGraphVisible={true}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-600 text-xs">
              Select a session to view workflow
            </div>
          )}
        </div>
      </div>

      <div className="px-4 py-3 border-b border-gray-800 flex-shrink-0">
        {(() => {
          const participants = selectedSession
            ? getSessionParticipantMembers(selectedSession.id)
            : [];
          return (
            <>
              <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-3">
                Active Participants ({participants.length})
              </div>
              {participants.length === 0 ? (
                <div className="text-xs text-gray-600 text-center py-2">No messages sent yet</div>
              ) : (
                <div className="space-y-1">
                  {participants.map((m) => (
                    <div key={m.id} className="flex items-center gap-2 py-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                      <CollabAvatar member={m} size="xs" />
                      <span className="text-xs text-gray-300 flex-1 truncate">{m.name}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          );
        })()}
      </div>

      <div className="px-4 py-3 flex-shrink-0">
        <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Session Info
        </div>
        <dl className="text-xs text-gray-500 space-y-1.5">
          <div className="flex justify-between">
            <dt className="font-medium text-gray-400">Team</dt>
            <dd>{teamName}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium text-gray-400">Blueprint</dt>
            <dd className="truncate ml-2 max-w-[140px]">
              {selectedSession?.blueprintName || selectedSession?.blueprintId || "—"}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium text-gray-400">Started</dt>
            <dd>{selectedSession?.lastActive || "—"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium text-gray-400">Status</dt>
            <dd
              className={
                isLiveRequest || isSessionBusy ? "text-emerald-400 font-semibold" : "text-gray-500"
              }
            >
              {isLiveRequest || isSessionBusy ? "Running" : selectedSession ? "Idle" : "—"}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium text-gray-400">Sessions</dt>
            <dd>{chatSessionsLength}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}

export interface CollaborationHubModalsProps {
  showAddFlowModal: boolean;
  setShowAddFlowModal: (open: boolean) => void;
  selectedFlowForModal: FlowObject | null;
  setSelectedFlowForModal: (flow: FlowObject | null) => void;
  isCreatingSession: boolean;
  onAddFlowConfirm: () => void;
  showDeleteModal: boolean;
  setShowDeleteModal: (open: boolean) => void;
  chatToDelete: ChatSession | null;
  isDeleting: boolean;
  onConfirmDelete: () => void;
  onDeleteCancel: () => void;
}

export function CollaborationHubModals({
  showAddFlowModal,
  setShowAddFlowModal,
  selectedFlowForModal,
  setSelectedFlowForModal,
  isCreatingSession,
  onAddFlowConfirm,
  showDeleteModal,
  setShowDeleteModal,
  chatToDelete,
  isDeleting,
  onConfirmDelete,
  onDeleteCancel,
}: CollaborationHubModalsProps) {
  return (
    <>
      <Dialog open={showAddFlowModal} onOpenChange={setShowAddFlowModal}>
        <CustomDialogContent className="bg-background-card border-gray-800 max-w-[95vw] w-[95vw] h-[85vh] max-h-[85vh] flex flex-col overflow-hidden">
          <DialogHeader className="flex-shrink-0 pb-4">
            <DialogTitle className="text-lg">Start New Session</DialogTitle>
          </DialogHeader>
          <div className="flex-1 min-h-0 overflow-hidden">
            <div key={`collab-hub-add-${showAddFlowModal}`} className="h-full">
              <WorkflowsPanel
                selectedFlow={selectedFlowForModal}
                onFlowSelect={(flow: FlowObject | null) => setSelectedFlowForModal(flow)}
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
              onClick={() => {
                setShowAddFlowModal(false);
                setSelectedFlowForModal(null);
              }}
              disabled={isCreatingSession}
              className="bg-background-dark border-gray-700 hover:bg-background-surface"
            >
              Cancel
            </Button>
            <Button
              onClick={onAddFlowConfirm}
              disabled={!selectedFlowForModal || isCreatingSession}
              className="bg-[#03DAC6] hover:bg-opacity-80 text-black"
            >
              {isCreatingSession ? "Creating..." : "Start Session"}
            </Button>
          </DialogFooter>
        </CustomDialogContent>
      </Dialog>

      <AlertDialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
        <AlertDialogContent className="bg-background-card border-gray-800">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Session</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{chatToDelete?.title}&quot;?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => {
                setShowDeleteModal(false);
                onDeleteCancel();
              }}
              className="bg-background-dark border-gray-700 hover:bg-background-surface"
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={onConfirmDelete}
              disabled={isDeleting}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
