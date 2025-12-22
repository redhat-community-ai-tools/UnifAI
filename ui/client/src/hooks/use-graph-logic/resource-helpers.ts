/**
 * Resource transformation helpers
 */

import { BuildingBlock } from '@/types/graph';
import { getCategoryDisplay } from '@/components/shared/helpers';

/**
 * Transform a resource from the API into a BuildingBlock
 */
export function transformResourceToBlock(resource: any): BuildingBlock {
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
}

/**
 * Filter blocks by category
 */
export function filterBlocksByCategory(
  blocks: BuildingBlock[],
  category: string
): BuildingBlock[] {
  return blocks.filter(
    (block) => block.workspaceData?.category === category
  );
}

/**
 * Find a block by rid
 */
export function findBlockByRid(
  blocks: BuildingBlock[],
  rid: string
): BuildingBlock | undefined {
  return blocks.find((block) => block.workspaceData?.rid === rid);
}

/**
 * Find a condition block by rid
 */
export function findConditionBlockByRid(
  blocks: BuildingBlock[],
  rid: string
): BuildingBlock | undefined {
  return blocks.find(
    (block) =>
      block.workspaceData?.category === 'conditions' &&
      block.workspaceData?.rid === rid
  );
}

