import React from "react";
import { X, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { PromptShortcutInput } from "@/api/blueprints";

const MAX_PROMPTS = 3;

interface PromptShortcutsEditorProps {
  prompts: PromptShortcutInput[];
  onChange: (prompts: PromptShortcutInput[]) => void;
  disabled?: boolean;
}

export default function PromptShortcutsEditor({
  prompts,
  onChange,
  disabled = false,
}: PromptShortcutsEditorProps) {
  const handleAdd = () => {
    if (prompts.length >= MAX_PROMPTS) return;
    onChange([...prompts, { text: "" }]);
  };

  const handleRemove = (index: number) => {
    onChange(prompts.filter((_, i) => i !== index));
  };

  const handleChange = (index: number, value: string) => {
    const updated = prompts.map((p, i) =>
      i === index ? { ...p, text: value } : p
    );
    onChange(updated);
  };

  return (
    <div className="space-y-3">
      {prompts.map((prompt, index) => (
        <div key={index} className="relative border border-gray-700 rounded-md p-3 space-y-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="absolute top-1 right-1 h-5 w-5 p-0 text-gray-400 hover:text-red-400"
            onClick={() => handleRemove(index)}
            disabled={disabled}
            aria-label={`Remove prompt shortcut ${index + 1}`}
          >
            <X className="h-3 w-3" />
          </Button>

          <div className="space-y-1">
            <Label htmlFor={`prompt-shortcut-${index}`} className="text-xs text-gray-400">Prompt text *</Label>
            <Textarea
              id={`prompt-shortcut-${index}`}
              placeholder="Enter the prompt text..."
              value={prompt.text}
              onChange={(e) => handleChange(index, e.target.value)}
              rows={2}
              className="input-dark-theme bg-input border-border text-foreground resize-none text-sm"
              disabled={disabled}
            />
          </div>
        </div>
      ))}

      <Button
        type="button"
        variant="outline"
        size="sm"
        className="w-full border-dashed border-gray-600 text-gray-400 hover:text-gray-200"
        onClick={handleAdd}
        disabled={disabled || prompts.length >= MAX_PROMPTS}
      >
        <Plus className="h-3.5 w-3.5 mr-1" />
        Add prompt shortcut
      </Button>
    </div>
  );
}