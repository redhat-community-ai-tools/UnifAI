import React from "react";
import { CalendarIcon, Copy } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { type WorkflowScheduleResponse } from "@/api/schedules";
import { RecurrenceOption, OVERLAP_OPTIONS, formatInMode } from "@/utils/scheduleDefinitionUtils";
import { useSchedulePromptForm } from "@/hooks/use-schedule-prompt-form";
import { CustomRecurrenceDialog } from "./CustomRecurrenceDialog";

interface SchedulePromptModalProps {
  isOpen: boolean;
  onClose: (saved?: boolean) => void;
  blueprintId: string;
  blueprintName: string;
  teamId?: string;
  editPrompt?: WorkflowScheduleResponse | null;
}

export default function SchedulePromptModal({
  isOpen,
  onClose,
  blueprintId,
  blueprintName,
  teamId,
  editPrompt,
}: SchedulePromptModalProps) {
  const {
    isEditMode,
    localTimezone,
    promptText,
    handlePromptTextChange,
    startDate,
    setStartDate,
    time,
    setTime,
    timezone,
    handleTimezoneChange,
    combinedDateTime,
    recurrence,
    recurrenceLabels,
    displayRecurrence,
    handleRecurrenceChange,
    reopenCustomDialog,
    customRecurrence,
    customDialogOpen,
    handleCustomDone,
    handleCustomCancel,
    overlapPolicy,
    setOverlapPolicy,
    shortcuts,
    shortcutsLoading,
    loadShortcuts,
    handleShortcutSelect,
    isSaving,
    error,
    handleSubmit,
  } = useSchedulePromptForm({ isOpen, blueprintId, teamId, editPrompt, onClose });

  return (
    <>
      <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
        <DialogContent className="bg-background-card border-gray-800 sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle>{isEditMode ? "Edit Scheduled Prompt" : "Schedule Prompt"}</DialogTitle>
          </DialogHeader>

          <div className="space-y-5 py-2">
            {/* Workflow */}
            <div className="space-y-1.5">
              <Label className="text-xs text-gray-400">Workflow</Label>
              <div className="text-sm font-medium text-gray-200 bg-background-surface px-3 py-2 rounded-md border border-gray-700">
                {blueprintName || blueprintId}
              </div>
            </div>

            {/* Prompt Text */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-xs text-gray-400">Prompt Text</Label>
                <DropdownMenu onOpenChange={(open) => { if (open) loadShortcuts(); }}>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="sm" className="h-6 text-xs text-primary hover:text-primary/80 px-2">
                      <Copy className="h-3 w-3 mr-1" />
                      Copy from shortcut
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="bg-popover border-gray-700 max-h-48 overflow-y-auto">
                    {shortcutsLoading ? (
                      <DropdownMenuItem disabled>Loading...</DropdownMenuItem>
                    ) : shortcuts.length === 0 ? (
                      <DropdownMenuItem disabled>No shortcuts available</DropdownMenuItem>
                    ) : (
                      shortcuts.map((s) => (
                        <DropdownMenuItem key={s.id} onClick={() => handleShortcutSelect(s.text)}>
                          <span className="truncate max-w-[250px]">{s.text}</span>
                        </DropdownMenuItem>
                      ))
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
              <Textarea
                placeholder="Enter the prompt text to execute on schedule..."
                value={promptText}
                onChange={(e) => handlePromptTextChange(e.target.value)}
                className="min-h-[80px] bg-background-dark border-gray-700 resize-none"
              />
            </div>

            {/* Start Date & Time */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-xs text-gray-400">Start Date & Time</Label>
                <div className="flex items-center bg-background-dark border border-gray-700 rounded-md p-0.5 gap-0.5">
                  <button
                    type="button"
                    onClick={() => handleTimezoneChange("UTC")}
                    className={`h-5 text-[10px] px-1.5 rounded font-medium transition-colors ${
                      timezone === "UTC"
                        ? "bg-secondary text-secondary-foreground"
                        : "text-gray-500 hover:bg-gray-800 hover:text-gray-200"
                    }`}
                  >
                    UTC
                  </button>
                  <button
                    type="button"
                    onClick={() => handleTimezoneChange("local")}
                    className={`h-5 text-[10px] px-1.5 rounded font-medium transition-colors ${
                      timezone === "local"
                        ? "bg-secondary text-secondary-foreground"
                        : "text-gray-500 hover:bg-gray-800 hover:text-gray-200"
                    }`}
                  >
                    {localTimezone}
                  </button>
                </div>
              </div>
              <div className="flex gap-2">
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      className={cn(
                        "flex-1 justify-start text-left font-normal bg-background-dark border-gray-700",
                        !startDate && "text-muted-foreground"
                      )}
                    >
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {startDate ? formatInMode(startDate, timezone, "PPP") : "Pick a date"}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0 bg-popover border-gray-700" align="start">
                    <Calendar
                      mode="single"
                      selected={startDate}
                      onSelect={(day) => {
                        if (!day) return;
                        // react-day-picker always returns a local-midnight-anchored Date for
                        // the clicked cell. In UTC mode we re-anchor it to UTC midnight of the
                        // same calendar day the user clicked, so merging in the time-of-day
                        // later (via setUTCHours) lands on the correct UTC date.
                        if (timezone === "UTC") {
                          setStartDate(new Date(Date.UTC(day.getFullYear(), day.getMonth(), day.getDate())));
                        } else {
                          setStartDate(day);
                        }
                      }}
                      disabled={(date) => {
                        if (timezone === "UTC") {
                          const cellAsUTC = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
                          const todayUTC = new Date(
                            Date.UTC(new Date().getUTCFullYear(), new Date().getUTCMonth(), new Date().getUTCDate())
                          );
                          return cellAsUTC < todayUTC;
                        }
                        return date < new Date(new Date().setHours(0, 0, 0, 0));
                      }}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
                <div className="flex items-center gap-0.5 w-[120px]">
                  <Input
                    type="number"
                    min={0}
                    max={23}
                    value={time.split(":")[0]}
                    onChange={(e) => {
                      const h = Math.min(23, Math.max(0, parseInt(e.target.value) || 0));
                      setTime(`${String(h).padStart(2, "0")}:${time.split(":")[1]}`);
                    }}
                    className="w-[52px] h-10 bg-background-dark border-gray-700 text-gray-200 text-center px-1 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  />
                  <span className="text-gray-400 font-medium select-none">:</span>
                  <Input
                    type="number"
                    min={0}
                    max={59}
                    value={time.split(":")[1]}
                    onChange={(e) => {
                      const m = Math.min(59, Math.max(0, parseInt(e.target.value) || 0));
                      setTime(`${time.split(":")[0]}:${String(m).padStart(2, "0")}`);
                    }}
                    className="w-[52px] h-10 bg-background-dark border-gray-700 text-gray-200 text-center px-1 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  />
                </div>
              </div>
            </div>

            {/* Recurrence */}
            <div className="space-y-1.5">
              <Label className="text-xs text-gray-400">Recurrence</Label>
              <Select
                value={recurrence}
                onValueChange={handleRecurrenceChange}
              >
                <SelectTrigger className="bg-background-dark border-gray-700">
                  <span className="truncate">{displayRecurrence}</span>
                </SelectTrigger>
                <SelectContent className="bg-popover border-gray-700">
                  {(Object.keys(recurrenceLabels) as RecurrenceOption[]).map((key) => (
                    <SelectItem
                      key={key}
                      value={key}
                      // Radix's Select only fires onValueChange when the value actually
                      // changes, so re-clicking "Custom..." while it's already selected
                      // wouldn't reopen the dialog otherwise. The setTimeout (in the hook)
                      // defers past the Select's own pointer-up handling (closing the
                      // popover) so the dialog isn't immediately dismissed by that same click.
                      onPointerUp={
                        key === "custom" && recurrence === "custom"
                          ? reopenCustomDialog
                          : undefined
                      }
                    >
                      {recurrenceLabels[key]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Advanced -- Overlap Policy */}
            <details className="group">
              <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-300 select-none">
                Advanced options
              </summary>
              <div className="mt-3 space-y-1.5">
                <Label className="text-xs text-gray-400">Overlap Policy</Label>
                <Select value={overlapPolicy} onValueChange={setOverlapPolicy}>
                  <SelectTrigger className="bg-background-dark border-gray-700">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-popover border-gray-700">
                    {OVERLAP_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        <div>
                          <span>{opt.label}</span>
                          <span className="ml-2 text-xs text-gray-500">{opt.description}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </details>

            {/* Error */}
            {error && (
              <p className="text-sm text-red-400">{error}</p>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => onClose()}
              disabled={isSaving}
              className="bg-background-dark border-gray-700 hover:bg-background-surface"
            >
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isSaving || !promptText.trim()}>
              {isSaving
                ? "Saving..."
                : isEditMode
                  ? "Save Changes"
                  : "Create Schedule"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <CustomRecurrenceDialog
        isOpen={customDialogOpen}
        onClose={handleCustomCancel}
        onDone={handleCustomDone}
        initialConfig={customRecurrence}
        startDate={combinedDateTime}
      />
    </>
  );
}
