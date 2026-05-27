import React, { useEffect, useState } from 'react';
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { BuildingBlock } from '@/types/graph';
import { FileText } from 'lucide-react';
import { maskSecretFieldsInConfig } from '../utils/maskSecretFields';
import { simplifyConfigForDisplay } from '../utils/displayUtils';
import { ElementSchema } from '../types/workspace';
import { getElementSpec } from '@/api/catalog';
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
  const { getResourceName, resolveRefsInConfig } = useAgenticAI();

  // Fetch schema when modal opens and element is available
  useEffect(() => {
    if (isOpen && element?.workspaceData) {
      const fetchSchema = async () => {
        try {
          // Fetch the element-specific schema
          const schema = await getElementSpec<ElementSchema>(
            element.workspaceData!.category,
            element.workspaceData!.type,
          );
          setElementSchema(schema);
        } catch (error) {
          console.error('Error fetching element schema:', error);
          setElementSchema(null);
        }
      };
      fetchSchema();
    } else {
      setElementSchema(null);
    }
  }, [isOpen, element?.workspaceData?.category, element?.workspaceData?.type]);

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
              {element.workspaceData.config && (
                <div>
                  <label className="text-sm font-medium text-gray-400">Full Configuration</label>
                  <div className="mt-2 bg-gray-900 p-4 rounded-md">
                    <pre className="text-xs text-gray-300 whitespace-pre-wrap overflow-x-auto">
                      {JSON.stringify(
                        maskSecretFieldsInConfig(
                          simplifyConfigForDisplay(resolveRefsInConfig(element.workspaceData.config)), 
                          elementSchema?.config_schema
                        ), 
                        null, 
                        2
                      )}
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