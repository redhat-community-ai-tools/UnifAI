import React, { useState, useEffect, useMemo, useCallback } from "react";
import { format } from "date-fns";
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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { cn } from "@/lib/utils";
import { getPromptShortcuts, PromptShortcut } from "@/api/blueprints";
import {
  createScheduledPrompt,
  updateScheduledPrompt,
  ScheduledPromptResponse,
  ScheduleDefinitionInput,
} from "@/api/prompts";

// ────────────────────────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────────────────────────

type RecurrenceOption =
  | "does_not_repeat"
  | "every_15m"
  | "every_hour"
  | "every_day"
  | "every_week"
  | "every_month"
  | "custom";

interface CustomRecurrenceConfig {
  repeatEvery: number;
  unit: "minute" | "hour" | "day" | "week" | "month";
  weekDays: number[];
  ends: "never" | "on_date" | "after_count";
  endDate?: Date;
  endCount?: number;
}

interface SchedulePromptModalProps {
  isOpen: boolean;
  onClose: (saved?: boolean) => void;
  blueprintId: string;
  blueprintName: string;
  userId?: string;
  identityType?: string;
  editPrompt?: ScheduledPromptResponse | null;
}

const DAY_NAMES = ["S", "M", "T", "W", "T", "F", "S"];
const DAY_CRON_NAMES = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
const CRON_TO_DAY: Record<string, number> = {
  SUN: 0, MON: 1, TUE: 2, WED: 3, THU: 4, FRI: 5, SAT: 6,
};

const OVERLAP_OPTIONS = [
  { value: "skip", label: "Skip", description: "If previous run is still executing, skip this tick" },
  { value: "buffer_one", label: "Buffer One", description: "Queue one pending tick, skip further overlaps" },
  { value: "cancel_other", label: "Cancel Other", description: "Cancel the running session, start a new one" },
  { value: "allow_all", label: "Allow All", description: "Run concurrently (no limit)" },
];

// ────────────────────────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────────────────────────

function getRecurrenceLabels(startDate: Date): Record<RecurrenceOption, string> {
  const dayName = format(startDate, "EEEE");
  const ordinalDate = format(startDate, "do");
  return {
    does_not_repeat: "Does not repeat",
    every_15m: "Every 15 minutes",
    every_hour: "Hourly",
    every_day: "Daily",
    every_week: `Weekly on ${dayName}`,
    every_month: `Monthly on the ${ordinalDate}`,
    custom: "Custom...",
  };
}

function summarizeCustomRecurrence(config: CustomRecurrenceConfig): string {
  const { repeatEvery, unit, weekDays } = config;
  const n = repeatEvery;
  if (unit === "minute") return n === 1 ? "Every minute" : `Every ${n} minutes`;
  if (unit === "hour") return n === 1 ? "Every hour" : `Every ${n} hours`;
  if (unit === "day") return n === 1 ? "Daily" : `Every ${n} days`;
  if (unit === "month") return n === 1 ? "Monthly" : `Every ${n} months`;
  if (unit === "week") {
    const dayLabels = weekDays.sort().map((d) => DAY_CRON_NAMES[d].slice(0, 3));
    const daysPart = dayLabels.length > 0 ? ` on ${dayLabels.join(", ")}` : "";
    return n === 1 ? `Weekly${daysPart}` : `Every ${n} weeks${daysPart}`;
  }
  return "Custom";
}

