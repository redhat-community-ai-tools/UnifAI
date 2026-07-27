import React, { useState } from 'react';
import yaml from 'js-yaml';
import axios from '@/http/axiosAgentConfig';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, Info, Plus, X, CheckCircle2, LoaderCircle } from 'lucide-react';

interface CreateTemplateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: {
    draft: Record<string, any>;
    placeholders: Record<string, any>;
    metadata: Record<string, any>;
  }) => Promise<void>;
  isSubmitting: boolean;
}

export const CreateTemplateDialog: React.FC<CreateTemplateDialogProps> = ({
  open,
  onOpenChange,
  onSubmit,
  isSubmitting,
}) => {
  const [draftYaml, setDraftYaml] = useState('');
  const [placeholdersJson, setPlaceholdersJson] = useState('{\n  "categories": []\n}');
  const [author, setAuthor] = useState('');
  const [category, setCategory] = useState('');
  const [version, setVersion] = useState('1.0.0');
  const [tagInput, setTagInput] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [capabilityInput, setCapabilityInput] = useState('');
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [parseError, setParseError] = useState<string | null>(null);
  const [isValidatingYaml, setIsValidatingYaml] = useState(false);
  const [yamlValidationResult, setYamlValidationResult] = useState<{ valid: boolean; message: string } | null>(null);

  const handleValidateYaml = async () => {
    setParseError(null);
    setYamlValidationResult(null);

    let draft: Record<string, any>;
    try {
      draft = yaml.load(draftYaml) as Record<string, any>;
      if (!draft || typeof draft !== 'object') {
        setParseError('Blueprint YAML must be a valid YAML object.');
        return;
      }
    } catch (e: any) {
      setParseError(`Blueprint YAML parse error: ${e.message}`);
      return;
    }

    setIsValidatingYaml(true);
    try {
      const yamlForValidation = {
        name: draft.name || 'Untitled blueprint',
        description: draft.description || 'default',
        conditions: draft.conditions || [],
        nodes: draft.nodes || [],
        plan: draft.plan || [],
      };
      const yamlString = yaml.dump(yamlForValidation, { indent: 2, lineWidth: -1, noRefs: true, sortKeys: false });
      const response = await axios.post('/graph/validation/all.validate', yamlString, {
        headers: { 'Content-Type': 'text/plain' },
      });
      const { validation_result } = response.data;
      if (validation_result?.is_valid) {
        setYamlValidationResult({ valid: true, message: 'Blueprint YAML is valid.' });
      } else {
        const errors = validation_result?.errors || [];
        setYamlValidationResult({ valid: false, message: `Validation failed: ${errors.join('; ') || 'unknown error'}` });
      }
    } catch (err: any) {
      const msg = err.response?.data?.error || err.message || 'Validation request failed.';
      setYamlValidationResult({ valid: false, message: msg });
    } finally {
      setIsValidatingYaml(false);
    }
  };

  const handleAddItem = (
    value: string,
    list: string[],
    setList: React.Dispatch<React.SetStateAction<string[]>>,
    setInput: React.Dispatch<React.SetStateAction<string>>,
  ) => {
    const trimmed = value.trim();
    if (trimmed && !list.includes(trimmed)) {
      setList([...list, trimmed]);
      setInput('');
    }
  };

  const handleAddTag = () => handleAddItem(tagInput, tags, setTags, setTagInput);
  const handleAddCapability = () => handleAddItem(capabilityInput, capabilities, setCapabilities, setCapabilityInput);

  const handleSubmit = async () => {
    setParseError(null);

    let draft: Record<string, any>;
    try {
      draft = yaml.load(draftYaml) as Record<string, any>;
      if (!draft || typeof draft !== 'object') {
        setParseError('Blueprint YAML must be a valid YAML object.');
        return;
      }
    } catch (e: any) {
      setParseError(`Blueprint YAML parse error: ${e.message}`);
      return;
    }

    const missing: string[] = [];
    if (!draft.name || typeof draft.name !== 'string' || !draft.name.trim()) missing.push('name');
    if (!draft.description || typeof draft.description !== 'string' || !draft.description.trim()) missing.push('description');
    if (!Array.isArray(draft.nodes) || draft.nodes.length === 0) missing.push('nodes');
    if (!Array.isArray(draft.plan) || draft.plan.length === 0) missing.push('plan');
    if (missing.length > 0) {
      setParseError(`Blueprint YAML is missing required fields: ${missing.join(', ')}`);
      return;
    }

    let placeholders: Record<string, any>;
    try {
      placeholders = JSON.parse(placeholdersJson);
      if (!placeholders || typeof placeholders !== 'object' || Array.isArray(placeholders)) {
        setParseError('Placeholders JSON must be a JSON object.');
        return;
      }
    } catch (e: any) {
      setParseError(`Placeholders JSON parse error: ${e.message}`);
      return;
    }

    const metadata = {
      author: author || undefined,
      category: category || undefined,
      version,
      tags,
      output_capabilities: capabilities,
      is_public: true,
    };

    await onSubmit({ draft, placeholders, metadata });
  };

  const resetForm = () => {
    setDraftYaml('');
    setPlaceholdersJson('{\n  "categories": []\n}');
    setAuthor('');
    setCategory('');
    setVersion('1.0.0');
    setTagInput('');
    setTags([]);
    setCapabilityInput('');
    setCapabilities([]);
    setParseError(null);
    setYamlValidationResult(null);
  };

  const handleClose = () => {
    if (!isSubmitting) {
      resetForm();
      onOpenChange(false);
    }
  };

  React.useEffect(() => {
    if (!open) resetForm();
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="dark-inputs max-w-4xl max-h-[90vh] flex flex-col bg-background text-foreground border-border">
        <DialogHeader>
          <DialogTitle className="text-lg font-heading">Add Template</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Create a new workflow template. Paste the blueprint YAML, define placeholders, and set metadata.
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="metadata" className="flex-1 overflow-hidden flex flex-col">
          <TabsList className="bg-muted border border-border">
            <TabsTrigger value="metadata">Metadata</TabsTrigger>
            <TabsTrigger value="blueprint">Blueprint (YAML)</TabsTrigger>
            <TabsTrigger value="placeholders">Placeholders (JSON)</TabsTrigger>
          </TabsList>

          <TabsContent value="metadata" className="flex-1 overflow-auto mt-4 space-y-4 pr-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Author</Label>
                <Input
                  value={author}
                  onChange={(e) => setAuthor(e.target.value)}
                  placeholder="e.g. UnifAI"
                  className="bg-muted/50 border-border"
                />
              </div>
              <div className="space-y-2">
                <Label>Category</Label>
                <Input
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder="e.g. SRE & Incident Response"
                  className="bg-muted/50 border-border"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Version</Label>
                <Input
                  value={version}
                  onChange={(e) => setVersion(e.target.value)}
                  placeholder="1.0.0"
                  className="max-w-[200px] bg-muted/50 border-border"
                />
            </div>

            <div className="space-y-2">
              <Label>Tags</Label>
              <div className="flex gap-2">
                <Input
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                  placeholder="Add a tag..."
                  className="bg-muted/50 border-border"
                />
                <Button type="button" variant="outline" size="sm" onClick={handleAddTag}>
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
              {tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="text-xs bg-primary/10 text-primary">
                      #{tag}
                      <button aria-label={`Remove tag ${tag}`} onClick={() => setTags(tags.filter(t => t !== tag))} className="ml-1 hover:text-foreground">
                        <X className="h-2.5 w-2.5" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label>Output Capabilities</Label>
              <div className="flex gap-2">
                <Input
                  value={capabilityInput}
                  onChange={(e) => setCapabilityInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddCapability())}
                  placeholder="Add a capability..."
                  className="bg-muted/50 border-border"
                />
                <Button type="button" variant="outline" size="sm" onClick={handleAddCapability}>
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
              {capabilities.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {capabilities.map((cap) => (
                    <Badge key={cap} variant="secondary" className="text-xs bg-primary/10 text-primary">
                      {cap}
                      <button aria-label={`Remove capability ${cap}`} onClick={() => setCapabilities(capabilities.filter(c => c !== cap))} className="ml-1 hover:text-foreground">
                        <X className="h-2.5 w-2.5" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="blueprint" className="flex-1 overflow-hidden mt-4 space-y-2">
            <Textarea
              value={draftYaml}
              onChange={(e) => { setDraftYaml(e.target.value); setYamlValidationResult(null); }}
              placeholder={"# Blueprint YAML\n# Must include: name, description, providers, llms, tools, nodes, plan\nname: My Template\ndescription: ...\nllms:\n  - rid: llm_rid\n    name: ...\nnodes:\n  - rid: ...\nplan:\n  - uid: ..."}
              className="h-[360px] font-mono text-xs bg-muted/50 border-border text-foreground placeholder:text-muted-foreground resize-none"
              spellCheck={false}
            />
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleValidateYaml}
                disabled={isValidatingYaml || !draftYaml.trim()}
              >
                {isValidatingYaml ? <LoaderCircle className="h-3 w-3 mr-1 animate-spin" /> : <CheckCircle2 className="h-3 w-3 mr-1" />}
                {isValidatingYaml ? 'Validating...' : 'Validate YAML'}
              </Button>
              {yamlValidationResult?.valid && (
                <span className="text-xs text-green-500">
                  {yamlValidationResult.message}
                </span>
              )}
            </div>
          </TabsContent>

          <TabsContent value="placeholders" className="flex-1 overflow-hidden mt-4 space-y-2">
            <div className="flex items-start gap-2 p-3 rounded-md border border-blue-500/30 bg-blue-500/10 text-xs text-muted-foreground">
              <Info className="h-4 w-4 shrink-0 mt-0.5 text-blue-500" />
              <span>
                Placeholders define the fields users must fill when instantiating this template.
                Ensure field paths match the resource RIDs in your blueprint — misconfigured
                placeholders will cause errors at instantiation time.
              </span>
            </div>
            <Textarea
              value={placeholdersJson}
              onChange={(e) => setPlaceholdersJson(e.target.value)}
              placeholder={'{\n  "categories": [\n    { "category": "llms", "resources": [{ "rid": "llm_rid", "placeholders": [...] }] }\n  ]\n}'}
              className="h-[360px] font-mono text-xs bg-muted/50 border-border text-foreground placeholder:text-muted-foreground resize-none"
              spellCheck={false}
            />
          </TabsContent>
        </Tabs>

        {parseError && (
          <div className="flex items-start gap-2 p-3 rounded-md border border-destructive/50 bg-destructive/10 text-destructive text-xs">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span className="font-mono">{parseError}</span>
          </div>
        )}

        <DialogFooter className="flex items-center gap-3 sm:justify-between">
          <span className="text-xs text-muted-foreground">
            {!draftYaml.trim()
              ? 'Paste a blueprint YAML to get started.'
              : yamlValidationResult === null
                ? 'Validate your YAML before creating.'
                : yamlValidationResult.valid
                  ? ''
                  : <span className="text-destructive">{yamlValidationResult.message}</span>}
          </span>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={handleClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isSubmitting || !draftYaml.trim() || yamlValidationResult?.valid !== true}>
              {isSubmitting ? 'Creating...' : 'Create Template'}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default CreateTemplateDialog;
