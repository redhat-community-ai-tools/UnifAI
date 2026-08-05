import { useState, useEffect, useMemo, useCallback } from "react";
import { format } from "date-fns";
import { getPromptShortcuts, PromptShortcut } from "@/api/blueprints";
import {
  createSchedule,
  updateSchedule,
  type WorkflowScheduleResponse,
} from "@/api/schedules";
import {
  RecurrenceOption,
  CustomRecurrenceConfig,
  getRecurrenceLabels,
  summarizeCustomRecurrence,
  buildScheduleDefinition,
  parseScheduleToState,
  isSameMinute,
  resolveStartDateTime,
} from "@/utils/scheduleDefinitionUtils";

interface UseSchedulePromptFormArgs {
  isOpen: boolean;
  blueprintId: string;
  userId?: string;
  identityType?: string;
  editPrompt?: WorkflowScheduleResponse | null;
  onClose: (saved?: boolean) => void;
}

/**
 * Owns all state, derived values, and submit/reset logic for `SchedulePromptModal`.
 * Keeping this here lets the component stay focused on rendering the form.
 */
export function useSchedulePromptForm({
  isOpen,
  blueprintId,
  userId,
  identityType,
  editPrompt,
  onClose,
}: UseSchedulePromptFormArgs) {
  const [promptText, setPromptText] = useState("");
  const [startDate, setStartDate] = useState<Date>(() => {
    const now = new Date();
    return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  });
  const [time, setTime] = useState(() => {
    const now = new Date();
    return `${String(now.getUTCHours()).padStart(2, "0")}:${String(now.getUTCMinutes()).padStart(2, "0")}`;
  });
  const [timezone, setTimezone] = useState<"UTC" | "local">("UTC");
  const [recurrence, setRecurrence] = useState<RecurrenceOption>("does_not_repeat");
  const [customRecurrence, setCustomRecurrence] = useState<CustomRecurrenceConfig | null>(null);
  const [customDialogOpen, setCustomDialogOpen] = useState(false);
  const [overlapPolicy, setOverlapPolicy] = useState("skip");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedFromShortcut, setCopiedFromShortcut] = useState(false);
  const [shortcuts, setShortcuts] = useState<PromptShortcut[]>([]);
  const [shortcutsLoading, setShortcutsLoading] = useState(false);
  const [prevRecurrence, setPrevRecurrence] = useState<RecurrenceOption>("does_not_repeat");

  const isEditMode = !!editPrompt;
  const localTimezone = useMemo(() => Intl.DateTimeFormat().resolvedOptions().timeZone, []);

  const handleTimezoneChange = useCallback(
    (newTz: "UTC" | "local") => {
      if (newTz === timezone) return;

      const [h, m] = time.split(":").map(Number);
      const d = new Date(startDate);

      if (timezone === "UTC") {
        d.setUTCHours(h, m, 0, 0);
      } else {
        d.setHours(h, m, 0, 0);
      }

      if (newTz === "UTC") {
        setTime(
          `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`
        );
        setStartDate(new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate())));
      } else {
        setTime(
          `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
        );
        setStartDate(new Date(d.getFullYear(), d.getMonth(), d.getDate()));
      }

      setTimezone(newTz);
    },
    [timezone, time, startDate]
  );

  const recurrenceLabels = useMemo(
    () => getRecurrenceLabels(startDate, timezone),
    [startDate, timezone],
  );

  useEffect(() => {
    if (!isOpen) return;
    setError(null);

    if (editPrompt) {
      setPromptText(editPrompt.inputs.user_prompt ?? "");
      const parsed = parseScheduleToState(editPrompt.schedule);
      setStartDate(parsed.startDate);
      setTime(format(parsed.startDate, "HH:mm"));
      setTimezone(parsed.timezone);
      setRecurrence(parsed.recurrence);
      setCustomRecurrence(parsed.customConfig);
      setOverlapPolicy(parsed.overlapPolicy);
      setCopiedFromShortcut(editPrompt.source === "shortcut_copy");
    } else {
      setPromptText("");
      const now = new Date();
      setStartDate(now);
      setTime(
        `${String(now.getUTCHours()).padStart(2, "0")}:${String(now.getUTCMinutes()).padStart(2, "0")}`
      );
      setTimezone("UTC");
      setRecurrence("does_not_repeat");
      setCustomRecurrence(null);
      setOverlapPolicy("skip");
      setCopiedFromShortcut(false);
    }
  }, [isOpen, editPrompt]);

  const loadShortcuts = useCallback(async () => {
    if (shortcuts.length > 0 || shortcutsLoading) return;
    setShortcutsLoading(true);
    try {
      const result = await getPromptShortcuts(blueprintId, userId, identityType);
      setShortcuts(result.prompts);
    } catch {
      setShortcuts([]);
    } finally {
      setShortcutsLoading(false);
    }
  }, [blueprintId, userId, identityType, shortcuts.length, shortcutsLoading]);

  const handlePromptTextChange = useCallback((text: string) => {
    setPromptText(text);
    setCopiedFromShortcut(false);
  }, []);

  const handleShortcutSelect = useCallback((text: string) => {
    setPromptText(text);
    setCopiedFromShortcut(true);
  }, []);

  const combinedDateTime = useMemo(() => {
    const [hours, minutes] = time.split(":").map(Number);
    const d = new Date(startDate);
    if (timezone === "UTC") {
      d.setUTCHours(hours, minutes, 0, 0);
    } else {
      d.setHours(hours, minutes, 0, 0);
    }
    return d;
  }, [startDate, time, timezone]);

  const handleRecurrenceChange = useCallback((value: string) => {
    const v = value as RecurrenceOption;
    if (v === "custom") {
      setPrevRecurrence(recurrence);
      setCustomDialogOpen(true);
    }
    setRecurrence(v);
  }, [recurrence]);

  const reopenCustomDialog = useCallback(() => {
    setTimeout(() => setCustomDialogOpen(true), 0);
  }, []);

  const handleCustomDone = useCallback((config: CustomRecurrenceConfig) => {
    setCustomRecurrence(config);
    setRecurrence("custom");
    setCustomDialogOpen(false);
  }, []);

  const handleCustomCancel = useCallback(() => {
    setCustomDialogOpen(false);
    if (!customRecurrence) {
      setRecurrence(prevRecurrence);
    }
  }, [customRecurrence, prevRecurrence]);

  const displayRecurrence = useMemo(() => {
    if (recurrence === "custom" && customRecurrence) {
      return summarizeCustomRecurrence(customRecurrence);
    }
    return recurrenceLabels[recurrence];
  }, [recurrence, customRecurrence, recurrenceLabels]);

  const handleSubmit = useCallback(async () => {
    if (!promptText.trim()) {
      setError("Prompt text is required");
      return;
    }

    const isCompleted = editPrompt?.schedule_status === "completed";
    const originalStart = editPrompt?.schedule.start_at
      ? new Date(editPrompt.schedule.start_at)
      : null;
    const startAtDirty =
      !isEditMode || isCompleted || !originalStart || !isSameMinute(combinedDateTime, originalStart);

    let effectiveStart = combinedDateTime;
    if (startAtDirty) {
      const resolved = resolveStartDateTime(combinedDateTime);
      if (!resolved) {
        setError("Start date and time must be in the future");
        return;
      }
      effectiveStart = resolved;
    }

    if (
      isEditMode &&
      !isCompleted &&
      customRecurrence?.ends === "after_count" &&
      customRecurrence.endCount != null &&
      editPrompt
    ) {
      const totalRuns = editPrompt.run_stats?.total_runs ?? 0;
      if (customRecurrence.endCount < totalRuns) {
        setError(
          `Ends after cannot be less than runs already completed (${totalRuns} so far)`,
        );
        return;
      }
    }

    setIsSaving(true);
    setError(null);
    try {
      const schedule = buildScheduleDefinition(
        effectiveStart, timezone, recurrence, customRecurrence, overlapPolicy,
      );
      if (isEditMode && !startAtDirty) {
        // Keep the original start on the server; omit so merge preserves it.
        delete schedule.start_at;
      }
      if (isEditMode && editPrompt) {
        await updateSchedule(
          { scheduleId: editPrompt.id, inputs: { user_prompt: promptText }, schedule },
          userId,
          identityType,
        );
      } else {
        const source = copiedFromShortcut ? "shortcut_copy" : "manual";
        await createSchedule(
          { blueprintId, inputs: { user_prompt: promptText }, source, schedule },
          userId,
          identityType,
        );
      }
      onClose(true);
    } catch (err: any) {
      const message = err?.response?.data?.error || err?.message || "Failed to save schedule";
      setError(message);
    } finally {
      setIsSaving(false);
    }
  }, [
    promptText, combinedDateTime, timezone, recurrence, customRecurrence, overlapPolicy,
    isEditMode, editPrompt, userId, identityType, copiedFromShortcut, blueprintId, onClose,
  ]);

  return {
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
  };
}
