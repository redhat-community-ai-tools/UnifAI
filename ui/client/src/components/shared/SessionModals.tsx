import React from "react";
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
import WorkflowsPanel from "@/components/agentic-ai/WorkflowsPanel";
import type { FlowObject } from "@/components/agentic-ai/graphs/interfaces";
import type { ChatSession } from "@/types/session";

// ── Add-Flow Modal ──────────────────────────────────────────────────────────

export interface AddFlowModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedFlow: FlowObject | null;
  onFlowSelect: (flow: FlowObject | null) => void;
  isCreating: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title?: string;
  confirmLabel?: string;
}

export function AddFlowModal({
  open,
  onOpenChange,
  selectedFlow,
  onFlowSelect,
  isCreating,
  onConfirm,
  onCancel,
  title = "Add New Session from Workflow",
  confirmLabel = "Add",
}: AddFlowModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <CustomDialogContent className="bg-background-card border-gray-800 max-w-[95vw] w-[95vw] h-[85vh] max-h-[85vh] flex flex-col overflow-hidden">
        <DialogHeader className="flex-shrink-0 pb-4">
          <DialogTitle className="text-lg">{title}</DialogTitle>
        </DialogHeader>
        <div className="flex-1 min-h-0 overflow-hidden">
          <div key={`add-flow-${open}`} className="h-full">
            <WorkflowsPanel
              selectedFlow={selectedFlow}
              onFlowSelect={(flow: FlowObject | null) => onFlowSelect(flow)}
              showDeleteButton={false}
              height="100%"
              graphProps={{ showBackground: true, interactive: true }}
            />
          </div>
        </div>
        <DialogFooter className="flex-shrink-0 pt-4 border-t border-gray-800">
          <Button
            variant="outline"
            onClick={onCancel}
            disabled={isCreating}
            className="bg-background-dark border-gray-700 hover:bg-background-surface"
          >
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={!selectedFlow || isCreating}
            className="bg-[#03DAC6] hover:bg-opacity-80 text-black"
          >
            {isCreating ? "Creating..." : confirmLabel}
          </Button>
        </DialogFooter>
      </CustomDialogContent>
    </Dialog>
  );
}

// ── Delete-Session Modal ────────────────────────────────────────────────────

export interface DeleteSessionModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  session: ChatSession | null;
  isDeleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title?: string;
}

export function DeleteSessionModal({
  open,
  onOpenChange,
  session,
  isDeleting,
  onConfirm,
  onCancel,
  title = "Delete Session",
}: DeleteSessionModalProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="bg-background-card border-gray-800">
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete &quot;{session?.title}&quot;?
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel
            onClick={onCancel}
            className="bg-background-dark border-gray-700 hover:bg-background-surface"
          >
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={isDeleting}
            className="bg-red-600 hover:bg-red-700 text-white"
          >
            {isDeleting ? "Deleting..." : "Delete"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
