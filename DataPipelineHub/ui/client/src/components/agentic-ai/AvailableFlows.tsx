import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  Database,
  FileText,
  Zap,
  Filter,
  GitBranch,
  MessageSquare,
  BookOpen,
  Trash2,
  Users,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useShared } from "@/contexts/SharedContext";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import SimpleTooltip from "@/components/shared/SimpleTooltip";
import { GraphFlow, FlowObject } from "./graphs/interfaces";
import ReactFlowGraph from "./graphs/ReactFlowGraph";
import axios from "../../http/axiosAgentConfig";

// Helper function to convert GraphFlow to FlowObject
const convertGraphFlowToFlowObject = (
  graphFlow: GraphFlow,
  index: number,
  blueprintId?: string,
): FlowObject | null => {
  if (!graphFlow) return null;

  // Extract metadata
  const name = graphFlow.name || `Flow ${index + 1}`;
  const description = graphFlow.description || "No description available";

  // Generate a random icon for the flow
  const iconOptions: React.FC<{ className?: string }>[] = [
    Activity,
    Database,
    FileText,
    Zap,
    Filter,
    GitBranch,
    MessageSquare,
    BookOpen,
  ];
  const IconComponent = iconOptions[index % iconOptions.length];

  return {
    id: blueprintId || index.toString(), // Use blueprintId if available
    name,
    description,
    icon: <IconComponent className="h-4 w-4 mr-2" />,
    flow: {
      nodes: [],
      edges: [],
    },
  };
};

export interface AvailableFlowsProps {
  selectedFlow: FlowObject | null;
  onFlowSelect: (flow: FlowObject | null) => void;
  onFlowDelete?: (flow: FlowObject) => void;
  showActiveStatus?: boolean;
  showDeleteButton?: boolean;
  className?: string;
  height?: string;
  useResolvedEndpoint?: boolean; // If true, uses resolved endpoint, otherwise uses regular get endpoint
  graphProps?: {
    showControls?: boolean;
    showMiniMap?: boolean;
    showBackground?: boolean;
    interactive?: boolean;
    isLiveRequest?: boolean;
  };
}

