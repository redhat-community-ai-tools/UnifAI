import React, { useState } from "react";
import { ChevronDown, ChevronRight, Info } from "lucide-react";
import type { ResponseMetadata } from "./types";

interface ResponseMetadataBadgeProps {
  metadata: ResponseMetadata;
}

/**
 * Open/closed state survives a remount: the chat re-renders its message list on every stream tick and sync,
 * which recreated this component and snapped the panel shut about 300 ms after a click. The state is kept
 * outside React, keyed by the message's identity.
 */
const openBadges = new Set<string>();

/** Render any JSON value as a short string. */
const display = (value: unknown): string =>
  typeof value === "string" ? value : JSON.stringify(value);

/**
 * Small collapsible per-message badge showing which provider/model produced a
 * response, based on the non-standard fields the LLM endpoint returned.
 * When the backend attached a `routing` explanation, a "Why this model" panel
 * shows it; the browser never fetches anything itself.
 */
export const ResponseMetadataBadge: React.FC<ResponseMetadataBadgeProps> = ({ metadata }) => {
  const fields = metadata.fields ?? {};
  const badgeKey = metadata.response_id ?? JSON.stringify([metadata.model, metadata.routing, fields]);
  const [open, setOpenState] = useState(() => openBadges.has(badgeKey));
  const setOpen = (update: (v: boolean) => boolean) => {
    const next = update(openBadges.has(badgeKey));
    if (next) openBadges.add(badgeKey);
    else openBadges.delete(badgeKey);
    setOpenState(next);
  };
  // Any field named "provider" or "<prefix>_provider" identifies the serving provider.
  const providerKey = Object.keys(fields).find((k) => k === "provider" || k.endsWith("_provider"));
  const provider = metadata.routing?.provider ?? (providerKey ? fields[providerKey] : undefined);
  const summary = [provider && display(provider), metadata.model].filter(Boolean).join(" · ");

  return (
    <div className="mt-2 text-xs text-gray-400" data-testid="response-metadata">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md border border-gray-600/60 hover:text-gray-200"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <Info className="h-3 w-3" aria-hidden="true" />
        <span>{summary || "Response details"}</span>
      </button>
      {open && (
        <div className="mt-1 ml-1 p-2 rounded-md border border-gray-700/60 space-y-1">
          {Object.entries(fields).map(([k, v]) => (
            <div key={k}>
              <span className="text-gray-500">{k}: </span>
              <span className="text-gray-300">{display(v)}</span>
            </div>
          ))}
          {metadata.response_id && (
            <div>
              <span className="text-gray-500">response id: </span>
              <span className="text-gray-300">{metadata.response_id}</span>
            </div>
          )}
          {metadata.routing && (
            <div data-testid="response-metadata-why">
              <div className="text-gray-500">Why this model</div>
              {Object.entries(metadata.routing).map(([k, v]) => (
                <div key={k}>
                  <span className="text-gray-500">{k}: </span>
                  <span className="text-gray-300">{display(v)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ResponseMetadataBadge;
