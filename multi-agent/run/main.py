from catalog import element_registry
from session.repository.mongo_session_repository import MongoSessionRepository
from blueprints.loader.yaml_blueprint_loader import YAMLBlueprintLoader
from session.workflow_session_factory import WorkflowSessionFactory
from session.user_session_manager import UserSessionManager
from session.session_executor import SessionExecutor
from blueprints.service import BlueprintService
from blueprints.repository.mongo_blueprint_repository import MongoBlueprintRepository
from resources.service import ResourcesService
from resources.registry import ResourcesRegistry
from resources.repository.mongo_repository import MongoResourceRepository
from blueprints.resolver import BlueprintResolver
from core.app_container import AppContainer
from typing import Iterator, Any, Dict, List
from config.app_config import AppConfig
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.console import Console

console = Console()


def make_layout(buffers: Dict[str, str], logs: List[str]) -> Layout:
    layout = Layout()

    # Top pane for logs
    layout.split_column(
        Layout(name="logs", size=len(logs) + 2),
        Layout(name="agents", ratio=1),
    )
    layout["logs"].update(Panel("\n".join(logs), title="Agents Stream"))

    # Bottom pane: one panel per agent, in order seen
    agent_panels = []
    for node, text in buffers.items():
        agent_panels.append(Panel(text or "[waiting…]", title=node, expand=True))
    # split row into as many columns as there are agents
    layout["agents"].split_row(*agent_panels)
    return layout


def stream_with_rich(
        stream: Iterator[Any],
        initial_logs: List[str] = None,
):
    logs = initial_logs[:] if initial_logs else []
    buffers: Dict[str, str] = {}

    with Live(make_layout(buffers, logs), console=console, refresh_per_second=10) as live:
        for raw in stream:
            # your filtering logic
            if raw[0] != "custom":
                continue
            chunk = raw[1]
            if chunk.get("type") != "llm_token":
                continue

            node = chunk.get("node", "unknown")
            token = chunk.get("chunk", "")

            buffers.setdefault(node, "")
            buffers[node] += token

            # update the layout in-place
            live.update(make_layout(buffers, logs))


def setup_components():
    # auto‐discover all your node/tool/llm factories
    element_registry.auto_discover()
    # factory that builds fresh WorkflowSession
    session_factory = WorkflowSessionFactory(
        element_registry=element_registry,
        engine_name="langgraph"
    )

    # repository that stores / loads sessions from disk
    repository = MongoSessionRepository(session_factory=session_factory)

    # manager + executor
    manager = UserSessionManager(repository, session_factory)
    executor = SessionExecutor(manager, repository)

    return manager, executor


def main_new_session():
    manager, executor = setup_components()

    blueprint_loader = YAMLBlueprintLoader()
    spec = blueprint_loader.load("run/test_2_agents_slack_docs_merger.yml")

    session = manager.create_session(
        user_id="alice",
        blueprint_spec=spec,
        metadata={"experiment": "test-v1"}
    )

    run_id = session.run_context.run_id
    print(f"Started run: {run_id}")

    # manager, executor = setup_components()
    # — run it to completion —

    stream = executor.stream(
        session_or_id=session,
        # inputs={"user_prompt": "what is the tm command and tell me from where do you get your info about it?"},
        inputs={"user_prompt": "how to install AIM on CNA?"},
        stream_mode=["custom"]
    )
    stream_with_rich(stream)
    # for chunk in stream:
    #     if "custom" == chunk[0]:
    #         chunk = chunk[1]
    #         if chunk["type"] =
    #
    #         = "llm_token" and \
    #                 (chunk["node"] == "slack_agent_node" or chunk["node"] == "agent_merger_node"):
    #             print(chunk["chunk"], end="", flush=True)


def main_resume_session(run_id: str):
    manager, executor = setup_components()

    # — resume an existing session —
    stream = executor.stream(
        session_or_id=run_id,
        inputs={"user_prompt": "what is the install command in AIM?"},
        stream_mode=["custom"]
    )
    stream_with_rich(stream)


def save_resources(app):
    llm_rid = app.resources_service.create(user_id="alice",
                                           category="llms",
                                           type="openai",
                                           name="openai_llm",
                                           config={
                                               "type": "openai",
                                               "model_name": "gemini-2.0-flash",
                                               "api_key": "AIzaSyBwuQtKPtwKILBulq_YW16RKjMAVx4gbKQ",
                                               "base_url": "https://generativelanguage.googleapis.com/v1beta/openai"
                                           }).rid

    mcp_rid = app.resources_service.create(user_id="alice",
                                           category="providers",
                                           type="mcp_server",
                                           name="My mcp server Node",
                                           config={
                                               "type": "mcp_server",
                                               "sse_endpoint": "http://localhost:8004"
                                           }).rid

    tool_rid = app.resources_service.create(user_id="alice",
                                            category="tools",
                                            type="mcp_proxy",
                                            name="My mcp addition tool",
                                            config={
                                                "type": "mcp_proxy",
                                                "tool_name": "addition",
                                                "provider": f"$ref:{mcp_rid}"
                                            }).rid

    app.resources_service.create(user_id="alice",
                                 category="nodes",
                                 type="custom_agent_node",
                                 name="My Agent Node",
                                 config={
                                     "type": "custom_agent_node",
                                     "llm": f"$ref:{llm_rid}",
                                     "tools": [f"$ref:{tool_rid}"],
                                     "system_message": "You are a smart assistant …"})


def run_test_new_version(app, blueprint_id):
    session = app.session_service.create(user_id="alice", blueprint_id=blueprint_id)
    print(f"Created session with id: {session.run_context.run_id}")
    print(app.session_service.execute(session_id=session.run_context.run_id,
                                      inputs={"user_prompt": "what is latest issues in GENIE project?"},
                                      stream=False,
                                      scope="public"))


from graph.graph_plan import GraphPlan
from dataclasses import dataclass, asdict
import json

if __name__ == "__main__":
    config = AppConfig.get_instance()
    app = AppContainer(config)

    blueprint_loader = YAMLBlueprintLoader()
    # raw = blueprint_loader.load("run/branch_router_demo.yml")
    # raw = blueprint_loader.load("run/boolean_router_demo.yml")
    raw = blueprint_loader.load("run/blueprint_mcp_agent.yml")
    # raw = blueprint_loader.load("run/blueprint_SDJ.yml")
    blueprint_id = app.blueprint_service.save_draft(user_id="alice", draft_dict=raw)
    blueprint_spec = app.blueprint_service.load_resolved(blueprint_id=blueprint_id)
    run_test_new_version(app, blueprint_id=blueprint_id)

    # Use the separate services - build with graph service, validate with validation service
    # plan = app.graph_service.build_plan(blueprint_spec)
    # result, suggestions = app.graph_validation_service.validate_and_suggest(plan)

    # plan.pretty_print()
    # Alternative methods available:
    # result = app.graph_validation_service.validate_channels(plan)
    # result = app.graph_validation_service.validate_all(plan)
    # print(result)
    # print(result.model_dump_json())
    # print()
    # for fix in suggestions:
    #     print(fix.model_dump_json())
    # save_resources(app)

    # run_test_new_version(app)

    # app.blueprint_service.delete(blueprint_id="2af1b9b2900284ed79192e4ebbf8a05cf")
    # app.resources_service.delete(rid="af1b9b2900284ed79192e4ebbf8a05cf")
    # app.resources_service.delete(rid="49f4170dd7da45289a500e43c6a7f8b5")
