/**
 * YAML flow state update helpers
 * Pure functions for transforming YamlFlowState
 */

import { YamlFlowState, YamlFlowPlanStep } from './types';

/**
 * Remove a node from the YAML flow state
 * Cleans up plan steps, after references, branches, and orphaned node/condition definitions
 */
export function removeNodeFromYamlFlow(
  prevFlow: YamlFlowState,
  nodeId: string
): YamlFlowState {
  // Remove the plan step for this node and clean up references
  const updatedPlan = prevFlow.plan
    .filter((step) => step.uid !== nodeId)
    .map((step) => cleanupPlanStepReferences(step, nodeId));

  // Get the node rid that was referenced by the deleted plan step
  const deletedStep = prevFlow.plan.find((step) => step.uid === nodeId);
  const deletedNodeRid = deletedStep?.node;

  // Check if any remaining plan step still references this node rid
  const nodeStillInUse = updatedPlan.some((step) => step.node === deletedNodeRid);

  // Only keep node definitions that are still referenced in the plan
  const updatedNodes = nodeStillInUse
    ? prevFlow.nodes
    : prevFlow.nodes.filter((n) => {
        const rid = n.rid?.startsWith('$ref:') ? n.rid.slice(5) : n.rid;
        return rid !== deletedNodeRid;
      });

  // Clean up orphaned conditions - only keep conditions still referenced in plan
  const usedConditions = new Set(
    updatedPlan.filter((s) => s.exit_condition).map((s) => s.exit_condition)
  );
  const updatedConditions = (prevFlow.conditions || []).filter((c) => {
    const rid = c.rid?.startsWith('$ref:') ? c.rid.slice(5) : c.rid;
    return usedConditions.has(rid);
  });

  return {
    nodes: updatedNodes,
    conditions: updatedConditions,
    plan: updatedPlan,
  };
}

/**
 * Clean up references to a deleted node in a plan step
 */
function cleanupPlanStepReferences(step: YamlFlowPlanStep, deletedNodeId: string): YamlFlowPlanStep {
  let result = { ...step };

  // Clean up 'after' references
  if (result.after === deletedNodeId) {
    const { after, ...rest } = result;
    result = rest as YamlFlowPlanStep;
  } else if (Array.isArray(result.after)) {
    const filteredAfter = result.after.filter((a) => a !== deletedNodeId);
    if (filteredAfter.length === 0) {
      const { after, ...rest } = result;
      result = rest as YamlFlowPlanStep;
    } else {
      result = {
        ...result,
        after: filteredAfter.length === 1 ? filteredAfter[0] : filteredAfter,
      };
    }
  }

  // Clean up branches that target the deleted node
  if (result.branches) {
    const updatedBranches = { ...result.branches };
    Object.keys(updatedBranches).forEach((key) => {
      if (updatedBranches[key] === deletedNodeId) {
        delete updatedBranches[key];
      }
    });
    if (Object.keys(updatedBranches).length === 0) {
      const { branches, ...rest } = result;
      result = rest as YamlFlowPlanStep;
    } else {
      result = { ...result, branches: updatedBranches };
    }
  }

  return result;
}

/**
 * Remove an edge from the YAML flow state
 */
export function removeEdgeFromYamlFlow(
  prevFlow: YamlFlowState,
  sourceId: string,
  targetId: string
): YamlFlowState {
  const updatedPlan = prevFlow.plan.map((step) => {
    if (step.uid !== targetId) return step;

    let result = { ...step };

    // Handle 'after' references
    if (result.after) {
      if (Array.isArray(result.after)) {
        const updatedAfter = result.after.filter((afterId) => afterId !== sourceId);
        if (updatedAfter.length === 0) {
          const { after, ...rest } = result;
          result = rest as YamlFlowPlanStep;
        } else if (updatedAfter.length === 1) {
          result = { ...result, after: updatedAfter[0] };
        } else {
          result = { ...result, after: updatedAfter };
        }
      } else if (result.after === sourceId) {
        const { after, ...rest } = result;
        result = rest as YamlFlowPlanStep;
      }
    }

    // Handle conditional branches
    if (result.branches) {
      const updatedBranches = { ...result.branches };
      Object.keys(updatedBranches).forEach((branchKey) => {
        if (updatedBranches[branchKey] === targetId) {
          delete updatedBranches[branchKey];
        }
      });
      if (Object.keys(updatedBranches).length === 0) {
        const { branches, ...rest } = result;
        result = rest as YamlFlowPlanStep;
      } else {
        result = { ...result, branches: updatedBranches };
      }
    }

    return result;
  });

  return {
    nodes: prevFlow.nodes,
    conditions: prevFlow.conditions || [],
    plan: updatedPlan,
  };
}

/**
 * Add a connection to the YAML flow state
 */
