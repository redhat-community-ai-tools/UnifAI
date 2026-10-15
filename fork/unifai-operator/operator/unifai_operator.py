"""UnifAI operator: reconciles unifai.startx.fr/v1alpha1 custom resources into UnifAI through its REST API.

Resource-like kinds (LLM, Provider, Tool, Condition, Retriever, Sandbox, Agent) are rows of the MAS `resources` collection.
Other kinds (Workflow, Schedule, Template, Chat, RAGPipeline) use their dedicated endpoints.
In specs, `$ref:<kind>/<name>` is replaced by `$ref:<rid>` and `$rid:<kind>/<name>` by the bare rid (used in blueprint plans).
"""
import base64
import copy
import hashlib
import json
import re
from datetime import datetime, timezone

import kopf
import kubernetes
import requests

import client
from client import ApiError, KIND_CATEGORY, REF_RE

GROUP, VERSION = "unifai.startx.fr", "v1alpha1"
ADOPT = "unifai.startx.fr/adopt"
RETRY = 10

# plural -> (category, ref kind)
RESOURCE_KINDS = {
    "unifaillms": ("llms", "llm"), "unifaiproviders": ("providers", "provider"), "unifaitools": ("tools", "tool"),
    "unifaiconditions": ("conditions", "condition"), "unifairetrievers": ("retrievers", "retriever"),
    "unifaisandboxes": ("sandboxes", "sandbox"), "unifaiagents": ("nodes", "agent"),
}
REF_ANY = re.compile(r"^\$(ref|rid):(llm|provider|tool|retriever|sandbox|condition|agent)/(.+)$")


@kopf.on.startup()
def startup(settings: kopf.OperatorSettings, **_):
    settings.persistence.finalizer = "unifai.startx.fr/finalizer"
    settings.posting.level = 20
    try:
        kubernetes.config.load_incluster_config()
    except kubernetes.config.ConfigException:
        kubernetes.config.load_kube_config()


# ---------------------------------------------------------------------------- helpers
def _api(spec, kind="mas"):
    f = client.mas if kind == "mas" else client.rag
    return f(spec.get("owner") or "admin", spec.get("teamId"))


def _hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _set_path(cfg, path, value):
    parts = path.split(".")
    for p in parts[:-1]:
        cfg = cfg.setdefault(p, {})
    cfg[parts[-1]] = value


def _secret_value(namespace, ref):
    try:
        sec = kubernetes.client.CoreV1Api().read_namespaced_secret(ref["name"], namespace)
    except kubernetes.client.ApiException as e:
        raise kopf.TemporaryError(f"secret {ref['name']}: {e.reason}", delay=RETRY)
    if ref["key"] not in (sec.data or {}):
        raise kopf.TemporaryError(f"secret {ref['name']} has no key {ref['key']}", delay=RETRY)
    return base64.b64decode(sec.data[ref["key"]]).decode()


def _apply_secrets(spec, namespace, target):
    for s in spec.get("secretRefs") or []:
        _set_path(target, s["path"], _secret_value(namespace, s["secretKeyRef"]))


class Resolver:
    """Resolves `$ref:kind/name` tokens to resource ids (library resources of the owner)."""

    def __init__(self, api):
        self.api, self.cache = api, {}

    def rid(self, kind, name):
        cat = KIND_CATEGORY[kind]
        if name not in self._load(cat):
            raise kopf.TemporaryError(f"{kind} '{name}' not found in UnifAI (not reconciled yet?)", delay=RETRY)
        return self.cache[cat][name]["rid"]

    def _load(self, cat):
        if cat not in self.cache:
            res = self.api.call("GET", "/api/resources/resources.list", {"category": cat, "limit": 200})
            self.cache[cat] = {r["name"]: r for r in res["resources"]}
        return self.cache[cat]

    def expand_library_nodes(self, bp):
        """Blueprint entries `{rid: $ref:<rid>}` without config get the library resource's config (as the UI stores them)."""
        for cat in ("nodes", "conditions"):
            by_rid = {r["rid"]: r for r in self._load(cat).values()}
            for item in bp.get(cat) or []:
                rid = str(item.get("rid", ""))
                if rid.startswith("$ref:") and not item.get("config") and rid[5:] in by_rid:
                    res = by_rid[rid[5:]]
                    item["config"] = res["cfg_dict"]
                    item.setdefault("name", res["name"])
                    item.setdefault("type", None)
        return bp

    def walk(self, obj):
        if isinstance(obj, dict):
            return {k: self.walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.walk(v) for v in obj]
        if isinstance(obj, str):
            m = REF_ANY.match(obj)
            if m:
                rid = self.rid(m.group(2), m.group(3))
                return f"$ref:{rid}" if m.group(1) == "ref" else rid
        return obj


