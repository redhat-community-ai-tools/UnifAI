import React from "react";
import { AlertTriangle, XCircle, Loader2, Info } from "lucide-react";

export type BannerVariant = "warning" | "error" | "info" | "loading";

interface WorkflowStatusBannerProps {
  variant: BannerVariant;
  title?: string;
  message: string;
  className?: string;
}

const variantStyles: Record<BannerVariant, {
  bg: string;
  border: string;
  text: string;
  icon: React.ReactNode;
}> = {
  warning: {
    bg: "bg-orange-900/20",
    border: "border-orange-500/50",
    text: "text-orange-200",
    icon: <AlertTriangle className="w-5 h-5 mr-2 flex-shrink-0" />,
  },
  error: {
    bg: "bg-red-900/20",
    border: "border-red-500/50",
    text: "text-red-200",
    icon: <XCircle className="w-5 h-5 mr-2 flex-shrink-0" />,
  },
  info: {
    bg: "bg-blue-900/20",
    border: "border-blue-500/50",
    text: "text-blue-200",
    icon: <Info className="w-5 h-5 mr-2 flex-shrink-0" />,
  },
  loading: {
    bg: "bg-blue-900/20",
    border: "border-blue-500/50",
    text: "text-blue-200",
    icon: <Loader2 className="w-5 h-5 mr-2 flex-shrink-0 animate-spin" />,
  },
};

/**
 * Reusable status banner for displaying workflow-related messages.
 * 
 * Variants:
 * - warning: Orange banner for warnings (e.g., sharing disabled)
 * - error: Red banner for errors (e.g., validation failed, workflow deleted)
 * - info: Blue banner for informational messages
 * - loading: Blue banner with spinner for loading states
 */
export default function WorkflowStatusBanner({
  variant,
  title,
  message,
  className = "",
}: WorkflowStatusBannerProps) {
  const styles = variantStyles[variant];

  return (
    <div className={`mb-4 p-3 ${styles.bg} border ${styles.border} rounded-lg ${className}`}>
      <div className={`flex items-center ${styles.text}`}>
        {styles.icon}
        <span className="text-sm font-medium">
          {title && <>{title}: </>}{message}
        </span>
      </div>
    </div>
  );
}

// Pre-configured banner messages for common workflow states
export const WorkflowBannerMessages = {
  deleted: {
    variant: "error" as BannerVariant,
    title: "Workflow Unavailable",
    message: "The workflow associated with this chat has been deleted and can no longer be continued.",
  },
  sharingDisabled: {
    variant: "warning" as BannerVariant,
    title: "Workflow Unavailable",
    message: "Chat sharing has been disabled for this workflow.",
  },
  validationFailed: {
    variant: "error" as BannerVariant,
    title: "Workflow Unavailable",
    message: "This workflow failed validation and cannot be used. Please contact the workflow owner.",
  },
  validating: {
    variant: "loading" as BannerVariant,
    message: "Validating workflow...",
  },
};

