import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Eye, Loader2 } from "lucide-react";
import { BuildingBlock } from "@/types/graph";
import { getCategoryDisplay } from "@/components/shared/helpers";
import ResourceDetailsModal from "./ResourceDetailsModal";

interface BuildingBlocksSidebarProps {
  buildingBlocks: BuildingBlock[];
  conditions: BuildingBlock[];
  isLoading: boolean;
  onDragStart: (event: React.DragEvent, block: BuildingBlock) => void;
  usedElementIds?: Set<string>; // Track which elements are currently used on canvas
}

const BuildingBlocksSidebar: React.FC<BuildingBlocksSidebarProps> = ({
  buildingBlocks,
  conditions,
  isLoading,
  onDragStart,
  usedElementIds = new Set<string>(),
}) => {
  const [selectedElement, setSelectedElement] = useState<BuildingBlock | null>(
    null,
  );
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);

  const handleViewDetails = (block: BuildingBlock) => {
    setSelectedElement(block);
    setIsDetailsModalOpen(true);
  };

  const handleDragStart = (event: React.DragEvent, block: BuildingBlock) => {
    // Prevent dragging if element is already used
    if (usedElementIds.has(block.id)) {
      event.preventDefault();
      return;
    }
    onDragStart(event, block);
  };

  return (
    <div className="w-80 h-full">
      <Card className="bg-background-card shadow-card border-gray-800 h-full flex flex-col">
        <CardHeader className="py-3 px-6 border-b border-gray-800">
          <CardTitle className="text-lg font-heading">Elements</CardTitle>
        </CardHeader>
        <CardContent className="p-4 flex-1 overflow-hidden flex flex-col">
          <div className="flex-1 min-h-0">
            <Tabs defaultValue="nodes" className="h-full flex flex-col">
              <TabsList className="grid w-full grid-cols-2 bg-gray-800">
                <TabsTrigger value="nodes" className="text-gray-300 data-[state=active]:text-white">
                  Nodes ({buildingBlocks.length})
                </TabsTrigger>
                <TabsTrigger value="conditions" className="text-gray-300 data-[state=active]:text-white">
                  Conditions ({conditions.length})
                </TabsTrigger>
              </TabsList>

              <TabsContent value="nodes" className="mt-4">
                {isLoading ? (
                  <div className="flex items-center justify-center h-32">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <span className="ml-2 text-sm text-gray-400">
                      Loading blocks...
                    </span>
                  </div>
                ) : (
                  <div className="space-y-2 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 430px)' }}>
                    {buildingBlocks.map((block) => {
                      const isUsed = usedElementIds.has(block.id);
                      return (
                        <Card
                          key={block.id}
                          className={`transition-colors ${
                            isUsed
                              ? 'bg-gray-900 border-gray-800 opacity-50 cursor-not-allowed'
                              : 'bg-gray-800 border-gray-700 hover:border-gray-600 cursor-grab active:cursor-grabbing'
                          }`}
                          draggable={!isUsed}
                          onDragStart={(event) => handleDragStart(event, block)}
                        >
                        <CardContent className="p-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 flex-1">
                              <div className="flex items-center justify-center w-8 h-8 rounded-full text-xs font-semibold text-white"
                                   style={{ backgroundColor: block.color }}>
                                {getCategoryDisplay(block.workspaceData?.category || "default").icon}
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <h4 className={`font-medium text-sm truncate ${isUsed ? 'text-gray-500' : 'text-white'}`}>
                                    {block.label}
                                  </h4>
                                  {isUsed && (
                                    <span className="text-xs bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded">
                                      Used
                                    </span>
                                  )}
                                </div>
                                <p className="text-xs text-gray-400 truncate">
                                  {block.workspaceData?.type || block.type}
                                </p>
                              </div>
                            </div>
                            {block.workspaceData && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0 text-gray-400 hover:text-white"
                                onClick={() => handleViewDetails(block)}
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                      );
                    })}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="conditions" className="mt-4">
                {isLoading ? (
                  <div className="flex items-center justify-center h-32">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <span className="ml-2 text-sm text-gray-400">
                      Loading conditions...
                    </span>
                  </div>
                ) : (
                  <div className="space-y-2 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 430px)' }}>
                    {conditions.map((condition) => {
                      const isUsed = usedElementIds.has(condition.id);
                      return (
                        <Card
                          key={condition.id}
                          className={`transition-colors ${
                            isUsed
                              ? 'bg-orange-950 border-orange-800 opacity-50 cursor-not-allowed'
                              : 'bg-orange-900 border-orange-700 hover:border-orange-600 cursor-grab active:cursor-grabbing'
                          }`}
                          draggable={!isUsed}
                          onDragStart={(event) => handleDragStart(event, condition)}
                        >
                        <CardContent className="p-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 flex-1">
                              <div className="flex items-center justify-center w-8 h-8 rounded-full text-xs font-semibold text-white bg-orange-600">
                                {getCategoryDisplay("conditions").icon}
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <h4 className={`font-medium text-sm truncate ${isUsed ? 'text-gray-500' : 'text-white'}`}>
                                    {condition.label}
                                  </h4>
                                  {isUsed && (
                                    <span className="text-xs bg-orange-800 text-orange-300 px-1.5 py-0.5 rounded">
                                      Used
                                    </span>
                                  )}
                                </div>
                                <p className="text-xs text-gray-400 truncate">
                                  {condition.workspaceData?.type || condition.type}
                                </p>
                              </div>
                            </div>
                            {condition.workspaceData && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0 text-gray-400 hover:text-white"
                                onClick={() => handleViewDetails(condition)}
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                      );
                    })}
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </div>

          {/* Fixed Instructions Footer */}
          {!isLoading && (
            <div className="mt-4 p-4 bg-gray-900 rounded-lg border border-gray-700 flex-shrink-0">
              <h4 className="font-medium text-white mb-2">How to use:</h4>
              <div className="text-xs text-gray-400 space-y-1">
                <p>• Drag nodes from sidebar to canvas</p>
                <p>• Connect nodes to build workflow</p>
                <p>• Drag conditions onto nodes for branching</p>
                <p>• Each node supports only one condition</p>
                <p>• Always start with User Input node</p>
                <p>• End workflow with Final Answer node</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Resource Details Modal */}
      <ResourceDetailsModal
        isOpen={isDetailsModalOpen}
        onClose={() => setIsDetailsModalOpen(false)}
        element={selectedElement}
      />
    </div>
  );
};

export default BuildingBlocksSidebar;