export default function AvailableFlows({
  selectedFlow,
  onFlowSelect,
  onFlowDelete,
  showActiveStatus = false,
  showDeleteButton = false,
  className = "",
  height = "100%",
  useResolvedEndpoint = false,
  graphProps = {
    showControls: true,
    showMiniMap: false,
    showBackground: true,
    interactive: true,
    isLiveRequest: false,
  },
}: AvailableFlowsProps): React.ReactElement {
  // State for available graph flows
  const [graphFlows, setGraphFlows] = useState<FlowObject[]>([]);
  const [activeFlowIds, setActiveFlowIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [showDeleteModal, setShowDeleteModal] = useState<boolean>(false);
  const [flowToDelete, setFlowToDelete] = useState<FlowObject | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const { user } = useAuth();
  const { openShareForItem } = useShared();

  // Fetch available workflows from API
  const fetchAvailableFlows = async (): Promise<void> => {
    try {
      const userId = user?.username || "default";
      const endpoint = useResolvedEndpoint 
        ? `/blueprints/available.blueprints.resolved.get?userId=${userId}`
        : `/blueprints/available.blueprints.get?userId=${userId}`;
      
      const response = await axios.get(endpoint);
      const blueprints: Array<{ blueprint_id: string; spec_dict: GraphFlow }> = response.data;

      // Convert the blueprints to the format expected by the component
      const processedFlows = blueprints
        .map((blueprint) =>
          convertGraphFlowToFlowObject(blueprint.spec_dict, 0, blueprint.blueprint_id),
        )
        .filter((flow): flow is FlowObject => flow !== null);
      
      setGraphFlows(processedFlows);

      // Auto-select the first flow if none is selected and flows are available
      if (processedFlows.length > 0 && !selectedFlow) {
        onFlowSelect(processedFlows[0]);
      }
    } catch (error) {
      console.error("Error fetching available workflows:", error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch active flows (only if showActiveStatus is true)
  const fetchActiveFlows = async (): Promise<void> => {
    if (!showActiveStatus) return;

    try {
      const userId = user?.username || "default";
      const response = await axios.get(
        `/sessions/session.user.blueprints.get?userId=${userId}`
      );
      setActiveFlowIds(response.data || []);
    } catch (error) {
      console.error("Error fetching active flows:", error);
      setActiveFlowIds([]);
    }
  };

  // Effect to load graph flows from API
  useEffect(() => {
    setIsLoading(true);
    Promise.all([
      fetchAvailableFlows(),
      fetchActiveFlows(),
    ]).finally(() => {
      setIsLoading(false);
    });
  }, [user, useResolvedEndpoint]);

  const handleFlowSelect = (flow: FlowObject): void => {
    onFlowSelect(flow);
  };

  const isFlowActive = (flowId: string): boolean => {
    return activeFlowIds.includes(flowId);
  };

  const handleDeleteClick = (flow: FlowObject, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent flow selection when clicking delete
    setFlowToDelete(flow);
    setShowDeleteModal(true);
  };

  const handleShareClick = (flow: FlowObject, event: React.MouseEvent) => {
    event.stopPropagation(); // Prevent flow selection when clicking share
    openShareForItem({
      itemKind: 'blueprint',
      itemId: flow.id,
      itemName: flow.name,
    });
  };

  const handleDeleteConfirm = async () => {
    if (!flowToDelete) return;

    setIsDeleting(true);
    try {
      await axios.delete(`/blueprints/remove.blueprint?blueprintId=${flowToDelete.id}`);
      
      // Remove the deleted flow from the list
      setGraphFlows(prevFlows => prevFlows.filter(flow => flow.id !== flowToDelete.id));
      
      // If the deleted flow was selected, clear the selection
      if (selectedFlow?.id === flowToDelete.id) {
        onFlowSelect(null);
      }
      
      // Call the optional onFlowDelete callback
      if (onFlowDelete) {
        onFlowDelete(flowToDelete);
      }
      
      setShowDeleteModal(false);
      setFlowToDelete(null);
    } catch (error) {
      console.error('Error deleting blueprint:', error);
      // Handle error (we can consider show a toast notification here)
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDeleteCancel = () => {
    setShowDeleteModal(false);
    setFlowToDelete(null);
  };

  // Expose flows data for parent components
  useEffect(() => {
    // This allows parent components to access the flows data if needed
    if (typeof onFlowSelect === 'function' && graphFlows.length > 0 && !selectedFlow) {
      onFlowSelect(graphFlows[0]);
    }
  }, [graphFlows, selectedFlow, onFlowSelect]);

  if (isLoading) {
    return (
      <div className={`flex h-full overflow-hidden ${className}`} style={{ height }}>
        <div className="w-1/3 border-r border-gray-800 bg-background-dark flex flex-col min-h-0">
          <div className="py-3 px-4 border-b border-gray-800 bg-background-surface flex-shrink-0">
            <h3 className="text-sm font-medium">Available Workflows</h3>
          </div>
          <div className="flex-1 flex items-center justify-center overflow-hidden">
            <div className="text-gray-400">Loading flows...</div>
          </div>
        </div>
        <div className="flex-grow min-h-0 overflow-hidden">
          <div className="flex items-center justify-center h-full text-gray-400">
            Loading...
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className={`flex h-full overflow-hidden ${className}`} style={{ height }}>
        {/* Available Workflows Sidebar */}
        <div className="w-1/3 border-r border-gray-800 bg-background-dark flex flex-col min-h-0 relative">
          <div className="py-3 px-4 border-b border-gray-800 bg-background-surface flex-shrink-0">
            <h3 className="text-sm font-medium">Available Workflows ({graphFlows.length})</h3>
          </div>
          <div className="flex-1 overflow-y-auto py-2 max-h-full relative">
            {graphFlows.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <div className="text-gray-400">No flows available</div>
              </div>
            ) : (
              graphFlows.map((flow) => (
                <motion.div
                  key={flow.id}
                  className={`px-4 py-2 border-l-2 cursor-pointer ${
                    selectedFlow?.id === flow.id
                      ? "border-primary bg-primary/20"
                      : "border-transparent hover:bg-background-surface"
                  }`}
                  onClick={() => handleFlowSelect(flow)}
                  whileHover={{ x: 2 }}
                  transition={{ duration: 0.1 }}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center min-w-0 flex-1">
                      {flow.icon}
                      <span className="text-sm font-medium truncate">{flow.name}</span>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {showActiveStatus && isFlowActive(flow.id) && (
                        <span className="text-xs bg-primary text-white px-2 py-1 rounded-full">
                          Active
                        </span>
                      )}
                      <SimpleTooltip content={<p>Share this workflow</p>}>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0 hover:bg-blue-500/20 hover:text-blue-400"
                          onClick={(e) => handleShareClick(flow, e)}
                        >
                          <Users className="h-3 w-3" />
                        </Button>
                      </SimpleTooltip>
                      {showDeleteButton && (
                        <SimpleTooltip content={<p>Delete this workflow</p>}>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 w-6 p-0 hover:bg-red-500/20 hover:text-red-400"
                            onClick={(e) => handleDeleteClick(flow, e)}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </SimpleTooltip>
                      )}
                    </div>
                  </div>
                  <p className="text-xs text-gray-400 mt-1 truncate">
                    {flow.description}
                  </p>
                </motion.div>
              ))
            )}
          </div>
        </div>

        {/* Graph Visualization */}
        <div className="flex-grow min-h-0 overflow-hidden">
          {selectedFlow ? (
            <ReactFlowGraph
              blueprintId={selectedFlow.id}
              height="100%"
              {...graphProps}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400">
              Select a flow to view its visualization
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteButton && (
        <Dialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
          <DialogContent className="bg-background-card border-gray-800">
            <DialogHeader>
              <DialogTitle>Delete Flow</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete "{flowToDelete?.name}"?
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={handleDeleteCancel}
                disabled={isDeleting}
                className="bg-background-dark border-gray-700 hover:bg-background-surface"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDeleteConfirm}
                disabled={isDeleting}
              >
                {isDeleting ? "Deleting..." : "Confirm"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}
