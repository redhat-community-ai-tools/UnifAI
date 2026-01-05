
import { Button } from "@/components/ui/button";
import { FaTrash } from "react-icons/fa";

interface BulkDeleteButtonProps {
  selectedCount: number;
  onClick: () => void;
  disabled?: boolean;
  itemName?: string; // e.g., "document" or "channel", defaults to "Selected"
  className?: string;
}

export function BulkDeleteButton({
  selectedCount,
  onClick,
  disabled = false,
  itemName = "Selected",
  className = "",
}: BulkDeleteButtonProps) {
  return (
    <Button
      variant="outline"
      onClick={onClick}
      disabled={disabled || selectedCount === 0}
      className={`border-primary/40 bg-primary/5 text-primary/100 hover:bg-primary/25 hover:border-primary/60 hover:text-primary ${className}`}
    >
      <FaTrash className="mr-2 h-3 w-3" />
      Delete {selectedCount} {itemName}
    </Button>
  );
}