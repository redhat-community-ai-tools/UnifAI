
import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { motion } from 'framer-motion';
import { 
  Settings, 
  Trash2, 
  LoaderCircle,
  FileText,
  Database,
  Eye,
  Users
} from 'lucide-react';
import SimpleTooltip from '@/components/shared/SimpleTooltip';
import { useShared } from '@/contexts/SharedContext';
import { useAgenticAI } from '@/contexts/AgenticAIContext';
import { ElementInstance, ElementType, ElementSchema } from '../../../types/workspace';
import { ElementData } from './ElementData';
import { formatConfigValue } from '../../../utils/maskSecretFields';

interface ElementGridProps {
  elements: ElementInstance[];
  elementType: ElementType;
  isLoading: boolean;
  onEditElement: (element: ElementInstance) => void;
  onDeleteElement: (rid: string) => void;
  elementSchema?: ElementSchema | null;
}

export const ElementGrid: React.FC<ElementGridProps> = ({
  elements,
  elementType,
  isLoading,
  onEditElement,
  onDeleteElement,
  elementSchema
}) => {
  const [selectedElement, setSelectedElement] = useState<ElementInstance | null>(null);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);
  const { openShareForItem } = useShared();
  const { getResourceName } = useAgenticAI();

  const handleViewDetails = (element: ElementInstance) => {
    setSelectedElement(element);
    setIsDetailsModalOpen(true);
  };

  const handleShareElement = (element: ElementInstance) => {
    openShareForItem({
      itemKind: 'resource',
      itemId: element.rid,
      itemName: element.name || `${elementType.name} Instance`,
    });
  };
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoaderCircle className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (elements.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-gray-400">
        <Database className="h-12 w-12 mb-4 opacity-50" />
        <h3 className="text-lg font-medium mb-2">No {elementType.name} instances found</h3>
        <p className="text-sm text-center max-w-md">
          Create your first {elementType.name.toLowerCase()} instance by clicking the "Create New" button above.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {elements.map((element, index) => (
        <motion.div
          key={element.rid}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: index * 0.1 }}
        >
          <Card className="bg-background-card shadow-card border-gray-800 h-full flex flex-col">
            <CardHeader className="py-4 px-6 border-b border-gray-800">
              <div className="flex justify-between items-start">
                <div className="flex items-center">
                  <FileText className="h-5 w-5 mr-2 text-primary" />
                  <CardTitle className="text-lg font-heading">
                    {element.name || `${elementType.name} Instance`}
                  </CardTitle>
                </div>
                <div className="flex items-center gap-2">
                  <SimpleTooltip content={<p>Share this resource</p>}>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="text-gray-400 hover:text-blue-400 hover:bg-blue-500/10"
                      onClick={() => handleShareElement(element)}
                    >
                      <Users className="h-4 w-4" />
                    </Button>
                  </SimpleTooltip>
                  <SimpleTooltip content={<p>Delete this resource</p>}>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="text-gray-400 hover:text-red-400"
                      onClick={() => onDeleteElement(element.rid)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </SimpleTooltip>
                </div>
              </div>
            </CardHeader>
            
            <CardContent className="p-4 flex-grow">
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-xs text-gray-500">ID:</span>
                  <span className="text-xs font-mono text-gray-300">
                    {element.rid.slice(0, 8)}...
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-gray-500">Type:</span>
                  <Badge variant="outline" className="text-xs">
                    {elementType.type}
                  </Badge>
                </div>
                {element.version && (
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-500">Version:</span>
                    <span className="text-xs text-gray-300">v{element.version}</span>
                  </div>
                )}
                {element.updated && (
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-500">Last Updated:</span>
                    <span className="text-xs text-gray-300">
                      {new Date(element.updated).toLocaleDateString()}
                    </span>
                  </div>
                )}
                {element.config && (
                  <div className="mt-3">
                    <span className="text-xs text-gray-500">Configuration:</span>
                    <div className="text-xs text-gray-300 mt-1 space-y-1">
                      {Object.keys(element.config).slice(0, 3).map((key) => {
                        const fieldSchema = elementSchema?.config_schema?.properties?.[key];
                        const rawValue = element.config[key];
                        const displayValue = Array.isArray(rawValue)
                          ? rawValue.map((item: any) => getResourceName(item)).join(', ')
                          : getResourceName(rawValue);
                        return (
                          <div key={key} className="flex justify-between">
                            <span className="truncate">{key}:</span>
                            <span className="text-gray-400 ml-2 truncate max-w-24" title={displayValue}>
                              {formatConfigValue(displayValue, fieldSchema)}
                            </span>
                          </div>
                        );
                      })}
                      {Object.keys(element.config).length > 3 && (
                        <div className="text-gray-500 text-center">
                          +{Object.keys(element.config).length - 3} more...
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>

            <CardFooter className="px-6 py-3 border-t border-gray-800 bg-background-dark">
              <div className="flex gap-2 w-full">
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="flex-1 flex items-center justify-center gap-2"
                  onClick={() => onEditElement(element)}
                >
                  <Settings className="h-3 w-3" />
                  Configure
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="flex-1 flex items-center justify-center gap-2"
                  onClick={() => handleViewDetails(element)}
                >
                  <Eye className="h-3 w-3" />
                  Details
                </Button>
              </div>
            </CardFooter>
          </Card>
        </motion.div>
      ))}
      
      {/* Element Details Modal */}
      <ElementData
        element={selectedElement}
        elementType={elementType}
        isOpen={isDetailsModalOpen}
        onOpenChange={setIsDetailsModalOpen}
        elementSchema={elementSchema}
      />
    </div>
  );
};