export function addConnectionToYamlFlow(
  prevFlow: YamlFlowState,
  sourceId: string,
  targetId: string
): YamlFlowState {
  const updatedPlan = prevFlow.plan.map((step) => {
    if (step.uid !== targetId) return step;

    const existingAfter = step.after;
    let newAfter: string | string[];

    if (!existingAfter) {
      newAfter = sourceId;
    } else if (Array.isArray(existingAfter)) {
      if (!existingAfter.includes(sourceId)) {
        newAfter = [...existingAfter, sourceId];
      } else {
        newAfter = existingAfter;
      }
    } else {
      if (existingAfter !== sourceId) {
        newAfter = [existingAfter, sourceId];
      } else {
        newAfter = existingAfter;
      }
    }

    return { ...step, after: newAfter };
  });

  return {
    nodes: prevFlow.nodes,
    conditions: prevFlow.conditions || [],
    plan: updatedPlan,
  };
}

/**
 * Add a new node to the YAML flow state
 */
export function addNodeToYamlFlow(
  prevFlow: YamlFlowState,
  nodeRid: string,
  nodeName: string,
  nodeConfig: any,
  planStepUid: string
): YamlFlowState {
  const nodeRef = `$ref:${nodeRid}`;
  const nodeExists = prevFlow.nodes.some((node) => node.rid === nodeRef);

  const newYamlNode = {
    rid: nodeRef,
    name: nodeName,
    config: nodeConfig || {},
  };

  const newPlanStep = {
    uid: planStepUid,
    node: nodeRid,
  };

  return {
    nodes: nodeExists ? prevFlow.nodes : [...prevFlow.nodes, newYamlNode],
    conditions: prevFlow.conditions || [],
    plan: [...prevFlow.plan, newPlanStep],
  };
}

/**
 * Add a condition to a node in the YAML flow state
 */
export function addConditionToYamlFlow(
  prevFlow: YamlFlowState,
  nodeId: string,
  conditionRid: string,
  conditionData: { name: string; type?: string; config?: any }
): YamlFlowState {
  // Update plan with exit_condition
  const updatedPlan = prevFlow.plan.map((step) => {
    if (step.uid === nodeId) {
      return { ...step, exit_condition: conditionRid };
    }
    return step;
  });

  // Add condition definition if not exists
  const conditionExists = (prevFlow.conditions || []).some(
    (cond) => cond.rid === `$ref:${conditionRid}`
  );

  const updatedConditions = conditionExists
    ? prevFlow.conditions || []
    : [
        ...(prevFlow.conditions || []),
        {
          rid: `$ref:${conditionRid}`,
          name: conditionData.name,
          type: conditionData.type,
          config: conditionData.config,
        },
      ];

  return {
    ...prevFlow,
    conditions: updatedConditions,
    plan: updatedPlan,
  };
}

/**
 * Remove a condition from a node in the YAML flow state
 */
export function removeConditionFromYamlFlow(
  prevFlow: YamlFlowState,
  nodeId: string,
  conditionRid: string
): YamlFlowState {
  // Remove condition from plan
  const updatedPlan = prevFlow.plan.map((step) => {
    if (step.uid === nodeId && step.exit_condition === conditionRid) {
      const { exit_condition, branches, ...rest } = step;
      return rest as YamlFlowPlanStep;
    }
    return step;
  });

  // Remove condition definition
  const updatedConditions = (prevFlow.conditions || []).filter(
    (cond) => cond.rid !== `$ref:${conditionRid}`
  );

  return {
    ...prevFlow,
    conditions: updatedConditions.length > 0 ? updatedConditions : [],
    plan: updatedPlan,
  };
}

/**
 * Add a conditional branch to the YAML flow state
 */
export function addConditionalBranchToYamlFlow(
  prevFlow: YamlFlowState,
  sourceNodeId: string,
  targetNodeId: string,
  conditionRid: string,
  conditionData: { name?: string; type?: string; config?: any } | null,
  branchConfig: { conditionType: string; branch: string }
): YamlFlowState {
  const updatedPlan = prevFlow.plan.map((step) => {
    if (step.uid !== sourceNodeId) return step;

    const existingBranches = step.branches || {};
    const newBranches = { ...existingBranches };

    if (branchConfig.conditionType === "router_direct") {
      newBranches[targetNodeId] = targetNodeId;
    } else if (branchConfig.conditionType === "router_boolean") {
      const branchKey =
        branchConfig.branch === "true"
          ? "true"
          : branchConfig.branch === "false"
          ? "false"
          : branchConfig.branch;

      newBranches[branchKey] = targetNodeId;
    }

    return {
      ...step,
      exit_condition: conditionRid,
      branches: newBranches,
    };
  });

  // Add condition definition if not exists
  let updatedConditions = prevFlow.conditions || [];
  if (conditionData) {
    const conditionExists = updatedConditions.some(
      (cond) => cond.rid === `$ref:${conditionRid}`
    );
    if (!conditionExists) {
      updatedConditions = [
        ...updatedConditions,
        {
          rid: `$ref:${conditionRid}`,
          name: conditionData.name || '',
          type: conditionData.type,
          config: conditionData.config,
        },
      ];
    }
  }

  return {
    nodes: prevFlow.nodes,
    conditions: updatedConditions.length > 0 ? updatedConditions : [],
    plan: updatedPlan,
  };
}

