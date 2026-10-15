#!/usr/bin/env python3
"""Generates crds/*.yaml (unifai.startx.fr/v1alpha1). Run: python3 gen_crds.py"""
import pathlib
import yaml

GROUP, VER = "unifai.startx.fr", "v1alpha1"
OBJ = {"type": "object", "x-kubernetes-preserve-unknown-fields": True}
S = {"type": "string"}
COMMON = {
    "owner": {**S, "default": "admin", "description": "UnifAI user owning the object (workspace identity)"},
    "teamId": {**S, "description": "Use a team workspace instead of the user's"},
    "unifaiName": {**S, "description": "Name in UnifAI (defaults to metadata.name)"},
}
SECRETS = {"type": "array", "description": "Values injected into config (dotted path) from a Secret",
           "items": {"type": "object", "required": ["path", "secretKeyRef"], "properties": {
               "path": S, "secretKeyRef": {"type": "object", "required": ["name", "key"], "properties": {"name": S, "key": S}}}}}
CFG = {"config": {**OBJ, "description": "UnifAI cfg_dict; `$ref:<kind>/<name>` references another UnifAI object"}, "secretRefs": SECRETS}
STATUS = {"type": "object", "x-kubernetes-preserve-unknown-fields": True}

# Types = what the deployed instance serves (GET /api/catalog/elements.list.get), not the whole upstream code base.
# kind, plural, short, spec props, required, extra printer columns
RES_TYPES = {
    "LLM": ("unifaillms", "ullm", ["openai", "openai_compatible", "google_genai"]),
    "Provider": ("unifaiproviders", "uprov", ["mcp_server"]),
    "Tool": ("unifaitools", "utool", ["ssh_exec", "oc_exec", "web_fetch"]),
    "Condition": ("unifaiconditions", "ucond", ["router_direct"]),
    "Retriever": ("unifairetrievers", "uretr", ["docs_rag"]),
    "Sandbox": ("unifaisandboxes", "usbx", ["openshell_sandbox"]),
    "Agent": ("unifaiagents", "uagent", ["custom_agent_node", "orchestrator_node", "deep_agent_node", "claude_agent_node",
                                         "a2a_agent_node"]),
}
KINDS = {}
for k, (plural, short, types) in RES_TYPES.items():
    KINDS[k] = (plural, short, {**COMMON, "type": {**S, "enum": types}, **CFG}, ["type"], [("Type", ".spec.type")])
KINDS["Workflow"] = ("unifaiworkflows", "uwf", {**COMMON, "description": S, "secretRefs": SECRETS,
                     "blueprint": {**OBJ, "description": "BlueprintDraft: nodes, plan, conditions... (inline or `$ref:` / `$rid:` to library objects)"}},
                     ["blueprint"], [("BlueprintId", ".status.blueprintId")])
KINDS["Schedule"] = ("unifaischedules", "usch", {**COMMON, "workflow": {**S, "description": "UnifAI workflow (blueprint) name"},
                     "inputs": {**OBJ, "description": "Workflow inputs, e.g. user_prompt"},
                     "suspend": {"type": "boolean"},
                     "schedule": {"type": "object", "description": "interval (ISO-8601) XOR cron_expression", "properties": {
                         "interval": S, "cron_expression": S, "timezone": S, "overlap_policy": {**S, "enum": ["skip", "buffer_one", "cancel_other"]},
                         "start_at": S, "end_at": S, "remaining_actions": {"type": "integer"}, "enabled": {"type": "boolean"}}}},
                     ["workflow", "inputs", "schedule"], [("Workflow", ".spec.workflow"), ("ScheduleId", ".status.scheduleId")])
KINDS["Template"] = ("unifaitemplates", "utpl", {**COMMON, "secretRefs": SECRETS, "draft": {**OBJ, "description": "BlueprintDraft"},
                     "placeholders": OBJ, "metadata": OBJ}, ["draft"], [("TemplateId", ".status.templateId")])
KINDS["Chat"] = ("unifaichats", "uchat", {**COMMON, "workflow": S, "prompt": S, "title": S, "hitl": {"type": "boolean"}},
                 ["workflow", "prompt"], [("Workflow", ".spec.workflow"), ("Session", ".status.sessionId")])
KINDS["RAGPipeline"] = ("unifairagpipelines", "urag", {**COMMON, "skipValidation": {"type": "boolean"},
                        "documents": {"type": "array", "items": {"type": "object", "required": ["name", "source"], "properties": {
                            "name": {**S, "description": "File name with extension (pdf, docx, md, pptx)"},
                            "tags": {"type": "array", "items": S}, "metadata": OBJ,
                            "source": {"type": "object", "properties": {"inline": S, "url": S, "configMapKeyRef": {
                                "type": "object", "required": ["name", "key"], "properties": {"name": S, "key": S}}}}}}}},
                        ["documents"], [])

out = pathlib.Path(__file__).parent / "crds"
out.mkdir(exist_ok=True)
for kind, (plural, short, props, req, cols) in KINDS.items():
    cols = [{"name": "Phase", "type": "string", "jsonPath": ".status.phase"}] + [
        {"name": n, "type": "string", "jsonPath": p} for n, p in cols] + [
        {"name": "Message", "type": "string", "jsonPath": ".status.message", "priority": 1},
        {"name": "Age", "type": "date", "jsonPath": ".metadata.creationTimestamp"}]
    crd = {"apiVersion": "apiextensions.k8s.io/v1", "kind": "CustomResourceDefinition",
           "metadata": {"name": f"{plural}.{GROUP}"},
           "spec": {"group": GROUP, "scope": "Namespaced",
                    "names": {"kind": f"Unifai{kind}", "plural": plural, "singular": f"unifai{kind.lower()}", "shortNames": [short],
                              "categories": ["unifai"]},
                    "versions": [{"name": VER, "served": True, "storage": True, "subresources": {"status": {}},
                                  "additionalPrinterColumns": cols,
                                  "schema": {"openAPIV3Schema": {"type": "object", "properties": {
                                      "spec": {"type": "object", "required": req, "properties": props},
                                      "status": STATUS}}}}]}}
    (out / f"{plural}.yaml").write_text(yaml.safe_dump(crd, sort_keys=False))
print("generated", len(KINDS), "CRDs")