def _status(patch, phase, message="", **extra):
    patch.status["phase"] = phase
    patch.status["message"] = message[:500]
    patch.status["lastReconciled"] = datetime.now(timezone.utc).isoformat()
    patch.status.update(extra)


def _fail(patch, e):
    _status(patch, "Error", str(e))
    raise kopf.PermanentError(str(e))


def _adopt_check(annotations, what, patch):
    if (annotations or {}).get(ADOPT) != "true":
        _fail(patch, f"{what} already exists in UnifAI and is not managed by this CR; annotate the CR with {ADOPT}=true to take it over")


# ---------------------------------------------------------------------------- resource kinds
def reconcile_resource(plural, spec, name, namespace, meta, status, patch, **_):
    category, _kind = RESOURCE_KINDS[plural]
    api = _api(spec)
    uname = spec.get("unifaiName") or name
    rtype = spec["type"]
    cfg = copy.deepcopy(spec.get("config") or {})
    cfg.setdefault("type", rtype)
    _apply_secrets(spec, namespace, cfg)
    cfg = Resolver(api).walk(cfg)
    h = _hash([rtype, uname, cfg])

    try:
        api.call("POST", "/api/resources/config.validate", body={"category": category, "type": rtype, "name": uname, "config": cfg})
    except ApiError as e:
        if e.status in (400, 422) or "No spec registered" in str(e.body):
            _fail(patch, e)
        raise kopf.TemporaryError(str(e), delay=RETRY)

    existing = None
    for r in api.call("GET", "/api/resources/resources.list", {"category": category, "limit": 200})["resources"]:
        if r["name"] == uname:
            existing = r
    rid = status.get("rid")
    if existing and existing["rid"] != rid:
        _adopt_check(meta.get("annotations"), f"{category}/{uname}", patch)
    if existing and existing["type"] != rtype:
        api.call("DELETE", "/api/resources/resource.delete", {"resourceId": existing["rid"]})
        existing = None
    try:
        if existing:
            if status.get("hash") == h and rid == existing["rid"]:
                return
            api.call("PUT", "/api/resources/resource.update", body={"resourceId": existing["rid"], "config": cfg, "name": uname})
            rid = existing["rid"]
        else:
            res = api.call("POST", "/api/resources/resource.save", body={"category": category, "type": rtype, "name": uname, "config": cfg})
            rid = res.get("rid") or (res.get("resource") or {}).get("rid") or Resolver(api).rid(_kind_of(category), uname)
    except ApiError as e:
        if e.status in (400, 409, 422):
            _fail(patch, e)
        raise kopf.TemporaryError(str(e), delay=RETRY)
    _status(patch, "Ready", f"{category}/{uname}", rid=rid, hash=h)


def _kind_of(category):
    return next(k for k, c in KIND_CATEGORY.items() if c == category)


def delete_resource(plural, spec, status, **_):
    rid = status.get("rid")
    if not rid:
        return
    try:
        _api(spec).call("DELETE", "/api/resources/resource.delete", {"resourceId": rid})
    except ApiError as e:
        if e.status == 404:
            return
        raise kopf.TemporaryError(f"cannot delete (still referenced?): {e}", delay=RETRY * 3)


# ---------------------------------------------------------------------------- workflows (blueprints)
def _find_blueprint(api, name):
    for b in api.call("GET", "/api/blueprints/available.blueprints.summary.get"):
        if b["name"] == name:
            return b["blueprint_id"]


@kopf.on.create(GROUP, VERSION, "unifaiworkflows")
@kopf.on.update(GROUP, VERSION, "unifaiworkflows")
@kopf.on.resume(GROUP, VERSION, "unifaiworkflows")
def reconcile_workflow(spec, name, namespace, meta, status, patch, **_):
    api = _api(spec)
    uname = spec.get("unifaiName") or name
    bp = copy.deepcopy(spec["blueprint"])
    bp["name"] = uname
    bp.setdefault("description", spec.get("description", ""))
    _apply_secrets(spec, namespace, bp)
    rs = Resolver(api)
    bp = rs.expand_library_nodes(rs.walk(bp))
    h = _hash(bp)
    bid = status.get("blueprintId")
    existing = _find_blueprint(api, uname)
    if existing and existing != bid:
        _adopt_check(meta.get("annotations"), f"workflow {uname}", patch)
    bid = existing or bid
    try:
        if bid:
            if status.get("hash") == h:
                return
            api.call("PUT", "/api/blueprints/blueprint.update", body={"blueprintId": bid, "blueprintRaw": json.dumps(bp)})
        else:
            bid = api.call("POST", "/api/blueprints/blueprint.save", body={"blueprintRaw": json.dumps(bp)})["blueprint_id"]
    except ApiError as e:
        if e.status in (400, 409, 422):
            _fail(patch, e)
        raise kopf.TemporaryError(str(e), delay=RETRY)
    _status(patch, "Ready", f"blueprint {uname}", blueprintId=bid, hash=h)


