import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { ResourceDependencySummary } from "@/api/resources";

interface CascadePreviewTarget {
  resourceName: string;
  cascaded: ResourceDependencySummary[];
}

interface CascadeConfirmDialogProps {
  target: CascadePreviewTarget | null;
  isConfirming: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}

/**
 * Confirmation dialog shown before promoting/toggling a resource "available
 * to all" when doing so would also sweep along aggregated dependencies
 * (LLMs, providers, tools, etc.) that aren't already public built-ins.
 * Surfaces the "cascaded_resources" disclaimer *before* the mutation
 * happens, using the read-only ``builtin.cascade-preview`` endpoint,
 * instead of only informing the admin after the fact via a success toast.
 */
export function CascadeConfirmDialog({
  target,
  isConfirming,
  onOpenChange,
  onConfirm,
}: CascadeConfirmDialogProps) {
  return (
    <AlertDialog open={!!target} onOpenChange={(open) => !open && onOpenChange(open)}>
      <AlertDialogContent className="bg-background-card border-gray-800">
        <AlertDialogHeader>
          <AlertDialogTitle>Also make dependencies available to all?</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div>
              Making &quot;{target?.resourceName}&quot; available to all also requires
              making the following resources it uses available to all, since they
              aren&apos;t public built-ins yet:
              <ul className="list-disc list-inside mt-2 space-y-1">
                {target?.cascaded.map((r) => (
                  <li key={r.rid}>
                    {r.name} <span className="text-gray-500">({r.category})</span>
                  </li>
                ))}
              </ul>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel className="bg-background-dark border-gray-700 hover:bg-background-surface">
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={(e) => { e.preventDefault(); onConfirm(); }}
            disabled={isConfirming}
            className="bg-primary hover:bg-primary/80"
          >
            {isConfirming ? "Applying..." : "Make all available"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
