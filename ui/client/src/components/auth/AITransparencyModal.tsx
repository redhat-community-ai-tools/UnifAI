import React, { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/hooks/use-toast";
import { approveUser } from "@/api/termsApproval";
import { AlertTriangle } from "lucide-react";

interface AITransparencyModalProps {
  open: boolean;
  onClose: () => void;
  username: string;
  onApproved?: (dontShowAgain: boolean) => void;
}

export default function AITransparencyModal({
  open,
  onClose,
  username,
  onApproved,
}: AITransparencyModalProps) {
  const [dontShowAgain, setDontShowAgain] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { toast } = useToast();

  const handleApprove = async () => {
    setIsSubmitting(true);
    try {
      if (dontShowAgain) {
        // Only call the API if user checked "don't show again"
        const result = await approveUser(username);
        if (!result.approved) {
          throw new Error("Failed to approve user");
        }
        // Show success toast
        toast({
          title: "✅ Preference saved",
          description: "You won't see this notification again on future logins.",
          variant: "default",
        });
      } else {
        // Show info toast for temporary acceptance
        toast({
          title: "ℹ️ Accepted",
          description: "You can continue using the system. This notification won't appear again during this session.",
          variant: "default",
        });
      }
      onApproved?.(dontShowAgain);
      onClose();
    } catch (error: any) {
      // Show error toast
      toast({
        title: "Failed to save preference",
        description: error?.response?.data?.error || error?.message || "The modal will appear again on next login.",
        variant: "destructive",
      });
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open}>
      <DialogContent 
        className="bg-background-card border-gray-800 max-w-2xl [&>button]:hidden"
        onInteractOutside={(e) => {
          // Prevent closing on backdrop click
          e.preventDefault();
        }}
        onEscapeKeyDown={(e) => {
          // Prevent closing on escape key
          e.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-yellow-500" />
            AI Disclosure
          </DialogTitle>
          <DialogDescription className="pt-4">
            <p className="text-sm text-muted-foreground leading-relaxed">
              You are about to use a Red Hat tool that utilizes AI technology to provide relevant information.
              <br /><br />
              By proceeding, you acknowledge that this tool and its outputs are for internal use only and may be shared only with individuals who have a legitimate business need.
              <br /><br />
              Do not include personal or customer-specific information in your input.
              <br /><br />
              All AI-generated responses must be reviewed and verified before use.
            </p>
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-center space-x-2 py-4">
          <Checkbox
            id="dont-show-again"
            checked={dontShowAgain}
            onCheckedChange={(checked) => setDontShowAgain(checked === true)}
          />
          <label
            htmlFor="dont-show-again"
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
          >
            Don't show message again
          </label>
        </div>
        <DialogFooter>
          <Button
            onClick={handleApprove}
            disabled={isSubmitting}
            className="min-w-[100px]"
          >
            {isSubmitting ? "Processing..." : "Accept"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