function buildScheduleDefinition(
  startDate: Date,
  timezone: "UTC" | "local",
  recurrence: RecurrenceOption,
  customConfig?: CustomRecurrenceConfig | null,
  overlapPolicy?: string,
): ScheduleDefinitionInput {
  const isUTC = timezone === "UTC";
  const tz = isUTC ? "UTC" : Intl.DateTimeFormat().resolvedOptions().timeZone;
  const startAt = startDate.toISOString();
  const M = isUTC ? startDate.getUTCMinutes() : startDate.getMinutes();
  const H = isUTC ? startDate.getUTCHours() : startDate.getHours();
  const dayOfMonth = isUTC ? startDate.getUTCDate() : startDate.getDate();
  const dayOfWeek = isUTC ? startDate.getUTCDay() : startDate.getDay();

  const base: ScheduleDefinitionInput = {
    timezone: tz,
    start_at: startAt,
  };
  if (overlapPolicy && overlapPolicy !== "skip") {
    base.overlap_policy = overlapPolicy;
  }

  if (recurrence === "custom" && customConfig) {
    const result = { ...base };

    const { repeatEvery: n, unit, weekDays, ends, endDate, endCount } = customConfig;
    switch (unit) {
      case "minute":
        result.interval = `PT${n}M`;
        break;
      case "hour":
        result.interval = `PT${n}H`;
        break;
      case "day":
        if (n === 1) {
          result.cron_expression = `${M} ${H} * * *`;
        } else {
          result.interval = `PT${n * 24}H`;
        }
        break;
      case "week":
        if (n === 1 && weekDays.length > 0) {
          const cronDays = weekDays.sort().map((d) => DAY_CRON_NAMES[d]).join(",");
          result.cron_expression = `${M} ${H} * * ${cronDays}`;
        } else {
          result.interval = `PT${n * 7 * 24}H`;
        }
        break;
      case "month":
        result.cron_expression = `${M} ${H} ${dayOfMonth} * *`;
        break;
    }

    if (ends === "on_date" && endDate) {
      result.end_at = endDate.toISOString();
    } else if (ends === "after_count" && endCount) {
      result.remaining_actions = endCount;
    }

    if (!result.interval && !result.cron_expression) {
      result.interval = `PT${n}H`;
    }
    return result;
  }

  switch (recurrence) {
    case "does_not_repeat":
      return { ...base, interval: "PT1H", remaining_actions: 1 };
    case "every_15m":
      return { ...base, interval: "PT15M" };
    case "every_hour":
      return { ...base, interval: "PT1H" };
    case "every_day":
      return { ...base, cron_expression: `${M} ${H} * * *` };
    case "every_week":
      return { ...base, cron_expression: `${M} ${H} * * ${dayOfWeek}` };
    case "every_month":
      return { ...base, cron_expression: `${M} ${H} ${dayOfMonth} * *` };
    default:
      return { ...base, interval: "PT1H", remaining_actions: 1 };
  }
}

function parseISODuration(iso: string): { value: number; unit: "minute" | "hour" | "day" } | null {
  const match = iso.match(/^PT(\d+)([MH])$/);
  if (!match) return null;
  const value = parseInt(match[1], 10);
  const u = match[2];
  if (u === "M") return { value, unit: "minute" };
  if (u === "H") {
    if (value % 24 === 0 && value > 24) return { value: value / 24, unit: "day" };
    return { value, unit: "hour" };
  }
  return null;
}

