import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import { useToast } from "@/hooks/use-toast";
import {
  CurrentGraph,
  BuildingBlock,
  CanvasNode,
  CanvasEdge,
  YamlFlowState,
} from "@/types/graph";
import { getCategoryDisplay } from "@/components/shared/helpers";
import { useAuth } from "@/contexts/AuthContext";
import { useView } from "@/contexts/ViewContext";
import { useTheme } from "@/contexts/ThemeContext";
import { useWorkspaceIdentity } from "@/hooks/use-workspace-identity";
import { deriveThemeColors } from "@/lib/colorUtils";
import axios from "../http/axiosAgentConfig";
import * as yaml from "js-yaml";
import { saveBlueprint, updateBlueprint } from "@/api/blueprints";
import {
  acquireTeamEditLock,
  heartbeatTeamEditLock,
  releaseTeamEditLock,
} from "@/api/collaborationEditLock";
import { loadBlueprintForEditing } from "@/hooks/use-load-blueprint";

const defaultYamlState: YamlFlowState = {
  nodes: [
    {
      rid: "user_question",
      name: "User Question Node",
      type: "user_question_node",
      config: {
        type: "user_question_node",
      },
    },
    {
      rid: "final_answer",
      name: "Final Answer Node",
      type: "final_answer_node",
      config: {
        type: "final_answer_node",
      },
    },
  ],
  plan: [
    {
      uid: "user_input",
      node: "user_question",
    },
    {
      uid: "finalize",
      node: "final_answer",
    },
  ],
};

export interface SavedBlueprintInfo {
  blueprintId: string;
  name: string;
  description: string;
}

interface UseGraphCreationLogicOptions {
  /** Callback to execute after a successful save (e.g., navigate back to workflow list) */
  onSaveComplete?: (savedBlueprint?: SavedBlueprintInfo) => void;
  /** When provided, load this blueprint for editing instead of starting with an empty canvas */
  editBlueprintId?: string | null;
  /** Team workspace: invoked when another user holds the blueprint edit lock */
  onEditLockDenied?: () => void;
}

