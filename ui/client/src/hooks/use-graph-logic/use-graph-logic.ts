/**
 * Graph logic hook for managing blueprint graph state
 * Handles node/edge operations, YAML flow state, validation, and persistence
 */

import { useState, useCallback, useEffect } from "react";
import {
  Node,
  Edge,
  Connection,
  addEdge,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "reactflow";
import { useToast } from "@/hooks/use-toast";
import { BuildingBlock } from "@/types/graph";
import { getCategoryDisplay } from "@/components/shared/helpers";
import { useAuth } from "@/contexts/AuthContext";
import * as yaml from "js-yaml";
import {
  fetchBlueprint,
  fetchAllResources,
  updateBlueprint,
  saveBlueprint,
  validateBlueprintGraph,
} from "@/api/agentic";

// Import helpers from graph-logic module
import {
  YamlFlowState,
  YamlFlowPlanStep,
  UseGraphLogicOptions,
  ConditionalEdgeModalState,
  NodeRid,
} from "./types";
import {
  DEFAULT_YAML_FLOW_STATE,
  BUILTIN_NODES,
  NODE_DIMENSIONS,
} from "./constants";
import {
  calculateNodePositions,
  createEdgesFromPlan,
  buildLookupMaps,
} from "./layout-helpers";
import {
  removeNodeFromYamlFlow,
  removeEdgeFromYamlFlow,
  addConnectionToYamlFlow,
  addNodeToYamlFlow,
  addConditionToYamlFlow,
  removeConditionFromYamlFlow,
  addConditionalBranchToYamlFlow,
} from "./yaml-flow-helpers";
import {
  transformResourceToBlock,
  filterBlocksByCategory,
  findBlockByRid,
} from "./resource-helpers";

export const useGraphLogic = (options: UseGraphLogicOptions = {}) => {
  const { editBlueprintId } = options;

  const { toast } = useToast();
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [nodeId, setNodeId] = useState(1);
  const [selectedNodes, setSelectedNodes] = useState<string[]>([]);
  const [selectedEdges, setSelectedEdges] = useState<string[]>([]);
  const [buildingBlocksData, setBuildingBlocksData] = useState<BuildingBlock[]>([]);
  const [allBlocksData, setAllBlocksData] = useState<BuildingBlock[]>([]);
  const [conditionsData, setConditionsData] = useState<BuildingBlock[]>([]);
  const [isLoadingBlocks, setIsLoadingBlocks] = useState(true);

  // Conditional edge modal state
  const [conditionalEdgeModal, setConditionalEdgeModal] = useState<ConditionalEdgeModalState>({
    isOpen: false,
    sourceNodeId: "",
    targetNodeId: "",
    conditionType: "",
    existingBranches: [],
  });

  // YAML flow state management
  const [yamlFlow, setYamlFlow] = useState<YamlFlowState>(DEFAULT_YAML_FLOW_STATE);

  // Graph validation state
  const [isGraphValid, setIsGraphValid] = useState(false);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [fixSuggestions, setFixSuggestions] = useState<any[]>([]);
  const [isValidating, setIsValidating] = useState(false);

  // Save modal state
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Edit mode state
  const [isEditMode, setIsEditMode] = useState(!!editBlueprintId);
  const [currentBlueprintId, setCurrentBlueprintId] = useState<string | null>(
    editBlueprintId || null
  );
  const [isLoadingBlueprint, setIsLoadingBlueprint] = useState(false);
  const [blueprintName, setBlueprintName] = useState("");
  const [blueprintDescription, setBlueprintDescription] = useState("");

  // Drag state to track what type of item is being dragged
  const [isDraggingCondition, setIsDraggingCondition] = useState(false);

  const { user } = useAuth();
  const USER_ID = user?.username || "default";

  // ─────────────────────────────────────────────────────────────────────────────
  // VALIDATION
  // ─────────────────────────────────────────────────────────────────────────────

  const validateGraph = useCallback(async () => {
    if (nodes.length <= 2) {
      setIsGraphValid(false);
      setValidationResult(null);
      setFixSuggestions([]);
      return;
    }

    try {
      setIsValidating(true);

      const yamlFlowForValidation = {
        name: yamlFlow.name || "Untitled blueprint",
        description: yamlFlow.description || "default",
        conditions: yamlFlow.conditions || [],
        nodes: yamlFlow.nodes || [],
        plan: yamlFlow.plan || [],
      };

      const yamlString = yaml.dump(yamlFlowForValidation, {
        indent: 2,
        lineWidth: -1,
        noRefs: true,
        sortKeys: false,
      });

      const validationResponse = await validateBlueprintGraph(yamlString);
      const { validation_result, fix_suggestions } = validationResponse;

      setValidationResult(validation_result);
      setFixSuggestions(fix_suggestions || []);
      setIsGraphValid(validation_result?.is_valid || false);
    } catch (error) {
      console.error("Error validating graph:", error);
      setIsGraphValid(false);
      setValidationResult(null);
      setFixSuggestions([]);
    } finally {
      setIsValidating(false);
    }
  }, [yamlFlow, nodes.length]);

  // ─────────────────────────────────────────────────────────────────────────────
  // NODE OPERATIONS
  // ─────────────────────────────────────────────────────────────────────────────

  const deleteNode = useCallback(
    (nodeIdToDelete: string) => {
      if (nodeIdToDelete === "user_input" || nodeIdToDelete === "finalize") {
        toast({
          title: "❌ Cannot Delete Required Node",
          description: "User Input and Final Answer nodes are required and cannot be deleted",
          variant: "destructive",
        });
        return;
      }

      setNodes((currentNodes) =>
        currentNodes.filter((node) => node.id !== nodeIdToDelete)
      );

      setEdges((currentEdges) => {
        const updatedEdges = currentEdges.filter(
          (edge) => edge.source !== nodeIdToDelete && edge.target !== nodeIdToDelete
        );
        setYamlFlow((prevFlow) => removeNodeFromYamlFlow(prevFlow, nodeIdToDelete));
        return updatedEdges;
      });
    },
    [setNodes, setEdges, toast]
  );

  const deleteEdge = useCallback(
    (edgeId: string) => {
      setEdges((currentEdges) => {
        const edgeToDelete = currentEdges.find((edge) => edge.id === edgeId);
        if (!edgeToDelete) return currentEdges;

        const updatedEdges = currentEdges.filter((edge) => edge.id !== edgeId);
        setYamlFlow((prevFlow) =>
          removeEdgeFromYamlFlow(prevFlow, edgeToDelete.source, edgeToDelete.target)
        );
        return updatedEdges;
      });
    },
    [setEdges]
  );

  // ─────────────────────────────────────────────────────────────────────────────
  // CONDITION OPERATIONS
  // ─────────────────────────────────────────────────────────────────────────────

  const attachConditionToNode = useCallback(
    (nodeId: string, condition: any) => {
      const targetNode = nodes.find((node) => node.id === nodeId);
      if (targetNode?.data?.referencedConditions?.length > 0) {
        toast({
          title: "❌ Condition Limit Reached",
          description: "Each node can only have one condition attached. Remove the existing condition first.",
          variant: "destructive",
        });
        return;
      }

      setNodes((prevNodes) =>
        prevNodes.map((node) =>
          node.id === nodeId
            ? { ...node, data: { ...node.data, referencedConditions: [condition] } }
            : node
        )
      );

      const conditionRid = condition.workspaceData?.rid || condition.id;
      setYamlFlow((prevFlow) =>
        addConditionToYamlFlow(prevFlow, nodeId, conditionRid, {
          name: condition.workspaceData?.name || condition.label,
          type: condition.workspaceData?.type,
          config: condition.workspaceData?.config,
        })
      );
    },
    [nodes, toast, setNodes]
  );

  const removeConditionFromNode = useCallback(
    (nodeId: string, conditionRid: string) => {
      setNodes((prevNodes) =>
        prevNodes.map((node) =>
          node.id === nodeId
            ? {
                ...node,
                data: {
                  ...node.data,
                  referencedConditions: (node.data.referencedConditions || []).filter(
                    (condition: any) =>
                      (condition.workspaceData?.rid || condition.id) !== conditionRid
                  ),
                },
              }
            : node
        )
      );
      setEdges((prevEdges) => prevEdges.filter((edge) => edge.source !== nodeId));
      setYamlFlow((prevFlow) => removeConditionFromYamlFlow(prevFlow, nodeId, conditionRid));
    },
    [setNodes, setEdges]
  );

  // ─────────────────────────────────────────────────────────────────────────────
  // NODE CREATION
  // ─────────────────────────────────────────────────────────────────────────────

  const createNodeFromBlock = useCallback(
    (
      block: BuildingBlock | null,
      uid: string,
      position: { x: number; y: number },
      options: {
        label?: string;
        color?: string;
        workspaceData?: any;
        referencedConditions?: any[];
      } = {}
    ): Node => {
      const label = options.label || block?.label || uid;
      const color = options.color || block?.color || "#6B7280";
      const workspaceData = options.workspaceData || block?.workspaceData;

      return {
        id: uid,
        type: "custom",
        position,
        data: {
          label,
          icon: getCategoryDisplay(workspaceData?.category || "nodes").icon,
          color,
          style: `bg-gray-800 text-white border`,
          description: block?.description || workspaceData?.name || "",
          workspaceData,
          onDelete: deleteNode,
          allBlocks: allBlocksData,
          referencedConditions: options.referencedConditions || [],
          onAttachCondition: attachConditionToNode,
          onRemoveCondition: removeConditionFromNode,
        },
      };
    },
    [allBlocksData, deleteNode, attachConditionToNode, removeConditionFromNode]
  );

  const initializeDefaultNodes = useCallback(() => {
    const userInputNode = createNodeFromBlock(
      null,
      "user_input",
      { x: 200, y: 100 },
      BUILTIN_NODES.user_question
    );
    const finalizeNode = createNodeFromBlock(
      null,
      "finalize",
      { x: 200, y: 900 },
      BUILTIN_NODES.final_answer
    );
    setNodes([userInputNode, finalizeNode]);
    setNodeId(3);
  }, [createNodeFromBlock, setNodes]);

  // ─────────────────────────────────────────────────────────────────────────────
  // DATA LOADING
  // ─────────────────────────────────────────────────────────────────────────────

  const loadBuildingBlocks = useCallback(async () => {
    try {
      setIsLoadingBlocks(true);
      const resources = await fetchAllResources(USER_ID);
      const allBlocks = resources.map(transformResourceToBlock);

      setAllBlocksData(allBlocks);
      setBuildingBlocksData(filterBlocksByCategory(allBlocks, "nodes"));
      setConditionsData(filterBlocksByCategory(allBlocks, "conditions"));
    } catch (error) {
      console.error("Error loading workspace resources:", error);
      toast({
        title: "❌ Error Loading Resources",
        description: "Failed to load workspace resources from server",
        variant: "destructive",
      });
    } finally {
      setIsLoadingBlocks(false);
    }
  }, [toast, USER_ID]);

  const loadBlueprintForEdit = useCallback(
    async (blueprintId: string, allBlocks: BuildingBlock[]) => {
      try {
        setIsLoadingBlueprint(true);
        const { spec_dict } = await fetchBlueprint(blueprintId);

        // Store metadata
        setBlueprintName(spec_dict.name || "");
        setBlueprintDescription(spec_dict.description || "");
        setCurrentBlueprintId(blueprintId);
        setIsEditMode(true);

        // Set yamlFlow directly - source of truth for saving
        setYamlFlow({
          name: spec_dict.name || "",
          description: spec_dict.description || "",
          nodes: spec_dict.nodes || [],
          plan: spec_dict.plan || [],
          conditions: spec_dict.conditions || [],
        });

        // Build lookup maps and calculate positions
        const { nodeDefMap, condDefMap } = buildLookupMaps(spec_dict);
        const positions = calculateNodePositions(spec_dict.plan || [], nodeDefMap);

        // Create nodes
        const reactFlowNodes: Node[] = (spec_dict.plan || []).map((step: YamlFlowPlanStep) => {
          const nodeRid = step.node;
          const matchingBlock = findBlockByRid(allBlocks, nodeRid);
          const builtinNode =
            nodeRid === NodeRid.USER_QUESTION
              ? BUILTIN_NODES[NodeRid.USER_QUESTION]
              : nodeRid === NodeRid.FINAL_ANSWER
              ? BUILTIN_NODES[NodeRid.FINAL_ANSWER]
              : null;

          // Build referenced conditions
          let referencedConditions: any[] = [];
          if (step.exit_condition) {
            const condBlock = allBlocks.find(
              (b) =>
                b.workspaceData?.category === "conditions" &&
                b.workspaceData?.rid === step.exit_condition
            );
            const condDef = condDefMap[step.exit_condition];
            if (condBlock || condDef) {
              referencedConditions = [
                {
                  id: step.exit_condition,
                  label: condBlock?.label || condDef?.name,
                  workspaceData: condBlock?.workspaceData || {
                    rid: step.exit_condition,
                    name: condDef?.name,
                    type: condDef?.type,
                    config: condDef?.config,
                    category: "conditions",
                  },
                },
              ];
            }
          }

          return createNodeFromBlock(
            matchingBlock || null,
            step.uid,
            positions[step.uid] || { x: 200, y: 100 },
            builtinNode ? { ...builtinNode, referencedConditions } : { referencedConditions }
          );
        });

        const reactFlowEdges = createEdgesFromPlan(spec_dict.plan || []);

        setNodes(reactFlowNodes);
        setEdges(reactFlowEdges);
        setNodeId(reactFlowNodes.length + 1);

        toast({
          title: "✅ Blueprint Loaded",
          description: `"${spec_dict.name}" loaded for editing`,
          duration: 3000,
        });
      } catch (error) {
        console.error("Error loading blueprint for edit:", error);
        toast({
          title: "❌ Error Loading Blueprint",
          description: "Failed to load blueprint for editing",
          variant: "destructive",
        });
        initializeDefaultNodes();
      } finally {
        setIsLoadingBlueprint(false);
      }
    },
    [toast, createNodeFromBlock, initializeDefaultNodes, setNodes, setEdges]
  );

  // ─────────────────────────────────────────────────────────────────────────────
  // INITIALIZATION EFFECTS
  // ─────────────────────────────────────────────────────────────────────────────

  useEffect(() => {
    const initializeGraph = async () => {
      await loadBuildingBlocks();
      if (editBlueprintId && allBlocksData.length > 0) {
        await loadBlueprintForEdit(editBlueprintId, allBlocksData);
      } else if (!editBlueprintId) {
        initializeDefaultNodes();
      }
    };
    initializeGraph();
  }, [loadBuildingBlocks]);

  useEffect(() => {
    if (editBlueprintId && allBlocksData.length > 0 && !isLoadingBlueprint && nodes.length === 0) {
      loadBlueprintForEdit(editBlueprintId, allBlocksData);
    }
  }, [editBlueprintId, allBlocksData, isLoadingBlueprint, nodes.length, loadBlueprintForEdit]);

  useEffect(() => {
    if (yamlFlow.plan && yamlFlow.plan.length > 2) {
      const validationTimeout = setTimeout(() => validateGraph(), 100);
      return () => clearTimeout(validationTimeout);
    }
  }, [yamlFlow, validateGraph]);

  // ─────────────────────────────────────────────────────────────────────────────
  // CONNECTION HANDLING
  // ─────────────────────────────────────────────────────────────────────────────

  const onConnect = useCallback(
    async (params: Connection) => {
      const sourceNode = nodes.find((node) => node.id === params.source);
      const hasCondition =
        sourceNode?.data?.referencedConditions && sourceNode.data.referencedConditions.length > 0;

      if (hasCondition) {
        const condition = sourceNode.data.referencedConditions[0];
        const conditionType = condition.workspaceData?.type || condition.type;
        const existingEdges = edges.filter((edge) => edge.source === params.source);
        const existingBranches = existingEdges.map((edge) => edge.data?.branch).filter(Boolean);

        setConditionalEdgeModal({
          isOpen: true,
          sourceNodeId: params.source || "",
          targetNodeId: params.target || "",
          conditionType,
          existingBranches,
        });
        return;
      }

      const newEdge = addEdge(params, edges);
      setEdges(newEdge);
      setYamlFlow((prevFlow) =>
        addConnectionToYamlFlow(prevFlow, params.source!, params.target!)
      );
    },
    [setEdges, edges, nodes]
  );

  // ─────────────────────────────────────────────────────────────────────────────
  // DRAG & DROP
  // ─────────────────────────────────────────────────────────────────────────────

  const onDragOver = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      if (isDraggingCondition) {
        const reactFlowBounds = event.currentTarget.getBoundingClientRect();
        const position = {
          x: event.clientX - reactFlowBounds.left - 75,
          y: event.clientY - reactFlowBounds.top - 25,
        };

        const targetNode = nodes.find((node) => {
          return (
            position.x >= node.position.x - NODE_DIMENSIONS.width / 2 &&
            position.x <= node.position.x + NODE_DIMENSIONS.width / 2 &&
            position.y >= node.position.y - NODE_DIMENSIONS.height / 2 &&
            position.y <= node.position.y + NODE_DIMENSIONS.height / 2
          );
        });

        event.dataTransfer.dropEffect = targetNode ? "copy" : "none";
      } else {
        event.dataTransfer.dropEffect = "move";
      }
    },
    [nodes, isDraggingCondition]
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      setIsDraggingCondition(false);

      const reactFlowBounds = event.currentTarget.getBoundingClientRect();
      const blockData = event.dataTransfer.getData("application/reactflow");

      if (!blockData) return;

      const block = JSON.parse(blockData);
      const position = {
        x: event.clientX - reactFlowBounds.left - 75,
        y: event.clientY - reactFlowBounds.top - 25,
      };

      const isConditionNode = block.workspaceData?.category === "conditions";

      if (isConditionNode) {
        const targetNode = nodes.find((node) => {
          return (
            position.x >= node.position.x - NODE_DIMENSIONS.width / 2 &&
            position.x <= node.position.x + NODE_DIMENSIONS.width / 2 &&
            position.y >= node.position.y - NODE_DIMENSIONS.height / 2 &&
            position.y <= node.position.y + NODE_DIMENSIONS.height / 2
          );
        });

        if (targetNode) {
          attachConditionToNode(targetNode.id, block);
        } else {
          toast({
            title: "❌ Invalid Drop Location",
            description: "Condition nodes can only be dropped on existing nodes.",
            variant: "destructive",
          });
        }
        return;
      }

      // Regular node creation
      const nodeUid = `${block.workspaceData?.name || block.label}-${
        block.workspaceData?.rid || block.id
      }-${nodeId}`;
      const newNode = createNodeFromBlock(block, nodeUid, position);

      const updatedNodes = [...nodes, newNode];
      setNodes(updatedNodes);
      setNodeId(nodeId + 1);

      setYamlFlow((prevFlow) =>
        addNodeToYamlFlow(
          prevFlow,
          block.workspaceData?.rid || block.id,
          block.workspaceData?.name || block.label,
          block.workspaceData?.config,
          nodeUid
        )
      );
    },
    [nodeId, setNodes, nodes, edges, createNodeFromBlock, attachConditionToNode, toast]
  );

  const onDragStart = useCallback(
    (event: React.DragEvent, block: BuildingBlock) => {
      const blockData = {
        id: block.id,
        type: block.type,
        label: block.label,
        description: block.description,
        color: block.color,
        workspaceData: block.workspaceData,
      };
      event.dataTransfer.setData("application/reactflow", JSON.stringify(blockData));

      const isCondition = block.workspaceData?.category === "conditions";
      setIsDraggingCondition(isCondition);
      event.dataTransfer.effectAllowed = isCondition ? "copy" : "move";

      // Create drag preview
      const dragPreview = document.createElement("div");
      dragPreview.style.cssText = `
        position: absolute; top: -1000px; left: -1000px;
        padding: 8px 12px; background: ${block.color || "#6B7280"};
        color: white; border-radius: 6px; font-size: 14px; font-weight: 500;
        white-space: nowrap; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        pointer-events: none; z-index: 1000;
      `;
      dragPreview.textContent = block.label;
      document.body.appendChild(dragPreview);
      event.dataTransfer.setDragImage(dragPreview, 50, 20);
      setTimeout(() => {
        if (document.body.contains(dragPreview)) {
          document.body.removeChild(dragPreview);
        }
      }, 0);
    },
    []
  );

  const onDragEnd = useCallback(() => {
    setIsDraggingCondition(false);
  }, []);

  // ─────────────────────────────────────────────────────────────────────────────
  // CHANGE HANDLERS
  // ─────────────────────────────────────────────────────────────────────────────

  const handleNodesChange = useCallback(
    (changes: any[]) => {
      onNodesChange(changes);
      const selected = nodes.filter((node) => node.selected).map((node) => node.id);
      setSelectedNodes(selected);
    },
    [onNodesChange, nodes]
  );

  const handleEdgesChange = useCallback(
    (changes: any[]) => {
      onEdgesChange(changes);
      const selected = edges.filter((edge) => edge.selected).map((edge) => edge.id);
      setSelectedEdges(selected);
    },
    [onEdgesChange, edges]
  );

  // ─────────────────────────────────────────────────────────────────────────────
  // GRAPH ACTIONS
  // ─────────────────────────────────────────────────────────────────────────────

  const clearGraph = useCallback(() => {
    initializeDefaultNodes();
    setEdges([]);
    setYamlFlow(DEFAULT_YAML_FLOW_STATE);
    setIsGraphValid(false);
    setValidationResult(null);
    setFixSuggestions([]);
  }, [initializeDefaultNodes, setEdges]);

  const openSaveModal = useCallback(() => {
    if (!isGraphValid) {
      toast({
        title: "❌ Cannot Save Invalid Graph",
        description: "Please fix all validation issues before saving the graph.",
        variant: "destructive",
      });
      return;
    }
    setSaveModalOpen(true);
  }, [isGraphValid, toast]);

  const saveGraph = useCallback(
    async (name: string, description: string) => {
      try {
        setIsSaving(true);

        const updatedYamlFlow = { ...yamlFlow, name, description };
        setYamlFlow(updatedYamlFlow);

        const yamlString = yaml.dump(updatedYamlFlow, {
          indent: 2,
          lineWidth: -1,
          noRefs: true,
          sortKeys: false,
        });

        let response;
        if (isEditMode && currentBlueprintId) {
          response = await updateBlueprint(currentBlueprintId, yamlString);
        } else {
          response = await saveBlueprint(yamlString, USER_ID);
        }

        if (response.status === "success") {
          toast({
            title: isEditMode
              ? "✅ Blueprint Updated Successfully"
              : "✅ Blueprint Saved Successfully",
            description: `Blueprint "${name}" ${isEditMode ? "updated" : "saved"} successfully`,
          });

          setSaveModalOpen(false);
          setIsSaving(false);

          setTimeout(() => {
            window.location.href = "/agentic-ai";
          }, 100);
        } else {
          throw new Error(response.error || "Unknown error occurred");
        }
      } catch (error) {
        console.error("Error saving graph:", error);
        toast({
          title: isEditMode ? "❌ Error Updating Workflow" : "❌ Error Saving Workflow",
          description: `Failed to ${isEditMode ? "update" : "save"} workflow to the server`,
          variant: "destructive",
        });
        setIsSaving(false);
      }
    },
    [yamlFlow, toast, isEditMode, currentBlueprintId, USER_ID]
  );

  // ─────────────────────────────────────────────────────────────────────────────
  // CONDITIONAL EDGE HANDLING
  // ─────────────────────────────────────────────────────────────────────────────

  const createConditionalEdge = useCallback(
    (params: Connection, branchConfig: any) => {
      const edgeId = `${params.source}-${params.target}-${branchConfig.branch || Date.now()}`;
      const newEdge = {
        id: edgeId,
        source: params.source!,
        target: params.target!,
        type: "custom",
        style: { strokeDasharray: "5,5", stroke: "#10b981" },
        markerEnd: { type: MarkerType.ArrowClosed, color: "#10b981" },
        data: { ...branchConfig, isConditional: true },
        label: branchConfig.branch || "",
      };

      setEdges((prevEdges) => [...prevEdges, newEdge]);

      const sourceNode = nodes.find((node) => node.id === params.source);
      const condition = sourceNode?.data?.referencedConditions?.[0];
      const conditionRid = condition?.workspaceData?.rid || condition?.id;

      setYamlFlow((prevFlow: any) =>
        addConditionalBranchToYamlFlow(
          prevFlow,
          params.source!,
          params.target!,
          conditionRid,
          condition
            ? {
                name: condition.workspaceData?.name || condition.label,
                type: condition.workspaceData?.type,
                config: condition.workspaceData?.config,
              }
            : null,
          branchConfig
        )
      );
    },
    [nodes, setEdges]
  );

  const handleConditionalEdgeConfirm = useCallback(
    (branchConfig: any) => {
      const params: Connection = {
        source: conditionalEdgeModal.sourceNodeId,
        target: conditionalEdgeModal.targetNodeId,
        sourceHandle: null,
        targetHandle: null,
      };

      createConditionalEdge(params, {
        ...branchConfig,
        conditionType: conditionalEdgeModal.conditionType,
      });

      setConditionalEdgeModal({
        isOpen: false,
        sourceNodeId: "",
        targetNodeId: "",
        conditionType: "",
        existingBranches: [],
      });
    },
    [conditionalEdgeModal, createConditionalEdge]
  );

  const handleConditionalEdgeCancel = useCallback(() => {
    setConditionalEdgeModal({
      isOpen: false,
      sourceNodeId: "",
      targetNodeId: "",
      conditionType: "",
      existingBranches: [],
    });
  }, []);

  // ─────────────────────────────────────────────────────────────────────────────
  // KEYBOARD SHORTCUTS
  // ─────────────────────────────────────────────────────────────────────────────

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Delete") {
        event.preventDefault();
        if (selectedNodes.length > 0) {
          selectedNodes.forEach((id) => deleteNode(id));
        }
        if (selectedEdges.length > 0) {
          selectedEdges.forEach((id) => deleteEdge(id));
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedNodes, selectedEdges, deleteNode, deleteEdge]);

  // ─────────────────────────────────────────────────────────────────────────────
  // RETURN
  // ─────────────────────────────────────────────────────────────────────────────

  return {
    // State
    nodes,
    edges,
    buildingBlocksData,
    conditionsData,
    allBlocksData,
    isLoadingBlocks,
    yamlFlow,

    // Handlers
    handleNodesChange,
    handleEdgesChange,
    onConnect,
    onDrop,
    onDragOver,
    onDragStart,
    onDragEnd,
    clearGraph,
    openSaveModal,
    saveGraph,
    deleteEdge,
    attachConditionToNode,
    removeConditionFromNode,

    // Conditional edge modal
    conditionalEdgeModal,
    handleConditionalEdgeConfirm,
    handleConditionalEdgeCancel,

    // Drag state
    isDraggingCondition,

    // Validation state
    isGraphValid,
    validationResult,
    fixSuggestions,
    isValidating,
    validateGraph,

    // Save modal state
    saveModalOpen,
    setSaveModalOpen,
    isSaving,

    // Edit mode state
    isEditMode,
    currentBlueprintId,
    isLoadingBlueprint,
    blueprintName,
    blueprintDescription,
  };
};