function parseScheduleToState(schedule: ScheduleDefinitionInput): {
  recurrence: RecurrenceOption;
  startDate: Date;
  timezone: "UTC" | "local";
  customConfig: CustomRecurrenceConfig | null;
  overlapPolicy: string;
} {
  const startDate = schedule.start_at ? new Date(schedule.start_at) : new Date();
  const timezone: "UTC" | "local" = schedule.timezone === "UTC" ? "UTC" : "local";
  const overlapPolicy = schedule.overlap_policy || "skip";

  const endsConfig = {
    ends: "never" as "never" | "on_date" | "after_count",
    endDate: undefined as Date | undefined,
    endCount: undefined as number | undefined,
  };
  if (schedule.end_at) {
    endsConfig.ends = "on_date";
    endsConfig.endDate = new Date(schedule.end_at);
  } else if (schedule.remaining_actions != null && schedule.remaining_actions !== 1) {
    endsConfig.ends = "after_count";
    endsConfig.endCount = schedule.remaining_actions;
  }

  if (schedule.remaining_actions === 1) {
    return { recurrence: "does_not_repeat", startDate, timezone, customConfig: null, overlapPolicy };
  }

  if (schedule.interval) {
    if (schedule.interval === "PT15M" && !schedule.end_at && schedule.remaining_actions == null) {
      return { recurrence: "every_15m", startDate, timezone, customConfig: null, overlapPolicy };
    }
    if (schedule.interval === "PT1H" && !schedule.end_at && schedule.remaining_actions == null) {
      return { recurrence: "every_hour", startDate, timezone, customConfig: null, overlapPolicy };
    }
    const parsed = parseISODuration(schedule.interval);
    if (parsed) {
      let unit = parsed.unit as CustomRecurrenceConfig["unit"];
      let repeatEvery = parsed.value;
      if (unit === "hour" && repeatEvery >= 24 && repeatEvery % 24 === 0) {
        unit = "day";
        repeatEvery = repeatEvery / 24;
      }
      if (unit === "day" && repeatEvery >= 7 && repeatEvery % 7 === 0) {
        unit = "week";
        repeatEvery = repeatEvery / 7;
      }
      return {
        recurrence: "custom",
        startDate,
        timezone,
        customConfig: { repeatEvery, unit, weekDays: [], ...endsConfig },
        overlapPolicy,
      };
    }
  }

  if (schedule.cron_expression) {
    const parts = schedule.cron_expression.split(" ");
    if (parts.length === 5) {
      const hasEnds = schedule.end_at || (schedule.remaining_actions != null && schedule.remaining_actions !== 1);

      if (parts[2] === "*" && parts[3] === "*" && parts[4] === "*" && !hasEnds) {
        return { recurrence: "every_day", startDate, timezone, customConfig: null, overlapPolicy };
      }
      if (parts[2] === "*" && parts[3] === "*" && parts[4] !== "*") {
        const dayParts = parts[4].split(",");
        if (dayParts.length === 1 && !hasEnds) {
          const dayNum = parseInt(dayParts[0], 10);
          if (!isNaN(dayNum) && dayNum === startDate.getDay()) {
            return { recurrence: "every_week", startDate, timezone, customConfig: null, overlapPolicy };
          }
          const cronDay = CRON_TO_DAY[dayParts[0]];
          if (cronDay !== undefined && cronDay === startDate.getDay()) {
            return { recurrence: "every_week", startDate, timezone, customConfig: null, overlapPolicy };
          }
        }
        const weekDays = dayParts.map((d) => {
          const num = parseInt(d, 10);
          if (!isNaN(num)) return num;
          return CRON_TO_DAY[d.toUpperCase()] ?? -1;
        }).filter((d) => d >= 0);
        return {
          recurrence: "custom",
          startDate,
          timezone,
          customConfig: { repeatEvery: 1, unit: "week", weekDays, ...endsConfig },
          overlapPolicy,
        };
      }
      if (parts[2] !== "*" && parts[3] === "*" && parts[4] === "*" && !hasEnds) {
        return { recurrence: "every_month", startDate, timezone, customConfig: null, overlapPolicy };
      }
      if (parts[2] !== "*" && parts[3] === "*" && parts[4] === "*" && hasEnds) {
        return {
          recurrence: "custom",
          startDate,
          timezone,
          customConfig: { repeatEvery: 1, unit: "month", weekDays: [], ...endsConfig },
          overlapPolicy,
        };
      }
      if (parts[2] === "*" && parts[3] === "*" && parts[4] === "*" && hasEnds) {
        return {
          recurrence: "custom",
          startDate,
          timezone,
          customConfig: { repeatEvery: 1, unit: "day", weekDays: [], ...endsConfig },
          overlapPolicy,
        };
      }
    }
  }

  return { recurrence: "does_not_repeat", startDate, timezone, customConfig: null, overlapPolicy };
}

// ────────────────────────────────────────────────────────────────────────────────
// Custom Recurrence Dialog
// ────────────────────────────────────────────────────────────────────────────────

interface CustomRecurrenceDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onDone: (config: CustomRecurrenceConfig) => void;
  initialConfig?: CustomRecurrenceConfig | null;
  startDate: Date;
}

