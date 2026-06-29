import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import PromptShortcutsEditor from "./PromptShortcutsEditor";
import { PromptShortcutInput, getPromptShortcuts } from "@/api/blueprints";

interface EditPromptShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
  blueprintId: string;
  onSave: (prompts: PromptShortcutInput[]) => Promise<void>;
}

export default function EditPromptShortcutsModal({
  isOpen,
  onClose,
  blueprintId,
  onSave,
}: EditPromptShortcutsModalProps) {
  const [prompts, setPrompts] = useState<PromptShortcutInput[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!isOpen || !blueprintId) return;
    let cancelled = false;
    setIsLoading(true);
    getPromptShortcuts(blueprintId)
      .then((data) => {
        if (!cancelled) setPrompts(data.prompts);
      })
      .catch((err) => {
        if (!cancelled) console.error("Failed to load prompt shortcuts:", err);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => { cancelled = true; };
  }, [isOpen, blueprintId]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const cleaned = prompts.filter((p) => p.text.trim());
      await onSave(cleaned);
      onClose();
    } catch (error) {
      console.error("Failed to save prompt shortcuts:", error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[500px] bg-gray-900 border-gray-700 max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-white">Prompt Shortcuts</DialogTitle>
        </DialogHeader>

        <div className="py-4">
          <p className="text-xs text-gray-500 mb-3">
            Clickable prompts shown as chips when starting a new chat session.
          </p>
          {isLoading ? (
            <div className="flex items-center justify-center py-6 text-gray-400 text-sm">
              Loading...
            </div>
          ) : (
            <PromptShortcutsEditor
              prompts={prompts}
              onChange={setPrompts}
              disabled={isSaving}
            />
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isSaving}
            className="border-gray-600 text-gray-300"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving}
            className="bg-primary hover:bg-primary/80"
          >
            {isSaving ? (
              <div className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                Saving...
              </div>
            ) : (
              "Save"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
