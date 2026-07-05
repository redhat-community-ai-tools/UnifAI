import { useMemo } from "react";
import type { PromptShortcut } from "@/api/blueprints";

interface HubWithSpecCache {
  selectedSession?: { blueprintId?: string } | null;
  blueprintSpecCache: Map<string, any>;
}


/**
 * Derives the active manual prompt shortcuts from the selected session's blueprint spec.
 *
 * Returns `undefined` when no session/blueprint is selected or no shortcuts are configured.
 */

export function useDefaultPrompts(hub: HubWithSpecCache): PromptShortcut[] | undefined {
  return useMemo(() => {
    if (!hub.selectedSession?.blueprintId) return undefined;
    const specDict = hub.blueprintSpecCache.get(hub.selectedSession.blueprintId);
    const shortcuts = specDict?.prompt_shortcuts;
    if (!Array.isArray(shortcuts)) return undefined;
    return shortcuts.filter((p: PromptShortcut) => p.kind === "manual");
  }, [hub.selectedSession?.blueprintId, hub.blueprintSpecCache]);
}