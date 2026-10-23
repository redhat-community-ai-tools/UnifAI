import { useEffect, useState } from "react";
import { useRoute } from "wouter";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BlueprintSummary, fetchBlueprintSummaries } from "@/api/blueprints";
import { useWorkspaceIdentity } from "@/hooks/use-workspace-identity";

/** Public, descriptive sheet of an agent, stored by the platform as `metadata.display` of its workflows. */
export interface AgentDisplay {
  agent?: string;
  title?: string;
  displayName?: string;
  description?: string;
  tileDescription?: string;
  maintainer?: string;
  state?: string;
  classification?: string;
  icon?: string;
  color?: string;
  tasks?: { name: string; title?: string }[];
}

/**
 * The sheet of `agent` among the blueprints the caller can already see, or undefined. A caller who cannot see
 * any workflow of the agent gets the same result as for an unknown agent, so existence is not revealed.
 */
export function findAgentSheet(summaries: BlueprintSummary[], agent: string): AgentDisplay | undefined {
  for (const s of summaries) {
    const d = s.metadata?.display as AgentDisplay | undefined;
    if (d && typeof d === "object" && d.agent === agent) return d;
  }
  return undefined;
}

// Only a plain CSS color keyword or #rrggbb is applied; anything else is ignored.
const SAFE_COLOR = /^(#[0-9a-fA-F]{6}|[a-zA-Z]{3,30})$/;

export default function AgentSheet() {
  const [, params] = useRoute("/agents/:agent");
  const agent = params?.agent ?? "";
  const { teamId } = useWorkspaceIdentity();
  const [state, setState] = useState<"loading" | "found" | "notfound">("loading");
  const [sheet, setSheet] = useState<AgentDisplay | undefined>();

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    fetchBlueprintSummaries(teamId)
      .then((summaries) => {
        if (cancelled) return;
        const found = findAgentSheet(summaries, agent);
        setSheet(found);
        setState(found ? "found" : "notfound");
      })
      .catch(() => {
        if (!cancelled) setState("notfound");
      });
    return () => {
      cancelled = true;
    };
  }, [agent, teamId]);

  if (state === "loading") {
    return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;
  }
  if (state === "notfound" || !sheet) {
    return (
      <div className="p-6" data-testid="agent-not-found">
        <h1 className="text-xl font-semibold">Agent not found</h1>
        <p className="mt-2 text-sm text-muted-foreground">There is no agent with this name that you can use.</p>
      </div>
    );
  }

  const accent = sheet.color && SAFE_COLOR.test(sheet.color) ? sheet.color : undefined;
  return (
    <div className="p-6 max-w-3xl space-y-4" data-testid="agent-sheet">
      <Card style={accent ? { borderTop: `4px solid ${accent}` } : undefined}>
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            <span>{sheet.displayName || sheet.title || sheet.agent}</span>
            {sheet.state && <Badge variant="secondary">{sheet.state}</Badge>}
            {sheet.classification && <Badge variant="outline">Up to {sheet.classification}</Badge>}
          </CardTitle>
          {sheet.tileDescription && <p className="text-sm text-muted-foreground">{sheet.tileDescription}</p>}
        </CardHeader>
        <CardContent className="space-y-4">
          {sheet.title && sheet.title !== sheet.displayName && <h2 className="font-medium">{sheet.title}</h2>}
          {/* Plain text only: the platform refuses raw HTML, and it is rendered as text here. */}
          {sheet.description && <p className="whitespace-pre-wrap text-sm">{sheet.description}</p>}
          {sheet.tasks && sheet.tasks.length > 0 && (
            <div>
              <h3 className="text-sm font-medium mb-1">What it does</h3>
              <ul className="list-disc pl-5 text-sm">
                {sheet.tasks.map((t) => (
                  <li key={t.name}>{t.title || t.name}</li>
                ))}
              </ul>
            </div>
          )}
          {sheet.maintainer && <p className="text-xs text-muted-foreground">Maintained by {sheet.maintainer}</p>}
        </CardContent>
      </Card>
    </div>
  );
}
