import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Copy, Check, Share2, Loader2, AlertTriangle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import { getBlueprintInfo, setBlueprintMetadata } from "@/api/blueprints";
import { constructShareLink } from "@/utils/blueprintHelpers";
import SimpleTooltip from "@/components/shared/SimpleTooltip";
import { UmamiTrack } from "@/components/ui/umamitrack";
import { UmamiEvents } from "@/config/umamiEvents";
import { cn } from "@/lib/utils";

interface ShareWorkflowProps {
  blueprintId: string;
  className?: string;
  /** Whether the blueprint is valid (passed validation) */
  isValid?: boolean;
  /** Whether validation is currently in progress */
  isValidating?: boolean;
}

export default function ShareWorkflow({
  blueprintId,
  className = "",
  isValid = true,
  isValidating = false,
}: ShareWorkflowProps) {
  const [enabled, setEnabled] = useState(false);
  const [shareLink, setShareLink] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const { toast } = useToast();
  const { user } = useAuth();
  
  // Determine if the toggle should be disabled
  const isSharingDisabled = isLoading || isValidating || (!isValid && !enabled);
  
  // Show warning if sharing is enabled but blueprint is invalid
  const showInvalidWarning = enabled && !isValid && !isValidating;

  // Fetch current public_usage_scope status from blueprint metadata
  useEffect(() => {
    if (!blueprintId) return;
    
    const fetchStatus = async () => {
      try {
        const blueprintInfo = await getBlueprintInfo(blueprintId);
        const isPublic = blueprintInfo.metadata?.usageScope === "public";
        setEnabled(isPublic);
        setShareLink(isPublic ? constructShareLink(blueprintId) : null);
      } catch (error) {
        console.error("Error fetching blueprint info:", error);
      }
    };

    fetchStatus();
  }, [blueprintId]);

  const handleToggle = async (checked: boolean) => {
    setIsLoading(true);
    try {
      await setBlueprintMetadata(blueprintId, { usageScope: checked ? "public" : "private" }, user?.username || "");
      setEnabled(checked);
      setShareLink(checked ? constructShareLink(blueprintId) : null);
      toast({
        title: checked ? "Sharing Enabled" : "Sharing Disabled",
        description: checked 
          ? "Your workflow is now accessible via the share link"
          : "Your workflow is no longer accessible via the share link",
          variant: "destructive"
      });
    } catch (error: any) {
      // Show the same error message format as "Load Workflow"
      const errorMessage = error.response?.data?.error || "Failed to update sharing settings";
      toast({
        title: checked ? "Failed to load current workflow" : "Error",
        description: `Error: ${errorMessage}`,
        variant: "destructive",
      });
      // Don't toggle the switch if enabling failed
      if (checked) {
        // Keep the switch in the off position since enabling failed
        setEnabled(false);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyLink = () => {
    if (shareLink) {
      navigator.clipboard.writeText(shareLink);
      setCopied(true);
      toast({
        title: "Link Copied",
        description: "Share link copied to clipboard",
      });
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!blueprintId) {
    return null;
  }

  // Get tooltip content for disabled state
  const getTooltipContent = () => {
    if (isValidating) {
      return <p>Validating workflow...</p>;
    }
    if (!isValid && !enabled) {
      return <p>Sharing is disabled for invalid workflows. Please fix validation errors first.</p>;
    }
    return null;
  };

  const tooltipContent = getTooltipContent();
  const isClickable = !isValidating && !isSharingDisabled && !isLoading;


  return (
    <div className={`space-y-4 ${className}`}>
      <div
        className={cn(
          "flex items-center justify-between rounded-md px-1 py-1",
          isClickable ? "cursor-pointer hover:bg-background-surface" : "cursor-not-allowed opacity-60")}
        onClick={() => {if (!isClickable) return; handleToggle(!enabled);}}
      >
        <div className="flex items-center space-x-2">
          <Share2 className="h-4 w-4 text-gray-400" />
          
          <Label className={cn("text-sm font-medium pointer-events-none", !isClickable && "text-gray-400")}>
            {isLoading ? (enabled ? "Disabling..." : "Enabling...") : isValidating ? "Validating..." : "Enable Public Chat Sharing" }
          </Label>
        </div>
        
        <SimpleTooltip content={tooltipContent}>
          <span>
            <Switch
              id="share-toggle"
              checked={enabled}
              onCheckedChange={handleToggle}
              disabled={isSharingDisabled}
              onClick={(e) => e.stopPropagation()}
              className={`
                data-[state=unchecked]:bg-gray-400
                data-[state=unchecked]:data-[disabled]:bg-gray-200
                data-[state=checked]:bg-primary
                data-[disabled]:opacity-60
              `}
            />
          </span>
        </SimpleTooltip>
        
      </div>

      {/* Warning for shared but invalid blueprints */}
      {showInvalidWarning && (
        <div className="p-3 bg-yellow-900/20 border border-yellow-500/50 rounded-lg">
          <div className="flex items-start text-yellow-200">
            <AlertTriangle className="w-5 h-5 mr-2 flex-shrink-0 mt-0.5" />
            <div>
              <span className="text-sm font-medium block">
                Warning: This workflow is shared but has validation errors
              </span>
              <span className="text-xs text-yellow-300/80 mt-1 block">
                Users may encounter issues. Please fix the validation errors or disable sharing.
              </span>
            </div>
          </div>
        </div>
      )}

      {enabled && shareLink && (
        <div className="space-y-2">
          <Label className="text-xs text-gray-400">Share Link</Label>
          <div className="flex items-center space-x-2">
            <div className="flex-1 bg-background-dark border border-gray-700 rounded-md px-3 py-2 text-sm text-gray-300 font-mono break-all">
              {shareLink}
            </div>
            <UmamiTrack 
              event={UmamiEvents.WORKFLOW_SHARE_COPY_LINK}
              eventData={{ blueprintId }}
            >
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopyLink}
                className="border-gray-700 hover:bg-background-surface flex-shrink-0"
                title="Copy link"
              >
                {copied ? (
                  <Check className="h-4 w-4 text-green-400" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </Button>
            </UmamiTrack>
          </div>
          <p className="text-xs text-gray-500">
            Anyone with this link can chat with your workflow (authentication required)
          </p>
        </div>
      )}

      {!enabled && !isValidating && isValid && (
        <p className="text-xs text-gray-500">
          Enable sharing to generate a public chat link for this workflow
        </p>
      )}
      
      {!enabled && !isValidating && !isValid && (
        <p className="text-xs text-gray-500">
          Fix validation errors to enable sharing for this workflow
        </p>
      )}
    </div>
  );
}