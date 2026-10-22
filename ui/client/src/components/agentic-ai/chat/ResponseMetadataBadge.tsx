import React, { useCallback, useState } from "react";
import { ChevronDown, ChevronRight, Info } from "lucide-react";
import type { ResponseMetadata } from "./types";

interface ResponseMetadataBadgeProps {
  metadata: ResponseMetadata;
}

/** Render any JSON value as a short string. */
const display = (value: unknown): string =>
  typeof value === "string" ? value : JSON.stringify(value);

/**
 * Small collapsible per-message badge showing which provider/model produced a
 * response, based on the non-standard fields the LLM endpoint returned.
 * When the backend resolved a `lookup_url`, a "Why this model" panel fetches
 * the explanation on demand.
 */
export const ResponseMetadataBadge: React.FC<ResponseMetadataBadgeProps> = ({ metadata }) => {
  const [open, setOpen] = useState(false);
  const [whyState, setWhyState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [why, setWhy] = useState<Record<string, unknown> | null>(null);

  const fields = metadata.fields ?? {};
  // Any field named "provider" or "<prefix>_provider" identifies the serving provider.
  const providerKey = Object.keys(fields).find((k) => k === "provider" || k.endsWith("_provider"));
  const provider = providerKey ? fields[providerKey] : undefined;
  const summary = [provider && display(provider), metadata.model].filter(Boolean).join(" · ");

  const loadWhy = useCallback(async () => {
    if (!metadata.lookup_url || whyState === "loading") return;
    setWhyState("loading");
    try {
      const res = await fetch(metadata.lookup_url, { credentials: "include" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setWhy(await res.json());
      setWhyState("done");
    } catch {
      setWhyState("error");
    }
  }, [metadata.lookup_url, whyState]);

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
          {metadata.lookup_url && (
            <div>
              {whyState === "idle" && (
                <button type="button" onClick={loadWhy} className="underline hover:text-gray-200">
                  Why this model
                </button>
              )}
              {whyState === "loading" && <span>Loading explanation...</span>}
              {whyState === "error" && (
                <span>
                  Explanation unavailable.{" "}
                  <button type="button" onClick={loadWhy} className="underline">
                    Retry
                  </button>
                </span>
              )}
              {whyState === "done" && why && (
                <div data-testid="response-metadata-why">
                  <div className="text-gray-500">Why this model</div>
                  {Object.entries(why).map(([k, v]) => (
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
      )}
    </div>
  );
};

export default ResponseMetadataBadge;