export const useGraphCreationLogic = (options: UseGraphCreationLogicOptions = {}) => {
  const { onSaveComplete, editBlueprintId, onEditLockDenied } = options;
  const { toast } = useToast();
  const { primaryHex } = useTheme();
  const themeColors = useMemo(() => deriveThemeColors(primaryHex), [primaryHex]);
  const [nodes, setNodes] = useState<CanvasNode[]>([]);
  const [edges, setEdges] = useState<CanvasEdge[]>([]);
  const [nodeId, setNodeId] = useState(1);
  const [selectedNodes, setSelectedNodes] = useState<string[]>([]);
  const [selectedEdges, setSelectedEdges] = useState<string[]>([]);
  const [buildingBlocksData, setBuildingBlocksData] = useState<BuildingBlock[]>(
    [],
  );
  const [orchestratorsData, setOrchestratorsData] = useState<BuildingBlock[]>(
    [],
  );
  const [allBlocksData, setAllBlocksData] = useState<BuildingBlock[]>([]);
  const [conditionsData, setConditionsData] = useState<BuildingBlock[]>([]);
  const [isLoadingBlocks, setIsLoadingBlocks] = useState(true);

  // Click-to-connect state
  const [pendingConnectionSource, setPendingConnectionSource] = useState<string | null>(null);

  const [currentGraph, setCurrentGraph] = useState<CurrentGraph>({
    id: `graph-${Date.now()}`,
    name: "Untitled Graph",
    nodes: [],
    edges: [],
    metadata: {
      created: new Date(),
      lastModified: new Date(),
      nodeCount: 0,
      edgeCount: 0,
    },
  });

  // YAML flow state management
  const [yamlFlow, setYamlFlow] = useState<YamlFlowState>(defaultYamlState);

  // Graph validation state
  const [isGraphValid, setIsGraphValid] = useState(false);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [fixSuggestions, setFixSuggestions] = useState<any[]>([]);
  const [isValidating, setIsValidating] = useState(false);

  // Save modal state
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Drag state to track what type of item is being dragged
  const [isDraggingCondition, setIsDraggingCondition] = useState(false);

  // Edit mode state
  const [isEditMode, setIsEditMode] = useState(!!editBlueprintId);
  const [isLoadingBlueprint, setIsLoadingBlueprint] = useState(!!editBlueprintId);
  const [editBlueprintName, setEditBlueprintName] = useState("");
  const [editBlueprintDescription, setEditBlueprintDescription] = useState("");
  const blueprintLoadedRef = useRef(false);
  const blueprintEditLockActiveRef = useRef(false);
  const [blueprintEditLockHeld, setBlueprintEditLockHeld] = useState(false);

  const { user } = useAuth();
  const { selectedTeam } = useView();
  const { isTeam, userId: USER_ID, displayName: USER_DISPLAY_NAME, identityType } = useWorkspaceIdentity();

  // Stable refs for callbacks embedded in node data (avoids stale closures)
  const deleteNodeRef = useRef<(id: string) => void>(() => {});
  const attachConditionRef = useRef<(nodeId: string, condition: BuildingBlock) => void>(() => {});
  const removeConditionRef = useRef<(nodeId: string, conditionRid: string) => void>(() => {});
  const allBlocksRef = useRef<BuildingBlock[]>([]);

  // Stable callback wrappers that delegate to the latest ref
  const stableDeleteNode = useCallback((id: string) => deleteNodeRef.current(id), []);
  const stableAttachCondition = useCallback((nodeId: string, condition: BuildingBlock) => attachConditionRef.current(nodeId, condition), []);
  const stableRemoveCondition = useCallback((nodeId: string, rid: string) => removeConditionRef.current(nodeId, rid), []);

  // Validate graph using the validation API
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

      const response = await axios.post(
        "/graph/validation/all.validate",
        yamlString,
        {
          headers: {
            "Content-Type": "text/plain",
          },
        },
      );

      const { validation_result, fix_suggestions } = response.data;

      setValidationResult(validation_result);
      setFixSuggestions(fix_suggestions || []);
      setIsGraphValid(validation_result?.is_valid || false);
    } catch (error) {
      console.error("Validation failed:", error);
      setIsGraphValid(false);
      setValidationResult(null);
      setFixSuggestions([]);
    } finally {
      setIsValidating(false);
    }
  }, [yamlFlow, nodes.length]);

  const transformResourceToBlock = (resource: any): BuildingBlock => {
    const display = getCategoryDisplay(resource.category);

    return {
      id: resource.rid,
      type: resource.type,
      label: resource.name,
      color: display.color,
      description: `${resource.category}/${resource.type} - ${resource.name}`,
      workspaceData: {
        rid: resource.rid,
        name: resource.name,
        category: resource.category,
        type: resource.type,
        config: resource.cfg_dict,
        version: resource.version,
        created: resource.created,
        updated: resource.updated,
        nested_refs: resource.nested_refs,
      },
    };
  };

  const deleteNode = useCallback(
    (nodeId: string) => {
      if (nodeId === "user_input" || nodeId === "finalize") {
        toast({
          title: "❌ Cannot Delete Required Node",
          description:
            "User Input and Final Answer nodes are required and cannot be deleted",
          variant: "destructive",
        });
        return;
      }

      setNodes((prev) => prev.filter((node) => node.id !== nodeId));

      setEdges((prev) =>
        prev.filter((edge) => edge.source !== nodeId && edge.target !== nodeId),
      );

      setPendingConnectionSource(null);

      setYamlFlow((prevFlow) => {
        const updatedPlan = prevFlow.plan
          .filter((step) => step.uid !== nodeId)
          .map((step) => {
            let updated = step;

            if (updated.after) {
              if (Array.isArray(updated.after)) {
                const filtered = updated.after.filter((a) => a !== nodeId);
                if (filtered.length === 0) {
                  const { after, ...rest } = updated;
                  updated = rest as typeof step;
                } else if (filtered.length === 1) {
                  updated = { ...updated, after: filtered[0] };
                } else {
                  updated = { ...updated, after: filtered };
                }
              } else if (updated.after === nodeId) {
                const { after, ...rest } = updated;
                updated = rest as typeof step;
              }
            }

            if (updated.branches) {
              const cleanedBranches = { ...updated.branches };
              for (const key of Object.keys(cleanedBranches)) {
                if (cleanedBranches[key] === nodeId) {
                  delete cleanedBranches[key];
                }
              }
              if (Object.keys(cleanedBranches).length === 0) {
                const { branches, exit_condition, ...rest } = updated;
                updated = rest as typeof step;
              } else {
                updated = { ...updated, branches: cleanedBranches };
              }
            }

            return updated;
          });

        const referencedRids = new Set(updatedPlan.map((step) => step.node));
        const updatedNodes = prevFlow.nodes.filter((node) => {
          const bareRid = node.rid.startsWith("$ref:")
            ? node.rid.slice(5)
            : node.rid;
          return referencedRids.has(bareRid) || referencedRids.has(node.rid);
        });

        const referencedConditions = new Set(
          updatedPlan.map((step) => step.exit_condition).filter(Boolean),
        );
        const updatedConditions = (prevFlow.conditions || []).filter((cond) => {
          const bareRid = cond.rid.startsWith("$ref:")
            ? cond.rid.slice(5)
            : cond.rid;
          return (
            referencedConditions.has(bareRid) ||
            referencedConditions.has(cond.rid)
          );
        });

        return {
          ...prevFlow,
          nodes: updatedNodes,
          conditions: updatedConditions,
          plan: updatedPlan,
        };
      });

      setCurrentGraph((prev) => ({
        ...prev,
        metadata: { ...prev.metadata, lastModified: new Date() },
      }));
    },
    [toast],
  );
  deleteNodeRef.current = deleteNode;

  const deleteEdge = useCallback(
    (edgeId: string) => {
      // Capture the edge to delete from current state via a ref-like approach:
      // we read it inside the setEdges updater so it's always fresh.
      let removedEdge: CanvasEdge | undefined;

      setEdges((currentEdges) => {
        removedEdge = currentEdges.find((edge) => edge.id === edgeId);
        if (!removedEdge) return currentEdges;
        return currentEdges.filter((edge) => edge.id !== edgeId);
      });

      // Schedule the YAML update separately; React batches these together.
      setYamlFlow((prevFlow) => {
        if (!removedEdge) return prevFlow;

        const updatedPlan = prevFlow.plan.map((step) => {
          if (step.uid === removedEdge!.target && step.after) {
            if (Array.isArray(step.after)) {
              const updatedAfter = step.after.filter(
                (afterId) => afterId !== removedEdge!.source,
              );
              if (updatedAfter.length === 0) {
                const { after, ...rest } = step;
                return rest;
              } else if (updatedAfter.length === 1) {
                return { ...step, after: updatedAfter[0] };
              }
              return { ...step, after: updatedAfter };
            } else if (step.after === removedEdge!.source) {
              const { after, ...rest } = step;
              return rest;
            }
          }

          if (step.uid === removedEdge!.source && step.branches) {
            const updatedBranches = { ...step.branches };
            Object.keys(updatedBranches).forEach((branchKey) => {
              if (updatedBranches[branchKey] === removedEdge!.target) {
                delete updatedBranches[branchKey];
              }
            });

            if (Object.keys(updatedBranches).length === 0) {
              const { branches, exit_condition, ...rest } = step;
              return rest;
            }
            return { ...step, branches: updatedBranches };
          }

          return step;
        });

        return {
          ...prevFlow,
          conditions: prevFlow.conditions || [],
          plan: updatedPlan,
        };
      });

      setCurrentGraph((prev) => ({
        ...prev,
        metadata: { ...prev.metadata, lastModified: new Date() },
      }));
    },
    [],
  );

  const attachConditionToNode = (nodeId: string, condition: BuildingBlock) => {
    // Check if node already has a condition attached
    const targetNode = nodes.find((node) => node.id === nodeId);
    if (
      targetNode?.data?.referencedConditions &&
      targetNode.data.referencedConditions.length > 0
    ) {
      toast({
        title: "❌ Condition Limit Reached",
        description:
          "Each node can only have one condition attached. Remove the existing condition first.",
        variant: "destructive",
      });
      return;
    }

    setNodes((prevNodes) =>
      prevNodes.map((node) =>
        node.id === nodeId
          ? {
              ...node,
              data: {
                ...node.data,
                referencedConditions: [condition], // Only allow one condition
              },
            }
          : node,
      ),
    );

    // Update YAML flow to immediately set exit_condition and add condition definition
    setYamlFlow((prevFlow) => {
      const conditionRid = condition.workspaceData?.rid || condition.id;
      
      // Update plan with exit_condition
      const updatedPlan = prevFlow.plan.map((step) => {
        if (step.uid === nodeId) {
          return {
            ...step,
            exit_condition: conditionRid,
          };
        }
        return step;
      });

      // Add condition definition to conditions section if not exists
      const conditionExists = (prevFlow.conditions || []).some(
        (cond) => cond.rid === `$ref:${conditionRid}`,
      );

      let updatedConditions = prevFlow.conditions || [];
      if (!conditionExists) {
        updatedConditions = [
          ...updatedConditions,
          {
            rid: `$ref:${conditionRid}`,
            name: condition.workspaceData?.name || condition.label,
            type: condition.workspaceData?.type,
            config: condition.workspaceData?.config,
          },
        ];
      }

      return {
        ...prevFlow,
        conditions: updatedConditions,
        plan: updatedPlan,
      };
    });
  };

  attachConditionRef.current = attachConditionToNode;

  const removeConditionFromNode = (nodeId: string, conditionRid: string) => {
    setNodes((prevNodes) =>
      prevNodes.map((node) =>
        node.id === nodeId
          ? {
              ...node,
              data: {
                ...node.data,
                referencedConditions: (
                  node.data.referencedConditions || []
                ).filter(
                  (condition: BuildingBlock) =>
                    (condition.workspaceData?.rid || condition.id) !==
                    conditionRid,
                ),
              },
            }
          : node,
      ),
    );

    // Remove related edges
    setEdges((prevEdges) => prevEdges.filter((edge) => edge.source !== nodeId));

    // Update YAML flow to remove the condition and related connections
    setYamlFlow((prevFlow) => {
      // Remove condition from plan
      const updatedPlan = prevFlow.plan.map((step) => {
        if (step.uid === nodeId && step.exit_condition === conditionRid) {
          const { exit_condition, branches, ...stepWithoutCondition } = step;
          return stepWithoutCondition;
        }
        return step;
      });

      // Remove condition definition from conditions section (if exists)
      const updatedConditions = (prevFlow.conditions || []).filter(
        (cond) => cond.rid !== `$ref:${conditionRid}`,
      );

      return {
        ...prevFlow,
        conditions: updatedConditions.length > 0 ? updatedConditions : [],
        plan: updatedPlan,
      };
    });
  };

  removeConditionRef.current = removeConditionFromNode;

  // Keep allBlocksRef in sync
  allBlocksRef.current = allBlocksData;

  // Initialize canvas with default required nodes
  const initializeDefaultNodes = useCallback(() => {
    const userInputNode: CanvasNode = {
      id: "user_input",
      position: { x: 200, y: 100 },
      data: {
        label: "User Input",
        icon: getCategoryDisplay("nodes").icon,
        color: "#4A90E2",
        style: "bg-blue-800 text-white border",
        description: "User question input node",
        workspaceData: {
          rid: "user_question",
          name: "user_question",
          category: "nodes",
          type: "user_question_node",
          config: {
            name: "User Input",
            type: "user_question_node",
          },
          version: 1,
          created: new Date().toISOString(),
          updated: new Date().toISOString(),
          nested_refs: [],
        },
        onDelete: stableDeleteNode,
        allBlocks: allBlocksRef.current,
        referencedConditions: [],
        onAttachCondition: stableAttachCondition,
        onRemoveCondition: stableRemoveCondition,
      },
    };

    const finalizeNode: CanvasNode = {
      id: "finalize",
      position: { x: 200, y: 900 },
      data: {
        label: "Final Answer",
        icon: getCategoryDisplay("nodes").icon,
        color: "#50C878",
        style: "bg-green-800 text-white border",
        description: "Final answer output node",
        workspaceData: {
          rid: "final_answer",
          name: "final_answer",
          category: "nodes",
          type: "final_answer_node",
          config: {
            name: "Final Answer",
            type: "final_answer_node",
          },
          version: 1,
          created: new Date().toISOString(),
          updated: new Date().toISOString(),
          nested_refs: [],
        },
        onDelete: stableDeleteNode,
        allBlocks: allBlocksRef.current,
        referencedConditions: [],
        onAttachCondition: stableAttachCondition,
        onRemoveCondition: stableRemoveCondition,
      },
    };

    setNodes([userInputNode, finalizeNode]);
    // Start from 3 since we have 2 default nodes
    setNodeId(3);
  }, [stableDeleteNode, stableAttachCondition, stableRemoveCondition]);

  const loadBuildingBlocks = useCallback(async () => {
    if (!isTeam && !user?.username) {
      setIsLoadingBlocks(false);
      return;
    }
    if (!USER_ID) {
      setIsLoadingBlocks(false);
      return;
    }
    try {
      setIsLoadingBlocks(true);
      const response = await axios.get(
        `/resources/resources.list?userId=${USER_ID}&identityType=${identityType}`,
      );
      const allBlocks = response.data.resources.map(transformResourceToBlock);

      setAllBlocksData(allBlocks);

      const orchestratorBlocks = allBlocks.filter(
        (block: BuildingBlock) =>
          block.workspaceData?.category === "nodes" &&
          block.workspaceData?.type === "orchestrator_node",
      );
      setOrchestratorsData(orchestratorBlocks);

      const nodeBlocks = allBlocks.filter(
        (block: BuildingBlock) =>
          block.workspaceData?.category === "nodes" &&
          block.workspaceData?.type !== "orchestrator_node",
      );
      setBuildingBlocksData(nodeBlocks);

      const conditionBlocks = allBlocks.filter(
        (block: BuildingBlock) =>
          block.workspaceData?.category === "conditions",
      );
      setConditionsData(conditionBlocks);
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
  }, [toast, USER_ID, identityType, isTeam, user?.username]);

  useEffect(() => {
    loadBuildingBlocks();
  }, [loadBuildingBlocks]);

  useEffect(() => {
    if (!editBlueprintId) {
      initializeDefaultNodes();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load existing blueprint for editing once building blocks are ready (team: acquire edit lock first)
  useEffect(() => {
    if (!editBlueprintId || isLoadingBlocks || blueprintLoadedRef.current) return;

    let cancelled = false;

    const releaseLockIfHeld = async () => {
      if (
        !blueprintEditLockActiveRef.current ||
        !isTeam ||
        !selectedTeam ||
        !user?.username ||
        !editBlueprintId
      ) {
        return;
      }
      blueprintEditLockActiveRef.current = false;
      setBlueprintEditLockHeld(false);
      await releaseTeamEditLock({
        teamId: selectedTeam.id,
        entityKind: "blueprint",
        entityId: editBlueprintId,
        userId: user.username,
      });
    };

    const run = async () => {
      if (isTeam && selectedTeam && user?.username) {
        try {
          const lockResult = await acquireTeamEditLock({
            teamId: selectedTeam.id,
            entityKind: "blueprint",
            entityId: editBlueprintId,
            userId: user.username,
            displayName: user.name?.trim() || user.username,
          });
          if (cancelled) {
            if (lockResult.acquired) {
              await releaseTeamEditLock({
                teamId: selectedTeam.id,
                entityKind: "blueprint",
                entityId: editBlueprintId,
                userId: user.username,
              });
            }
            return;
          }
          if (!lockResult.acquired) {
            toast({
              title: "Someone else is editing this workflow",
              description: `Currently being edited by ${lockResult.lockedBy.displayName || lockResult.lockedBy.userId}.`,
              variant: "destructive",
            });
            blueprintEditLockActiveRef.current = false;
            setBlueprintEditLockHeld(false);
            setIsLoadingBlueprint(false);
            onEditLockDenied?.();
            return;
          }
          blueprintEditLockActiveRef.current = true;
          setBlueprintEditLockHeld(true);
        } catch {
          if (cancelled) return;
          toast({
            title: "Could not open workflow editor",
            description: "Failed to acquire edit lock. Try again shortly.",
            variant: "destructive",
          });
          blueprintEditLockActiveRef.current = false;
          setBlueprintEditLockHeld(false);
          setIsLoadingBlueprint(false);
          onEditLockDenied?.();
          return;
        }
      }

      blueprintLoadedRef.current = true;

      try {
        const result = await loadBlueprintForEditing(
          editBlueprintId,
          allBlocksData,
          conditionsData,
        );
        if (cancelled) return;

        const nodesWithCallbacks = result.nodes.map((node) => ({
          ...node,
          data: {
            ...node.data,
            onDelete: stableDeleteNode,
            allBlocks: allBlocksData,
            onAttachCondition: stableAttachCondition,
            onRemoveCondition: stableRemoveCondition,
          },
        }));
        setNodes(nodesWithCallbacks);
        setEdges(result.edges);
        setYamlFlow(result.yamlFlow);
        setNodeId(result.nextNodeId);
        setIsEditMode(true);
        setEditBlueprintName(result.name);
        setEditBlueprintDescription(result.description);
        setIsLoadingBlueprint(false);
      } catch (err) {
        console.error("Failed to load blueprint for editing:", err);
        await releaseLockIfHeld();
        if (cancelled) return;
        setIsEditMode(false);
        setEditBlueprintName("");
        setEditBlueprintDescription("");
        setIsLoadingBlueprint(false);
        toast({
          title: "Failed to load blueprint",
          description:
            "Could not load the blueprint for editing. Starting with a blank canvas.",
          variant: "destructive",
        });
        initializeDefaultNodes();
      }
    };

    void run();

    return () => {
      cancelled = true;
      void releaseLockIfHeld();
    };
    // Intentionally keyed like the original hook: blocks/callbacks are read when
    // isLoadingBlocks becomes false, not on every blocks refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editBlueprintId, isLoadingBlocks]);

  useEffect(() => {
    if (
      !blueprintEditLockHeld ||
      !isTeam ||
      !selectedTeam ||
      !editBlueprintId ||
      !user?.username
    ) {
      return;
    }
    const teamId = selectedTeam.id;
    const bpId = editBlueprintId;
    const displayName = user.name?.trim() || user.username;
    let interval: ReturnType<typeof setInterval> | undefined;
    interval = window.setInterval(() => {
      void heartbeatTeamEditLock({
        teamId,
        entityKind: "blueprint",
        entityId: bpId,
        userId: user.username,
        displayName,
      }).catch((err: unknown) => {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 501) return;
        if (interval != null) window.clearInterval(interval);
        interval = undefined;
        setBlueprintEditLockHeld(false);
        blueprintEditLockActiveRef.current = false;
        toast({
          title: "Edit lock lost",
          description: "We could not renew the team edit lock. Editing is disabled.",
          variant: "destructive",
        });
      });
    }, 45_000);
    return () => {
      if (interval != null) window.clearInterval(interval);
    };
  }, [
    blueprintEditLockHeld,
    isTeam,
    selectedTeam?.id,
    editBlueprintId,
    user?.username,
    user?.name,
    toast,
  ]);

  // Sync allBlocks data to existing nodes when blocks change
  useEffect(() => {
    setNodes((prevNodes) =>
      prevNodes.map((node) => ({
        ...node,
        data: {
          ...node.data,
          allBlocks: allBlocksData,
        },
      })),
    );
  }, [allBlocksData, setNodes]);

  // Trigger validation whenever yamlFlow changes.
  useEffect(() => {
    if (yamlFlow.plan && yamlFlow.plan.length > 2) {
      const validationTimeout = setTimeout(() => {
        validateGraph();
      }, 100);

      return () => {
        clearTimeout(validationTimeout);
      };
    }

    // Plan dropped to ≤2 steps (only default nodes remain) — clear stale results
    setIsGraphValid(false);
    setValidationResult(null);
    setFixSuggestions([]);
    setIsValidating(false);
  }, [yamlFlow, validateGraph]);

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    
    if (isDraggingCondition) {
      const canvasBoundsRect = event.currentTarget.getBoundingClientRect();
      const position = {
        x: event.clientX - canvasBoundsRect.left - 75,
        y: event.clientY - canvasBoundsRect.top - 25,
      };

      const targetNode = nodes.find((node) => {
        const nodeWidth = node.width ?? 150;
        const nodeHeight = node.height ?? 80;
        
        return (
          position.x >= node.position.x - nodeWidth / 2 &&
          position.x <= node.position.x + nodeWidth / 2 &&
          position.y >= node.position.y - nodeHeight / 2 &&
          position.y <= node.position.y + nodeHeight / 2
        );
      });

      // Set different drop effects based on whether over a valid target
      event.dataTransfer.dropEffect = targetNode ? "copy" : "none";
    } else {
      // Regular nodes can be dropped anywhere
      event.dataTransfer.dropEffect = "move";
    }
  }, [nodes, isDraggingCondition]);

  const onDrop = useCallback(
    (event: React.DragEvent, localPosition?: { x: number; y: number }) => {
      event.preventDefault();

      setIsDraggingCondition(false);

      const blockData = event.dataTransfer.getData("application/unifai-block");

      if (blockData) {
        let block: any;
        try {
          block = JSON.parse(blockData);
        } catch {
          return;
        }
        const position = localPosition ?? (() => {
          const canvasBounds = event.currentTarget.getBoundingClientRect();
          return {
            x: event.clientX - canvasBounds.left - 75,
            y: event.clientY - canvasBounds.top - 25,
          };
        })();

        // Check if this is a condition node
        const isConditionNode = block.workspaceData?.category === "conditions";

        if (isConditionNode) {
          // For condition nodes, check if dropping on an existing node
          const targetNode = nodes.find((node) => {
            const nodeWidth = node.width ?? 150;
            const nodeHeight = node.height ?? 80;
            
            return (
              position.x >= node.position.x - nodeWidth / 2 &&
              position.x <= node.position.x + nodeWidth / 2 &&
              position.y >= node.position.y - nodeHeight / 2 &&
              position.y <= node.position.y + nodeHeight / 2
            );
          });

          if (targetNode) {
            // Attach condition to the target node
            attachConditionToNode(targetNode.id, block);
          } else {
            // Show error message if not dropped on a node
            toast({
              title: "❌ Invalid Drop Location",
              description: "Condition nodes can only be dropped on existing nodes. Please drag the condition onto a node.",
              variant: "destructive",
            });
          }
          return; // Exit early for condition nodes
        }

        const nodeUid = `${block.workspaceData?.name || block.label}-${block.workspaceData?.rid || block.id}-${nodeId}`;
        const newNode: CanvasNode = {
          id: nodeUid,
          position,
          data: {
            label: block.label,
            icon: getCategoryDisplay(block.workspaceData?.category || "default")
              .icon,
            color: block.color,
            style: `bg-gray-800 text-white border`,
            description: `${block.description}`,
            workspaceData: block.workspaceData,
            onDelete: stableDeleteNode,
            allBlocks: allBlocksRef.current,
            referencedConditions: [],
            onAttachCondition: stableAttachCondition,
            onRemoveCondition: stableRemoveCondition,
          },
        };

        setNodes((prev) => [...prev, newNode]);
        setNodeId((prev) => prev + 1);

        setYamlFlow((prevFlow) => {
          const nodeRid = `$ref:${block.workspaceData?.rid || block.id}`;

          const nodeExists = prevFlow.nodes.some(
            (node) => node.rid === nodeRid,
          );

          const newYamlNode = {
            rid: nodeRid,
            name: block.workspaceData?.name || block.label,
            config: block.workspaceData?.config || {},
          };

          const newPlanStep = {
            uid: nodeUid,
            node: block.workspaceData?.rid || block.id,
          };

          return {
            ...prevFlow,
            nodes: nodeExists
              ? prevFlow.nodes
              : [...prevFlow.nodes, newYamlNode],
            conditions: prevFlow.conditions || [],
            plan: [...prevFlow.plan, newPlanStep],
          };
        });

        setCurrentGraph((prev) => ({
          ...prev,
          metadata: { ...prev.metadata, lastModified: new Date() },
        }));
      }
    },
    [nodeId, nodes, stableDeleteNode, stableAttachCondition, stableRemoveCondition, toast],
  );

  const selectNode = useCallback(
    (nodeId: string | null) => {
      setNodes((prev) =>
        prev.map((n) => ({ ...n, selected: n.id === nodeId })),
      );
      setSelectedNodes(nodeId ? [nodeId] : []);
    },
    [setNodes],
  );

  const onDragStart = (event: React.DragEvent, block: BuildingBlock) => {
    const blockData = {
      id: block.id,
      type: block.type,
      label: block.label,
      description: block.description,
      color: block.color,
      workspaceData: block.workspaceData,
    };
    event.dataTransfer.setData(
      "application/unifai-block",
      JSON.stringify(blockData),
    );
    
    // Set drag state based on block category
    const isCondition = block.workspaceData?.category === "conditions";
    setIsDraggingCondition(isCondition);
    
    event.dataTransfer.effectAllowed = isCondition ? "copy" : "move";

    const previewColor = themeColors.primary;
    const dragPreview = document.createElement("div");
    dragPreview.style.cssText = `
      position: absolute;
      top: -1000px;
      left: -1000px;
      padding: 8px 12px;
      background: ${previewColor};
      color: white;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 500;
      white-space: nowrap;
      box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
      pointer-events: none;
      z-index: 1000;
    `;
    dragPreview.textContent = block.label;
    document.body.appendChild(dragPreview);

    event.dataTransfer.setDragImage(dragPreview, 50, 20);
    setTimeout(() => {
      if (document.body.contains(dragPreview)) {
        document.body.removeChild(dragPreview);
      }
    }, 0);
  };

  const onDragEnd = useCallback(() => {
    // Reset drag state when drag operation ends (whether successful or cancelled)
    setIsDraggingCondition(false);
  }, []);

  const clearGraph = () => {
    // Reset to default nodes instead of clearing completely
    initializeDefaultNodes();
    setEdges([]);

    // Reset YAML flow to default state
    setYamlFlow(defaultYamlState);

    // Reset validation and connection state
    setPendingConnectionSource(null);
    setIsGraphValid(false);
    setValidationResult(null);
    setFixSuggestions([]);

    setCurrentGraph((prev) => ({
      ...prev,
      nodes: [],
      edges: [],
      metadata: {
        ...prev.metadata,
        lastModified: new Date(),
        nodeCount: 2,
        edgeCount: 0,
      },
    }));
  };

  const openSaveModal = () => {
    if (!isGraphValid) {
      toast({
        title: "❌ Cannot Save Invalid Graph",
        description:
          "Please fix all validation issues before saving the graph.",
        variant: "destructive",
      });
      return;
    }
    setSaveModalOpen(true);
  };

  const saveGraph = useCallback(
    async (name: string, description: string) => {
      try {
        setIsSaving(true);

         // Update yamlFlow with name and description
        const updatedYamlFlow = {
          ...yamlFlow,
          name: name,
          description: description,
        };

        setYamlFlow(updatedYamlFlow);

        // Convert to YAML string using js-yaml library
        const yamlString = yaml.dump(updatedYamlFlow, {
          indent: 2,
          lineWidth: -1,
          noRefs: true,
          sortKeys: false,
        });

        let response;
        let blueprintId;
        
        if (isEditMode && editBlueprintId) {
          response = await updateBlueprint(editBlueprintId, yamlString);
          blueprintId = editBlueprintId;
        } else {
          if (!USER_ID) {
            toast({
              title: "❌ Cannot save workflow",
              description: "Sign in or select a workspace before saving.",
              variant: "destructive",
            });
            setIsSaving(false);
            return;
          }
          response = await saveBlueprint(yamlString, USER_ID, USER_DISPLAY_NAME, identityType);
          blueprintId = response.blueprint_id;
        }

        if (response.status !== "success") {
          throw new Error(
            isEditMode
              ? "Unknown error occurred while updating blueprint"
              : "Unknown error occurred while saving blueprint"
          );
        }

        toast({
          title: isEditMode
            ? "✅ Blueprint Updated Successfully"
            : "✅ Blueprint Saved Successfully",
          description: `Blueprint "${name}" ${isEditMode ? "updated" : "saved"} successfully`,
          variant: "default",
        });

        setSaveModalOpen(false);
        setIsSaving(false);

        if (onSaveComplete) {
          setTimeout(() => {
            onSaveComplete({
              blueprintId,
              name,
              description,
            });
          }, 100);
        }
      } catch (error) {
        console.error("Error saving graph:", error);
        toast({
          title: "❌ Error Saving Workflow",
          description: "Failed to save workflow to the server",
          variant: "destructive",
        });
        setIsSaving(false);
      }
    },
    [yamlFlow, toast, onSaveComplete, USER_ID, identityType, isEditMode, editBlueprintId],
  );

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Delete" || event.key === "Backspace") {
        const target = event.target as HTMLElement;
        if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
          return;
        }
        event.preventDefault();
        if (selectedNodes.length > 0) {
          selectedNodes.forEach((nodeId) => deleteNode(nodeId));
        }
        if (selectedEdges.length > 0) {
          selectedEdges.forEach((edgeId) => deleteEdge(edgeId));
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedNodes, selectedEdges, deleteNode, deleteEdge]);


  // --- Click-to-connect logic ---

  const cancelConnectionMode = useCallback(() => {
    setPendingConnectionSource(null);
    setSelectedNodes([]);
    setNodes((prevNodes) =>
      prevNodes.map((n) => ({
        ...n,
        selected: false,
        data: {
          ...n.data,
          isConnectionSource: false,
          isConnectionTarget: false,
        },
      })),
    );
  }, [setNodes]);

  const createRegularEdge = useCallback(
    (sourceId: string, targetId: string) => {
      const newEdge: CanvasEdge = {
        id: `${sourceId}-${targetId}`,
        source: sourceId,
        target: targetId,
      };

      setEdges((prevEdges) => [...prevEdges, newEdge]);

      setYamlFlow((prevFlow) => {
        const updatedPlan = prevFlow.plan.map((step) => {
          if (step.uid !== targetId) return step;
          const existingAfter = step.after;
          if (!existingAfter) return { ...step, after: sourceId };
          if (Array.isArray(existingAfter)) {
            return existingAfter.includes(sourceId)
              ? step
              : { ...step, after: [...existingAfter, sourceId] };
          }
          return existingAfter === sourceId
            ? step
            : { ...step, after: [existingAfter, sourceId] };
        });
        return { ...prevFlow, conditions: prevFlow.conditions || [], plan: updatedPlan };
      });

      setCurrentGraph((prev) => ({
        ...prev,
        edges: [...prev.edges, newEdge],
        metadata: { ...prev.metadata, lastModified: new Date(), edgeCount: prev.edges.length + 1 },
      }));
    },
    [],
  );

  const createConditionalEdge = useCallback(
    (sourceId: string, targetId: string, condition: BuildingBlock) => {
      const conditionType = condition.workspaceData?.type || condition.type;
      const conditionRid = condition.workspaceData?.rid || condition.id;

      const newEdge: CanvasEdge = {
        id: `${sourceId}-${targetId}`,
        source: sourceId,
        target: targetId,
        data: { isConditional: true },
      };

      setEdges((prevEdges) => [...prevEdges, newEdge]);

      setYamlFlow((prevFlow) => {
        const updatedPlan = prevFlow.plan.map((step) => {
          if (step.uid !== sourceId) return step;
          const existingBranches = step.branches || {};
          const newBranches = { ...existingBranches };

          if (conditionType === "router_direct") {
            newBranches[targetId] = targetId;
          } else if (conditionType === "router_boolean") {
            if (!newBranches["true"]) {
              newBranches["true"] = targetId;
            } else if (!newBranches["false"]) {
              newBranches["false"] = targetId;
            } else {
              let n = 2;
              while (newBranches[`branch_${n}`]) n++;
              newBranches[`branch_${n}`] = targetId;
            }
          } else {
            const usedKeys = new Set(Object.keys(newBranches));
            let branchKey = "true";
            if (usedKeys.has("true")) branchKey = "false";
            if (usedKeys.has("true") && usedKeys.has("false")) {
              let n = 2;
              while (usedKeys.has(`branch_${n}`)) n++;
              branchKey = `branch_${n}`;
            }
            newBranches[branchKey] = targetId;
          }

          return { ...step, exit_condition: conditionRid, branches: newBranches };
        });

        const conditionExists = (prevFlow.conditions || []).some(
          (cond) => cond.rid === `$ref:${conditionRid}`,
        );
        let updatedConditions = prevFlow.conditions || [];
        if (!conditionExists) {
          updatedConditions = [
            ...updatedConditions,
            {
              rid: `$ref:${conditionRid}`,
              name: condition.workspaceData?.name || condition.label,
              type: condition.workspaceData?.type,
              config: condition.workspaceData?.config,
            },
          ];
        }

        return {
          ...prevFlow,
          conditions: updatedConditions.length > 0 ? updatedConditions : [],
          plan: updatedPlan,
        };
      });

      setCurrentGraph((prev) => ({
        ...prev,
        edges: [...prev.edges, newEdge],
        metadata: { ...prev.metadata, lastModified: new Date(), edgeCount: prev.edges.length + 1 },
      }));
    },
    [],
  );

  const handleNodeClickForConnection = useCallback(
    (clickedNodeId: string) => {
      if (pendingConnectionSource === null) {
        setPendingConnectionSource(clickedNodeId);
        setSelectedNodes([clickedNodeId]);
        setNodes((prevNodes) =>
          prevNodes.map((n) => ({
            ...n,
            selected: n.id === clickedNodeId,
            data: {
              ...n.data,
              isConnectionSource: n.id === clickedNodeId,
              isConnectionTarget: n.id !== clickedNodeId,
            },
          })),
        );
        return;
      }

      if (pendingConnectionSource === clickedNodeId) {
        cancelConnectionMode();
        return;
      }

      const hasExisting = edges.some(
        (e) => e.source === pendingConnectionSource && e.target === clickedNodeId,
      );
      if (hasExisting) {
        toast({
          title: "Connection Already Exists",
          description: "This connection already exists.",
          variant: "destructive",
        });
      } else {
        const sourceNode = nodes.find((n) => n.id === pendingConnectionSource);
        const hasCondition =
          sourceNode?.data?.referencedConditions &&
          sourceNode.data.referencedConditions.length > 0;

        if (hasCondition) {
          createConditionalEdge(
            pendingConnectionSource,
            clickedNodeId,
            sourceNode.data.referencedConditions![0],
          );
        } else {
          createRegularEdge(pendingConnectionSource, clickedNodeId);
        }
      }

      cancelConnectionMode();
    },
    [pendingConnectionSource, edges, nodes, setNodes, cancelConnectionMode, toast, createRegularEdge, createConditionalEdge],
  );

  const handlePaneClick = useCallback(() => {
    if (pendingConnectionSource !== null) {
      cancelConnectionMode();
    }
    setSelectedNodes([]);
    setNodes((prev) => prev.map((n) => ({ ...n, selected: false })));
  }, [pendingConnectionSource, cancelConnectionMode, setNodes]);

  // ESC key handler for connection mode
  useEffect(() => {
    const handleEsc = (event: KeyboardEvent) => {
      if (event.key === "Escape" && pendingConnectionSource !== null) {
        cancelConnectionMode();
      }
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [pendingConnectionSource, cancelConnectionMode]);

  const updateNodePosition = useCallback(
    (nodeId: string, position: { x: number; y: number }) => {
      setNodes((prev) =>
        prev.map((n) => (n.id === nodeId ? { ...n, position } : n)),
      );
    },
    [setNodes],
  );

  return {
    nodes,
    edges,
    setNodes,
    setEdges,
    currentGraph,
    buildingBlocksData,
    orchestratorsData,
    conditionsData,
    allBlocksData,
    isLoadingBlocks,
    yamlFlow,
    selectNode,
    onDrop,
    onDragOver,
    onDragStart,
    onDragEnd,
    clearGraph,
    openSaveModal,
    saveGraph,
    deleteNode,
    deleteEdge,
    attachConditionToNode,
    removeConditionFromNode,
    updateNodePosition,
    pendingConnectionSource,
    handleNodeClickForConnection,
    handlePaneClick,
    cancelConnectionMode,
    isDraggingCondition,
    isGraphValid,
    validationResult,
    fixSuggestions,
    isValidating,
    validateGraph,
    saveModalOpen,
    setSaveModalOpen,
    isSaving,
    // Edit mode state
    isEditMode,
    isLoadingBlueprint,
    editBlueprintName,
    editBlueprintDescription,
  };
};
