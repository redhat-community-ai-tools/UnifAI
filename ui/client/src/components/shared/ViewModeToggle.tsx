import React from "react";
import { Columns3, MessageSquare, Network } from "lucide-react";

export type CarouselMode = "normal" | "chat" | "graph";

interface ViewModeToggleProps {
  mode: CarouselMode;
  onModeChange: (mode: CarouselMode) => void;
  className?: string;
}

const BUTTONS: { mode: CarouselMode; icon: typeof Columns3; title: string }[] = [
  { mode: "normal", icon: Columns3, title: "Split View" },
  { mode: "chat", icon: MessageSquare, title: "Full Chat View" },
  { mode: "graph", icon: Network, title: "Full Graph View" },
];

export function ViewModeToggle({ mode, onModeChange, className }: ViewModeToggleProps) {
  return (
    <div className={`flex items-center bg-background-surface border border-gray-700 rounded-lg p-0.5${className ? ` ${className}` : ""}`}>
      {BUTTONS.map(({ mode: btnMode, icon: Icon, title }) => (
        <button
          key={btnMode}
          onClick={() => onModeChange(btnMode)}
          className={`p-1.5 rounded-md transition-all duration-200 ${
            mode === btnMode
              ? "bg-primary text-white shadow-sm"
              : "text-gray-400 hover:text-gray-200 hover:bg-gray-700/50"
          }`}
          title={title}
          aria-label={title}
          aria-pressed={mode === btnMode}
        >
          <Icon className="h-4 w-4" />
        </button>
      ))}
    </div>
  );
}