function CustomRecurrenceDialog({
  isOpen,
  onClose,
  onDone,
  initialConfig,
  startDate,
}: CustomRecurrenceDialogProps) {
  const [repeatEvery, setRepeatEvery] = useState(1);
  const [unit, setUnit] = useState<CustomRecurrenceConfig["unit"]>("week");
  const [weekDays, setWeekDays] = useState<number[]>([]);
  const [ends, setEnds] = useState<"never" | "on_date" | "after_count">("never");
  const [endDate, setEndDate] = useState<Date | undefined>(undefined);
  const [endCount, setEndCount] = useState(13);

  useEffect(() => {
    if (!isOpen) return;
    if (initialConfig) {
      setRepeatEvery(initialConfig.repeatEvery);
      setUnit(initialConfig.unit);
      setWeekDays(initialConfig.weekDays);
      setEnds(initialConfig.ends);
      setEndDate(initialConfig.endDate);
      setEndCount(initialConfig.endCount ?? 13);
    } else {
      setRepeatEvery(1);
      setUnit("week");
      setWeekDays([startDate.getDay()]);
      setEnds("never");
      setEndDate(undefined);
      setEndCount(13);
    }
  }, [isOpen, initialConfig, startDate]);

  const toggleWeekDay = (day: number) => {
    setWeekDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
    );
  };

  const handleDone = () => {
    onDone({
      repeatEvery,
      unit,
      weekDays: unit === "week" ? weekDays : [],
      ends,
      endDate: ends === "on_date" ? endDate : undefined,
      endCount: ends === "after_count" ? endCount : undefined,
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="bg-background-card border-gray-800 sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>Custom Recurrence</DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-2">
          {/* Repeat every */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">Repeat every</Label>
            <div className="flex gap-2">
              <Input
                type="number"
                min={1}
                max={999}
                value={repeatEvery}
                onChange={(e) => setRepeatEvery(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-[80px] bg-background-dark border-gray-700"
              />
              <Select value={unit} onValueChange={(v) => setUnit(v as CustomRecurrenceConfig["unit"])}>
                <SelectTrigger className="flex-1 bg-background-dark border-gray-700">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-popover border-gray-700">
                  <SelectItem value="minute">minute</SelectItem>
                  <SelectItem value="hour">hour</SelectItem>
                  <SelectItem value="day">day</SelectItem>
                  <SelectItem value="week">week</SelectItem>
                  <SelectItem value="month">month</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Repeat on (week only) */}
          {unit === "week" && (
            <div className="space-y-2">
              <Label className="text-sm font-medium">Repeat on</Label>
              <div className="flex gap-2">
                {DAY_NAMES.map((label, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => toggleWeekDay(idx)}
                    className={cn(
                      "h-9 w-9 rounded-full text-sm font-medium transition-colors",
                      weekDays.includes(idx)
                        ? "bg-primary text-white"
                        : "bg-transparent border border-gray-600 text-gray-400 hover:border-gray-400"
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Ends */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">Ends</Label>
            <RadioGroup value={ends} onValueChange={(v) => setEnds(v as typeof ends)}>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="never" id="ends-never" />
                <label htmlFor="ends-never" className="text-sm cursor-pointer">Never</label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="on_date" id="ends-on" />
                <label htmlFor="ends-on" className="text-sm cursor-pointer">On</label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={ends !== "on_date"}
                      className={cn(
                        "h-8 bg-background-dark border-gray-700 text-sm",
                        ends !== "on_date" && "opacity-50"
                      )}
                    >
                      <CalendarIcon className="mr-1.5 h-3.5 w-3.5" />
                      {endDate ? format(endDate, "MMM d, yyyy") : "Pick a date"}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0 bg-popover border-gray-700" align="start">
                    <Calendar
                      mode="single"
                      selected={endDate}
                      onSelect={(day) => { if (day) setEndDate(day); }}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="after_count" id="ends-after" />
                <label htmlFor="ends-after" className="text-sm cursor-pointer">After</label>
                <Input
                  type="number"
                  min={1}
                  max={9999}
                  value={endCount}
                  onChange={(e) => setEndCount(Math.max(1, parseInt(e.target.value) || 1))}
                  disabled={ends !== "after_count"}
                  className={cn(
                    "w-[70px] h-8 bg-background-dark border-gray-700 text-sm",
                    ends !== "after_count" && "opacity-50"
                  )}
                />
                <span className={cn("text-sm", ends !== "after_count" && "text-gray-500")}>
                  occurrences
                </span>
              </div>
            </RadioGroup>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} className="text-primary hover:text-primary/80">
            Cancel
          </Button>
          <Button onClick={handleDone}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ────────────────────────────────────────────────────────────────────────────────
// Main Component
// ────────────────────────────────────────────────────────────────────────────────

export default function SchedulePromptModal({
  isOpen,
  onClose,
  blueprintId,
  blueprintName,
  userId,
  identityType,
  editPrompt,
}: SchedulePromptModalProps) {
  const [promptText, setPromptText] = useState("");
  const [startDate, setStartDate] = useState<Date>(new Date());
  const [time, setTime] = useState("09:00");
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

  const recurrenceLabels = useMemo(
    () => getRecurrenceLabels(startDate),
    [startDate],
  );

  useEffect(() => {
    if (!isOpen) return;
    setError(null);

    if (editPrompt) {
      setPromptText(editPrompt.text);
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
      setStartDate(new Date());
      setTime("09:00");
      setTimezone("UTC");
      setRecurrence("does_not_repeat");
      setCustomRecurrence(null);
      setOverlapPolicy("skip");
      setCopiedFromShortcut(false);
    }
  }, [isOpen, editPrompt]);

  const loadShortcuts = async () => {
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
  };

  const handleShortcutSelect = (text: string) => {
    setPromptText(text);
    setCopiedFromShortcut(true);
  };

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

  const handleSubmit = async () => {
    if (!promptText.trim()) {
      setError("Prompt text is required");
      return;
    }
    if (combinedDateTime < new Date()) {
      setError("Start date and time must be in the future");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const schedule = buildScheduleDefinition(
        combinedDateTime, timezone, recurrence, customRecurrence, overlapPolicy,
      );
      if (isEditMode && editPrompt) {
        await updateScheduledPrompt(
          { promptId: editPrompt.id, text: promptText, schedule },
          userId,
          identityType,
        );
      } else {
        const source = copiedFromShortcut ? "shortcut_copy" : "manual";
        await createScheduledPrompt(
          { blueprintId, text: promptText, source, schedule },
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
  };

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
                onChange={(e) => {
                  setPromptText(e.target.value);
                  if (copiedFromShortcut) setCopiedFromShortcut(false);
                }}
                className="min-h-[80px] bg-background-dark border-gray-700 resize-none"
              />
            </div>

            {/* Start Date & Time */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-xs text-gray-400">Start Date & Time</Label>
                <div className="flex items-center gap-1">
                  <Button
                    variant={timezone === "UTC" ? "secondary" : "ghost"}
                    size="sm"
                    className="h-5 text-[10px] px-1.5"
                    onClick={() => setTimezone("UTC")}
                  >
                    UTC
                  </Button>
                  <Button
                    variant={timezone === "local" ? "secondary" : "ghost"}
                    size="sm"
                    className="h-5 text-[10px] px-1.5"
                    onClick={() => setTimezone("local")}
                  >
                    {localTimezone}
                  </Button>
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
                      {startDate ? format(startDate, "PPP") : "Pick a date"}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0 bg-popover border-gray-700" align="start">
                    <Calendar
                      mode="single"
                      selected={startDate}
                      onSelect={(day) => { if (day) setStartDate(day); }}
                      disabled={(date) => date < new Date(new Date().setHours(0, 0, 0, 0))}
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
                    <SelectItem key={key} value={key}>
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