@kopf.on.delete(GROUP, VERSION, "unifaiworkflows")
def delete_workflow(spec, status, **_):
    bid = status.get("blueprintId")
    if bid:
        try:
            _api(spec).call("DELETE", "/api/blueprints/remove.blueprint", {"blueprintId": bid}, ok=(200, 404))
        except ApiError as e:
            raise kopf.TemporaryError(str(e), delay=RETRY * 3)


# ---------------------------------------------------------------------------- schedules
def _workflow_id(api, spec):
    bid = _find_blueprint(api, spec["workflow"])
    if not bid:
        raise kopf.TemporaryError(f"workflow '{spec['workflow']}' not found in UnifAI", delay=RETRY)
    return bid


@kopf.on.create(GROUP, VERSION, "unifaischedules")
@kopf.on.update(GROUP, VERSION, "unifaischedules")
@kopf.on.resume(GROUP, VERSION, "unifaischedules")
def reconcile_schedule(spec, status, patch, **_):
    api = _api(spec)
    bid = _workflow_id(api, spec)
    inputs, sched = spec.get("inputs") or {}, dict(spec["schedule"])
    enabled = sched.pop("enabled", True) and not spec.get("suspend", False)
    sched["enabled"] = enabled
    h = _hash([bid, inputs, sched])
    sid = status.get("scheduleId")
    try:
        if sid and status.get("blueprintId") != bid:  # workflow replaced: recreate
            api.call("DELETE", "/api/schedules/schedule.delete", body={"scheduleId": sid}, ok=(200, 404))
            sid = None
        if sid:
            if status.get("hash") == h:
                return
            api.call("POST", "/api/schedules/schedule.update", body={"scheduleId": sid, "inputs": inputs, "schedule": sched})
        else:
            sid = api.call("POST", "/api/schedules/schedule.create",
                           body={"blueprintId": bid, "inputs": inputs, "source": "manual", "schedule": sched})["id"]
    except ApiError as e:
        if e.status in (400, 409, 422):
            _fail(patch, e)
        raise kopf.TemporaryError(str(e), delay=RETRY)
    _status(patch, "Ready" if enabled else "Suspended", f"schedule {sid}", scheduleId=sid, blueprintId=bid, hash=h)


@kopf.on.delete(GROUP, VERSION, "unifaischedules")
def delete_schedule(spec, status, **_):
    if status.get("scheduleId"):
        _api(spec).call("DELETE", "/api/schedules/schedule.delete", body={"scheduleId": status["scheduleId"]}, ok=(200, 404))


# ---------------------------------------------------------------------------- templates
@kopf.on.create(GROUP, VERSION, "unifaitemplates")
@kopf.on.update(GROUP, VERSION, "unifaitemplates")
@kopf.on.resume(GROUP, VERSION, "unifaitemplates")
def reconcile_template(spec, namespace, status, patch, **_):
    api = _api(spec)  # owner must be an UnifAI admin
    draft = copy.deepcopy(spec["draft"])
    _apply_secrets(spec, namespace, draft)
    body = {"draft": draft, "placeholders": spec.get("placeholders") or {"categories": []}, "metadata": spec.get("metadata") or {}}
    h = _hash(body)
    tid = status.get("templateId")
    if tid and status.get("hash") == h:
        return
    try:
        if tid:  # no update endpoint: delete + create
            api.call("DELETE", "/api/templates/template.delete", {"templateId": tid}, ok=(200, 404))
        tid = api.call("POST", "/api/templates/template.create", body=body)["template_id"]
    except ApiError as e:
        if e.status in (400, 403, 409, 422):
            _fail(patch, e)
        raise kopf.TemporaryError(str(e), delay=RETRY)
    _status(patch, "Ready", f"template {tid}", templateId=tid, hash=h)


@kopf.on.delete(GROUP, VERSION, "unifaitemplates")
def delete_template(spec, status, **_):
    if status.get("templateId"):
        _api(spec).call("DELETE", "/api/templates/template.delete", {"templateId": status["templateId"]}, ok=(200, 404))


# ---------------------------------------------------------------------------- chats (one-shot sessions)
@kopf.on.create(GROUP, VERSION, "unifaichats")
@kopf.on.resume(GROUP, VERSION, "unifaichats")
def run_chat(spec, status, patch, name, **_):
    """Creates a session on the workflow and submits the prompt once; the result is read back on later timers."""
    if status.get("sessionId"):
        return
    api = _api(spec)
    bid = _workflow_id(api, spec)
    try:
        sid = api.call("POST", "/api/sessions/user.session.create",
                       body={"blueprintId": bid, "metadata": {"title": spec.get("title") or name, "source": "operator"},
                             "hitlEnabled": bool(spec.get("hitl", False))})
        api.call("POST", "/api/sessions/user.session.submit", body={"sessionId": sid, "inputs": {"user_prompt": spec["prompt"]}})
    except ApiError as e:
        if e.status in (400, 404, 422):
            _fail(patch, e)
        raise kopf.TemporaryError(str(e), delay=RETRY)
    _status(patch, "Running", "submitted", sessionId=sid)


