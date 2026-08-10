import { Dispatch, SetStateAction, useEffect, useState } from "react";

export type RefOptionsMap = { [category: string]: any[] };

/**
 * Fetches `$ref` dropdown options for a set of resource categories — the
 * "fetch each category, tolerate individual failures" loop shared by
 * `ElementForm` and `BuiltinConfigureModal`.
 *
 * Callers derive `refCategories` themselves (which fields to scan for refs,
 * and when, differs meaningfully between "edit the base definition" and
 * "set my personal overlay" forms) — this hook only owns the "go fetch
 * options for these categories" mechanics. Returns a `[value, setter]` pair
 * (like `useState`) so callers that need to optimistically patch a single
 * category in place (e.g. after saving a nested $ref'd resource) still can.
 */
export function useResourceRefOptions(
  refCategories: Set<string>,
  fetchResourcesForCategory: (category: string, ownership?: string) => Promise<any[]>,
  ownershipFilter?: string,
): [RefOptionsMap, Dispatch<SetStateAction<RefOptionsMap>>] {
  const [refOptions, setRefOptions] = useState<RefOptionsMap>({});
  // `refCategories` is typically recomputed (new Set instance) every render,
  // so depend on its serialized contents instead of its identity.
  const categoriesKey = Array.from(refCategories).sort().join(",");

  useEffect(() => {
    if (refCategories.size === 0) return;
    let cancelled = false;

    (async () => {
      const categories = Array.from(refCategories);
      const results = await Promise.allSettled(
        categories.map((category) => fetchResourcesForCategory(category, ownershipFilter)),
      );
      const options: RefOptionsMap = {};
      results.forEach((result, i) => {
        options[categories[i]] = result.status === "fulfilled" ? result.value : [];
      });
      if (!cancelled) setRefOptions(options);
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoriesKey, fetchResourcesForCategory, ownershipFilter]);

  return [refOptions, setRefOptions];
}
