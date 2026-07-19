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
import type { ResourceItem } from "./types";

interface DeleteResourceDialogProps {
  target: ResourceItem | null;
  isDeleting: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}

/** Confirmation dialog for deleting a built-in resource. */
export function DeleteResourceDialog({
  target,
  isDeleting,
  onOpenChange,
  onConfirm,
}: DeleteResourceDialogProps) {
  return (
    <AlertDialog open={!!target} onOpenChange={(open) => !open && onOpenChange(open)}>
      <AlertDialogContent className="bg-background-card border-gray-800">
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Resource</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete &quot;
            {target?.name || "Unnamed"}&quot;?
            <br />
            <br />
            <strong>This action is irreversible.</strong>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel className="bg-background-dark border-gray-700 hover:bg-background-surface">
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={isDeleting}
            className="bg-red-600 hover:bg-red-700 text-white"
          >
            {isDeleting ? "Deleting..." : "Delete"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
