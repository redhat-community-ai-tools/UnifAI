import React, { useEffect, useState } from 'react';
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { BuildingBlock } from '@/types/graph';
import { FileText } from 'lucide-react';
import { maskSecretFieldsInConfig } from '../utils/maskSecretFields';
import { filterHiddenFieldsInConfig, filterToFieldNames, simplifyConfigForDisplay } from '../utils/displayUtils';
import { getBuiltinVisibleFieldNames } from '@/lib/cardFields';
import { ElementSchema } from '../types/workspace';
import { getResource, getBuiltinSchema, getElementSpec } from '@/api/resources';
import { useAgenticAI } from '@/contexts/AgenticAIContext';

interface ResourceDetailsModalProps {
  isOpen: boolean;
  onClose: (open: boolean) => void;
  element: BuildingBlock | null;
}

const ResourceDetailsModal: React.FC<ResourceDetailsModalProps> = ({
  isOpen,
  onClose,
  element
}) => {
  const [elementSchema, setElementSchema] = useState<ElementSchema | null>(null);
  // Looked up here since the `BuildingBlock` passed in doesn't carry ownership info.
  const [ownership, setOwnership] = useState<'builtin' | 'custom' | null>(null);
  const { getResourceName, resolveRefsInConfig } = useAgenticAI();

  // Built-ins use `/resources/builtin.schema` instead of the plain
  // `/catalog/element.spec.get` schema so locked fields (e.g. `mcp_url`)
  // are correctly marked read-only rather than leaking into the allowlist below.
  useEffect(() => {
    const rid = element?.workspaceData?.rid;
    const category = element?.workspaceData?.category;
    const type = element?.workspaceData?.type;
    if (!isOpen || !rid || !category || !type) {
      setElementSchema(null);
      setOwnership(null);
      return;
    }

    let cancelled = false;

    (async () => {
      // Best-effort — an unresolvable rid falls back to non-builtin filtering below.
      let resolvedOwnership: 'builtin' | 'custom' | null = null;
      try {
        const resource = await getResource(rid);
        resolvedOwnership = resource.ownership ?? 'custom';
      } catch {
        resolvedOwnership = null;
      }
      if (cancelled) return;
      setOwnership(resolvedOwnership);

      try {
        if (resolvedOwnership === 'builtin') {
          const configSchema = await getBuiltinSchema(rid);
          if (!cancelled) {
            setElementSchema({ category, name: '', type, description: '', tags: [], config_schema: configSchema });
          }
        } else {
          const spec = await getElementSpec(category, type);
          if (!cancelled) setElementSchema(spec);
        }
      } catch (error) {
        console.error('Error fetching element schema:', error);
        if (!cancelled) setElementSchema(null);
      }
    })();

    return () => { cancelled = true; };
  }, [isOpen, element?.workspaceData?.rid, element?.workspaceData?.category, element?.workspaceData?.type]);

  // Built-ins only surface configurable + card-visible fields; other ownerships
  // just drop `hints.hidden` bookkeeping fields.
  const displayableConfig = element?.workspaceData?.config
    ? (() => {
        const resolved = simplifyConfigForDisplay(resolveRefsInConfig(element.workspaceData.config));
        return ownership === 'builtin'
          ? filterToFieldNames(resolved, getBuiltinVisibleFieldNames(elementSchema, resolved))
          : filterHiddenFieldsInConfig(resolved, elementSchema?.config_schema);
      })()
    : null;

  const visibleConfig = displayableConfig
    ? maskSecretFieldsInConfig(displayableConfig, elementSchema?.config_schema)
    : null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-background-card border-gray-800 text-foreground max-w-2xl max-h-[80vh] flex flex-col overflow-hidden p-0 gap-0">
        <DialogHeader className="px-6 pt-6 pb-4 flex-shrink-0 border-b border-gray-800">
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            {element?.label || 'Resource Details'}
          </DialogTitle>
        </DialogHeader>
        
        {element?.workspaceData && (
          <div className="flex-1 overflow-y-auto px-6 py-4 min-h-0">
            <div className="space-y-4">
              {/* Basic Info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-400">Resource ID</label>
                  <p className="font-mono text-sm text-gray-300">{element.workspaceData.rid}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-400">Type</label>
                  <p className="text-sm text-gray-300">{element.workspaceData.type}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-400">Version</label>
                  <p className="text-sm text-gray-300">v{element.workspaceData.version || 1}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-400">Category</label>
                  <p className="text-sm text-gray-300">{element.workspaceData.category}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-400">Created</label>
                  <p className="text-sm text-gray-300">
                    {element.workspaceData.created ? new Date(element.workspaceData.created).toLocaleString() : 'N/A'}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-400">Last Updated</label>
                  <p className="text-sm text-gray-300">
                    {element.workspaceData.updated ? new Date(element.workspaceData.updated).toLocaleString() : 'N/A'}
                  </p>
                </div>
              </div>

              {/* References */}
              {element.workspaceData.nested_refs && element.workspaceData.nested_refs.length > 0 && (
                <div>
                  <label className="text-sm font-medium text-gray-400">Referenced Resources</label>
                  <div className="mt-1 space-y-1">
                    {element.workspaceData.nested_refs.map((ref, index) => (
                      <Badge key={index} variant="outline" className="mr-2">
                        {getResourceName(ref)}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Configuration */}
              {visibleConfig && Object.keys(visibleConfig).length > 0 && (
                <div>
                  <label className="text-sm font-medium text-gray-400">Full Configuration</label>
                  <div className="mt-2 bg-gray-900 p-4 rounded-md">
                    <pre className="text-xs text-gray-300 whitespace-pre-wrap overflow-x-auto">
                      {JSON.stringify(visibleConfig, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default ResourceDetailsModal;