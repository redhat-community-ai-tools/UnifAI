import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { FileText } from 'lucide-react';
import { ElementInstance, ElementType, ElementSchema } from '../../../types/workspace';
import { maskSecretFieldsInConfig } from '../../../utils/maskSecretFields';
import { simplifyConfigForDisplay } from '../../../utils/displayUtils';
import { useAgenticAI } from '@/contexts/AgenticAIContext';

interface ElementDataProps {
  element: ElementInstance | null;
  elementType: ElementType;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  elementSchema: ElementSchema | null | undefined;
}

export const ElementData: React.FC<ElementDataProps> = ({
  element,
  elementType,
  isOpen,
  onOpenChange,
  elementSchema
}) => {
  const { getResourceName, resolveRefsInConfig } = useAgenticAI();

  // Resolve refs in nested_refs to show names
  const resolvedNestedRefs = element?.nested_refs?.map((ref) => {
    return getResourceName(ref);
  });

  // Resolve refs in config for display, then simplify object arrays to just names
  const configWithResolvedRefs = element?.config 
    ? simplifyConfigForDisplay(resolveRefsInConfig(element.config))
    : null;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="bg-background-card border-gray-800 text-foreground max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            {element?.name || `${elementType.name} Details`}
          </DialogTitle>
        </DialogHeader>
        
        {element && (
          <div className="space-y-4">
            {/* Basic Info */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-gray-400">Resource ID</label>
                <p className="font-mono text-sm text-gray-300">{element.rid}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-400">Type</label>
                <p className="text-sm text-gray-300">{element.type}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-400">Version</label>
                <p className="text-sm text-gray-300">v{element.version || 1}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-400">Category</label>
                <p className="text-sm text-gray-300">{element.category}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-400">Created</label>
                <p className="text-sm text-gray-300">
                  {element.created ? new Date(element.created).toLocaleString() : 'N/A'}
                </p>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-400">Last Updated</label>
                <p className="text-sm text-gray-300">
                  {element.updated ? new Date(element.updated).toLocaleString() : 'N/A'}
                </p>
              </div>
            </div>

            {/* References */}
            {resolvedNestedRefs && resolvedNestedRefs.length > 0 && (
              <div>
                <label className="text-sm font-medium text-gray-400">Referenced Resources</label>
                <div className="mt-1 space-y-1">
                  {resolvedNestedRefs.map((ref, index) => (
                    <Badge key={index} variant="outline" className="mr-2">
                      {ref}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Configuration */}
            {configWithResolvedRefs && (
              <div>
                <label className="text-sm font-medium text-gray-400">Full Configuration</label>
                <div className="mt-2 bg-gray-900 p-4 rounded-md">
                  <pre className="text-xs text-gray-300 whitespace-pre-wrap overflow-x-auto">
                    {JSON.stringify(maskSecretFieldsInConfig(configWithResolvedRefs, elementSchema?.config_schema), null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