@kopf.timer(GROUP, VERSION, "unifaichats", interval=10, initial_delay=10, idle=5)
def poll_chat(spec, status, patch, **_):
    sid = status.get("sessionId")
    if not sid or status.get("phase") not in ("Running",):
        return
    api = _api(spec)
    try:
        st = api.call("GET", "/api/sessions/session.status.get", {"sessionId": sid})
        s = st if isinstance(st, str) else (st.get("status") or st.get("state") or "")
        s = str(s).upper()
        if s in ("COMPLETED", "FAILED", "CANCELLED", "ERROR", "DONE", "SUCCESS", "SUCCEEDED", "IDLE"):
            chat = api.call("GET", "/api/sessions/session.chat.get", {"sessionId": sid})
            patch.status["result"] = json.dumps(chat, default=str)[:4000]
            _status(patch, "Failed" if s in ("FAILED", "ERROR") else "Completed", f"session {s}")
        else:
            patch.status["message"] = f"session {s}"
    except ApiError as e:
        patch.status["message"] = str(e)[:300]


@kopf.on.delete(GROUP, VERSION, "unifaichats")
def delete_chat(spec, status, **_):
    if status.get("sessionId"):
        try:
            _api(spec).call("DELETE", "/api/sessions/session.delete", {"sessionId": status["sessionId"]}, ok=(200, 404))
        except ApiError:
            pass


# ---------------------------------------------------------------------------- RAG pipeline (document ingestion)
def _doc_content(doc, namespace):
    src = doc.get("source") or {}
    if "inline" in src:
        return src["inline"].encode()
    if "url" in src:
        r = requests.get(src["url"], timeout=60)
        r.raise_for_status()
        return r.content
    if "configMapKeyRef" in src:
        ref = src["configMapKeyRef"]
        cm = kubernetes.client.CoreV1Api().read_namespaced_config_map(ref["name"], namespace)
        return cm.data[ref["key"]].encode()
    raise kopf.PermanentError(f"document {doc.get('name')}: source needs inline, url or configMapKeyRef")


@kopf.on.create(GROUP, VERSION, "unifairagpipelines")
@kopf.on.update(GROUP, VERSION, "unifairagpipelines")
@kopf.on.resume(GROUP, VERSION, "unifairagpipelines")
def reconcile_rag(spec, namespace, status, patch, **_):
    """Uploads the declared documents then starts the document pipeline (chunk + embed + Qdrant) on rag-server."""
    api = _api(spec, "rag")
    docs = spec["documents"]
    contents = {d["name"]: _doc_content(d, namespace) for d in docs}
    h = _hash({n: hashlib.sha256(c).hexdigest() for n, c in contents.items()} | {"tags": [d.get("tags") for d in docs]})
    if status.get("hash") == h:
        return
    try:
        api.call("POST", "/api/docs/upload", body={"files": [{"name": n, "content": base64.b64encode(c).decode()} for n, c in contents.items()]})
        res = api.call("PUT", "/api/pipelines/embed", body={
            "source_type": "document", "skip_validation": bool(spec.get("skipValidation", False)),
            "data": [{"source_name": d["name"], "tags": d.get("tags") or [], "metadata": d.get("metadata") or {}} for d in docs]})
    except ApiError as e:
        if e.status in (400, 422):
            _fail(patch, e)
        raise kopf.TemporaryError(str(e), delay=RETRY * 3)
    _status(patch, "Submitted", "pipeline dispatched to celery", hash=h, response=json.dumps(res)[:1500])


# ---------------------------------------------------------------------------- handler registration for resource kinds
def _register():
    for plural in RESOURCE_KINDS:
        def make(p):
            def on_change(**kw):
                return reconcile_resource(p, **kw)

            def on_delete(**kw):
                return delete_resource(p, **kw)
            on_change.__name__, on_delete.__name__ = f"reconcile_{p}", f"delete_{p}"
            return on_change, on_delete
        chg, dele = make(plural)
        kopf.on.create(GROUP, VERSION, plural, id=f"reconcile-{plural}")(chg)
        kopf.on.update(GROUP, VERSION, plural, id=f"reconcile-{plural}")(chg)
        kopf.on.resume(GROUP, VERSION, plural, id=f"reconcile-{plural}")(chg)
        kopf.on.delete(GROUP, VERSION, plural, id=f"delete-{plural}")(dele)


_register()
