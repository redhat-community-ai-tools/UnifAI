import { useState } from "react";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { X } from "lucide-react";
import { Document } from "@/types";
import { updateDocument } from "@/api/docs";
import { toast } from "@/hooks/use-toast";

interface EditDocumentModalProps {
  document: Document;
  open: boolean;
  onClose: () => void;
  onUpdated: () => void;
}

export const EditDocumentModal: React.FC<EditDocumentModalProps> = ({
  document,
  open,
  onClose,
  onUpdated,
}) => {
  const [tags, setTags] = useState<string[]>(document.tags);
  const [tagInput, setTagInput] = useState("");
  const [loading, setLoading] = useState(false);

  const addTag = () => {
    const trimmed = tagInput.trim();
    if (trimmed && !tags.includes(trimmed)) {
      setTags([...tags, trimmed]);
      setTagInput("");
    }
  };

  const removeTag = (tagToRemove: string) => {
    setTags(tags.filter((t) => t !== tagToRemove));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addTag();
    }
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      await updateDocument(document.source_id, { tags });
      toast({ title: "Success", description: "Document updated successfully" });
      onUpdated();
      onClose();
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Error",
        description: "Failed to update document",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setTags(document.tags);
      setTagInput("");
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit Document</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <p className="text-sm text-muted-foreground mb-1">Document</p>
            <p className="font-medium truncate">{document.source_name}</p>
          </div>

          <div>
            <p className="text-sm text-muted-foreground mb-2">Tags</p>
            
            {tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-3">
                {tags.map((tag) => (
                  <Badge key={tag} variant="secondary" className="gap-1 pr-1">
                    {tag}
                    <button
                      onClick={() => removeTag(tag)}
                      className="ml-1 hover:text-destructive"
                      disabled={loading}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}

            <div className="flex gap-2">
              <Input
                placeholder="Add a tag..."
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading}
                className="flex-1 dark:!text-white"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={addTag}
                disabled={!tagInput.trim() || loading}
              >
                Add
              </Button>
            </div>
          </div>
        </div>

        <DialogFooter className="mt-4">
          <Button variant="ghost" onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={loading}>
            {loading ? "Saving..." : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
