import React, { useState, useEffect } from "react";
import { format } from "date-fns";
import { CalendarIcon } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { cn } from "@/lib/utils";
import { DAY_NAMES } from "@/constants/dateConstants";
import { CustomRecurrenceConfig } from "@/utils/scheduleDefinitionUtils";

interface CustomRecurrenceDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onDone: (config: CustomRecurrenceConfig) => void;
  initialConfig?: CustomRecurrenceConfig | null;
  startDate: Date;
}

export function CustomRecurrenceDialog({
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

  // Weekday selection can only be honored for "every 1 week" -- there's no way to
  // represent "every N weeks on specific days" in the underlying schedule format
  // (it falls back to a flat N*7*24h interval with no day-of-week concept), so we
  // don't let the user pick days they'd expect to be respected but won't be.
  const canPickWeekDays = unit === "week" && repeatEvery === 1;

  const handleDone = () => {
    onDone({
      repeatEvery,
      unit,
      weekDays: canPickWeekDays ? weekDays : [],
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

          {/* Repeat on (week, every 1 week only) */}
          {canPickWeekDays && (
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
          {unit === "week" && repeatEvery > 1 && (
            <p className="text-xs text-gray-500">
              Weekday selection isn't available when repeating every {repeatEvery} weeks -- this
              repeats every {repeatEvery * 7} days starting from your start date.
            </p>
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
