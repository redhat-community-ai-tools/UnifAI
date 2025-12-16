import { useMemo } from "react";
import { normalizeCategory, FALLBACK_CATEGORIES } from "@/constants/resources";

interface ResourceCategory {
  category: string;
  count: number;
  types: { [type: string]: number };
}

export function useResourceDistribution(
  resourceCategories: string[],
  resourcesByCategory: ResourceCategory[]
) {
  const resourceDistribution = useMemo(() => {
    const allCategories =
      resourceCategories.length > 0
        ? resourceCategories.map((cat) => normalizeCategory(cat))
        : FALLBACK_CATEGORIES;

    const resourceDistributionMap = new Map(
      (resourcesByCategory || []).map((cat) => {
        const categoryKey = normalizeCategory(cat.category);
        return [categoryKey, { ...cat, category: categoryKey }];
      })
    );

    return allCategories.map((category) => {
      const existing = resourceDistributionMap.get(category);
      if (existing) {
        return existing;
      }
      return {
        category,
        count: 0,
        types: {},
      };
    });
  }, [resourceCategories, resourcesByCategory]);

  return resourceDistribution;
}

