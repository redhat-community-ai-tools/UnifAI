/**
 * Resource category constants and utilities
 * Centralizes category mapping logic to follow DRY principle
 */

/**
 * Maps backend category names to display names
 * Used for normalizing categories across the application
 */
export const CATEGORY_DISPLAY_MAP: Record<string, string> = {
  nodes: 'agents',
  // Add other mappings as needed
};

/**
 * Normalizes a category name by mapping it to its display name
 * @param category - The category name to normalize
 * @returns The normalized category name (lowercase, mapped if applicable)
 */
export function normalizeCategory(category: string): string {
  const normalized = category.toLowerCase();
  return CATEGORY_DISPLAY_MAP[normalized] || normalized;
}

/**
 * Fallback categories used when backend categories are unavailable
 */
export const FALLBACK_CATEGORIES = [
  'conditions',
  'llms',
  'agents',
  'providers',
  'retrievers',
  'tools',
] as const;

