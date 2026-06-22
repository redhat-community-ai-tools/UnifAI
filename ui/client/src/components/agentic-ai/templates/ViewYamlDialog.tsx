import React, { useMemo, useRef, useEffect } from 'react';
import yaml from 'js-yaml';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Copy, Check } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface ViewYamlDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  templateName: string;
  draft: Record<string, any> | null;
}

export const ViewYamlDialog: React.FC<ViewYamlDialogProps> = ({
  open,
  onOpenChange,
  templateName,
  draft,
}) => {
  const { toast } = useToast();
  const [copied, setCopied] = React.useState(false);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    };
  }, []);

  const yamlContent = useMemo(() => {
    if (!draft) return '';
    try {
      return yaml.dump(draft, { indent: 2, lineWidth: 120, noRefs: true });
    } catch {
      return JSON.stringify(draft, null, 2);
    }
  }, [draft]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(yamlContent);
      setCopied(true);
      toast({ title: 'Copied', description: 'YAML copied to clipboard.' });
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
      copyTimerRef.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      toast({ title: 'Error', description: 'Failed to copy.', variant: 'destructive' });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="dark-inputs max-w-4xl max-h-[85vh] flex flex-col bg-background border-border">
        <DialogHeader>
          <DialogTitle className="text-lg font-heading">
            Blueprint YAML — {templateName}
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Read-only view of this template's blueprint definition. Copy and adapt when creating new templates.
          </DialogDescription>
        </DialogHeader>

        <div className="flex justify-end">
          <Button variant="outline" size="sm" onClick={handleCopy} className="text-xs">
            {copied ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
            {copied ? 'Copied' : 'Copy YAML'}
          </Button>
        </div>

        <div className="flex-1 overflow-auto rounded-md border border-border bg-muted/50">
          <pre className="p-4 text-xs font-mono text-foreground whitespace-pre overflow-x-auto leading-relaxed">
            {yamlContent}
          </pre>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ViewYamlDialog;
