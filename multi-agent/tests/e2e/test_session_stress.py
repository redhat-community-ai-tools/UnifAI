"""
End-to-End Stress Test for session create + run under load.

Default path is UI-aligned submit + status poll:

  1. POST /sessions/user.session.submit  → HTTP 202 (Temporal starts in background)
  2. Poll GET /sessions/session.status.get until COMPLETED | FAILED | CANCELLED
  3. Assert final status == COMPLETED

Switch to blocking/streaming execute with --stress-exec-mode=execute
(and optional --use-streaming).

Run with:
    pytest tests/e2e/test_session_stress_submit.py::TestSessionStressSubmit::test_concurrent_session_creation_and_execution \
        -v -s -o addopts= --import-mode=importlib \
        --blueprint-id=<uuid> --stress-sessions=1 --stress-concurrent=1 \
        --input-text="your question"

    # Execute path (optional streaming)
    ... --stress-exec-mode=execute
    ... --stress-exec-mode=execute --use-streaming

Ramp load (start at 1 concurrent, add 1 every 30s, up to 5):
    ... --stress-sessions=20 --stress-concurrent=5 \
        --stress-ramp-start=1 --stress-ramp-step=1 --stress-ramp-interval=30
"""

import os
import pytest
import requests
import time
import json
import yaml
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from enum import Enum
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass, field
import threading
from collections import defaultdict


# =============================================================================
# TEST CONFIGURATION
# =============================================================================

class LLMType(str, Enum):
    GOOGLE_GENAI = "google_genai"
    OPENAI = "openai"


@dataclass
class StressTestConfig:
    """Configuration for stress test parameters."""
    # API Configuration
    # base_url: str = "http://localhost:8002"
    #base_url: str = "http://unifai-multiagent-be-tag-ai--pipeline.apps.stc-ai-e1-pp.imap.p1.openshiftapps.com"
    base_url: str = "https://unifai-ui-tag-ai--playground.apps.stc-ai-e1-pp.imap.p1.openshiftapps.com"
    api_prefix: str = "/api2"
    # Set False only for clusters with self-signed certificates (--stress-insecure).
    verify_ssl: bool = True
    
    # User Configuration
    #user_id: str = "stress_test_user"
    user_id: str = "sfiresht"
    # Blueprint Configuration
    blueprint_path: Optional[str] = None  # Path to YAML blueprint file
    # Existing online blueprint ID — skip create/delete when set
    blueprint_id: Optional[str] = None
    input_text: str = "What is 2+2?"  # Input text for execution

    # -------------------------------------------------------------------------
    # LLM Configuration (edit here — don't pass CLI flags for these)
    # By default the test creates a temporary catalog LLM from llm_* below
    # and wires it as $ref:<rid>. Override with --llm-ref to reuse an existing one.
    # -------------------------------------------------------------------------
    create_llm: bool = True
    llm_ref: Optional[str] = None  # set / pass --llm-ref to skip create
    llm_api_key: Optional[str] = None  # from STRESS_LLM_API_KEY / --llm-api-key
    llm_type: LLMType = LLMType.GOOGLE_GENAI
    llm_model: str = "gemini-2.5-flash"
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    llm_name: str = "stress_test_llm"
    
    # Execution Configuration
    # "submit" = UI path (submit + status poll); "execute" = user.session.execute
    exec_mode: str = "submit"
    use_streaming: bool = False  # only used when exec_mode == "execute"
    
    # Load Configuration
    num_sessions: int = 20  # Total sessions to create
    concurrent_create: int = 5  # Concurrent session creations
    concurrent_execute: int = 10  # Max in-flight run workers at peak
    
    # Ramp-up: when ramp_interval > 0, start at ramp_start in-flight and
    # increase by ramp_step every ramp_interval seconds until concurrent_execute.
    # ramp_interval <= 0 disables ramp (run up to concurrent_execute immediately).
    ramp_start: int = 1
    ramp_step: int = 1
    ramp_interval: float = 0.0
    
    # Timing Configuration
    creation_timeout: float = 30.0  # Per session creation
    execution_timeout: float = 1800.0  # Max wait for one session to finish
    total_timeout: float = 3600.0  # Total test timeout
    poll_interval: float = 5.0  # Seconds between session.status.get polls (submit mode)
    terminal_statuses: Tuple[str, ...] = ("COMPLETED", "FAILED", "CANCELLED")
    
    # Retry Configuration
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Verification Configuration
    verify_state: bool = True
    verify_status: bool = True

    # Cleanup: when False, leave sessions (chats) and created blueprints in place
    cleanup_sessions: bool = True


@dataclass
class SessionMetrics:
    """Metrics collected during stress test."""
    # Creation Metrics
    created_sessions: int = 0
    failed_creates: int = 0
    create_times: List[float] = field(default_factory=list)
    
    # Execution Metrics
    executed_sessions: int = 0
    failed_executions: int = 0
    execution_times: List[float] = field(default_factory=list)
    
    # Error Tracking
    errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Timing
    total_start_time: float = 0
    total_end_time: float = 0
    
    def add_create_success(self, duration: float):
        """Record successful session creation."""
        self.created_sessions += 1
        self.create_times.append(duration)
    
    def add_create_failure(self, error_type: str):
        """Record failed session creation."""
        self.failed_creates += 1
        self.errors[f"create_{error_type}"] += 1
    
    def add_execute_success(self, duration: float):
        """Record successful session execution."""
        self.executed_sessions += 1
        self.execution_times.append(duration)
    
    def add_execute_failure(self, error_type: str):
        """Record failed session execution."""
        self.failed_executions += 1
        self.errors[f"execute_{error_type}"] += 1
    
    def get_summary(self) -> Dict:
        """Get summary statistics."""
        total_time = self.total_end_time - self.total_start_time
        
        return {
            "total_time": total_time,
            "creation": {
                "successful": self.created_sessions,
                "failed": self.failed_creates,
                "avg_time": sum(self.create_times) / len(self.create_times) if self.create_times else 0,
                "min_time": min(self.create_times) if self.create_times else 0,
                "max_time": max(self.create_times) if self.create_times else 0,
                "throughput": self.created_sessions / total_time if total_time > 0 else 0,
            },
            "execution": {
                "successful": self.executed_sessions,
                "failed": self.failed_executions,
                "avg_time": sum(self.execution_times) / len(self.execution_times) if self.execution_times else 0,
                "min_time": min(self.execution_times) if self.execution_times else 0,
                "max_time": max(self.execution_times) if self.execution_times else 0,
                "throughput": self.executed_sessions / total_time if total_time > 0 else 0,
            },
            "errors": dict(self.errors)
        }


# =============================================================================
# API CLIENT
# =============================================================================

class SessionAPIClient:
    """Client for interacting with Session API."""
    
    def __init__(self, config: StressTestConfig):
        self.config = config
        self.base_url = f"{config.base_url}{config.api_prefix}"
        self.session = requests.Session()
        self.session.verify = config.verify_ssl
        self.session.headers.update({
            "X-Authenticated-User": self.config.user_id
        })
    
    def create_blueprint(self, blueprint_dict: Dict) -> str:
        """Create a blueprint and return its ID."""
        url = f"{self.base_url}/blueprints/blueprint.save"
        
        # Convert dict to YAML string (API expects raw YAML/JSON string)
        blueprint_yaml = yaml.dump(blueprint_dict, default_flow_style=False, sort_keys=False)
        
        payload = {
            "blueprintRaw": blueprint_yaml,
            "userId": self.config.user_id
        }
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        return result.get("blueprint_id") or result.get("blueprintId")
    
    def create_session(self, blueprint_id: str, metadata: Optional[Dict] = None) -> str:
        """Create a session and return session ID."""
        url = f"{self.base_url}/sessions/user.session.create"
        
        payload = {
            "blueprintId": blueprint_id,
            "userId": self.config.user_id
        }
        
        # Only include metadata if provided (API will use default SessionMeta() if not provided)
        if metadata:
            payload["metadata"] = metadata
        
        response = self.session.post(
            url, 
            json=payload,
            timeout=self.config.creation_timeout
        )
        response.raise_for_status()
        
        # Response is just the session_id string
        session_id = response.json()
        return session_id
    
    def submit_session(self, session_id: str, inputs: Dict) -> Dict:
        """
        Fire-and-forget submit (UI path). Returns immediately with HTTP 202.
        """
        url = f"{self.base_url}/sessions/user.session.submit"

        payload = {
            "sessionId": session_id,
            "inputs": inputs,
            "scope": "public",
        }

        response = self.session.post(
            url,
            json=payload,
            timeout=self.config.creation_timeout,
        )
        if response.status_code >= 400:
            detail = response.text[:500]
            raise requests.exceptions.HTTPError(
                f"{response.status_code} submitting session: {detail}",
                response=response,
            )
        # Expect 202 Accepted
        return response.json()

    def execute_session(self, session_id: str, inputs: Dict) -> Dict:
        """Blocking execute (non-streaming)."""
        url = f"{self.base_url}/sessions/user.session.execute"

        payload = {
            "sessionId": session_id,
            "inputs": inputs,
            "stream": False,
            "scope": "public",
        }

        response = self.session.post(
            url,
            json=payload,
            timeout=self.config.execution_timeout,
        )
        response.raise_for_status()
        return response.json()

    def execute_session_streaming(self, session_id: str, inputs: Dict) -> Dict:
        """Execute with streaming; consume chunks until the connection closes."""
        url = f"{self.base_url}/sessions/user.session.execute"

        payload = {
            "sessionId": session_id,
            "inputs": inputs,
            "stream": True,
            "streamMode": ["custom"],
            "scope": "public",
        }

        response = self.session.post(
            url,
            json=payload,
            stream=True,
        )
        response.raise_for_status()

        chunk_count = 0
        try:
            for line in response.iter_lines():
                if line:
                    chunk_count += 1
        finally:
            response.close()

        return {"status": "completed", "chunks_received": chunk_count}

    def run_session(self, session_id: str, inputs: Dict) -> Dict:
        """Run a session using config.exec_mode (submit | execute)."""
        if self.config.exec_mode == "execute":
            if self.config.use_streaming:
                return self.execute_session_streaming(session_id, inputs)
            return self.execute_session(session_id, inputs)
        return self.submit_and_wait(session_id, inputs)

    def get_session_status(self, session_id: str) -> str:
        """Get session status string (e.g. RUNNING, COMPLETED, FAILED)."""
        url = f"{self.base_url}/sessions/session.status.get"
        params = {"sessionId": session_id}

        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()

        status = response.json()
        # jsonify(str) → JSON string; tolerate {"status": "..."} just in case
        if isinstance(status, dict):
            return str(status.get("status") or status.get("state") or status)
        return str(status)

    def submit_and_wait(self, session_id: str, inputs: Dict) -> Dict:
        """
        Submit session then poll status until terminal or timeout.

        Returns dict with sessionId, workflowId (if any), final status, and poll count.
        Raises TimeoutError / RuntimeError on failure.
        """
        submit_result = self.submit_session(session_id, inputs)
        workflow_id = submit_result.get("workflowId") or submit_result.get("workflow_id")
        short_id = session_id[:8]
        print(
            f"    📤 Submitted {short_id}... "
            f"(workflowId={workflow_id or 'n/a'}) — polling every "
            f"{self.config.poll_interval}s",
            flush=True,
        )

        deadline = time.time() + self.config.execution_timeout
        started = time.time()
        polls = 0
        last_status = "UNKNOWN"

        while time.time() < deadline:
            polls += 1
            last_status = self.get_session_status(session_id)
            elapsed = time.time() - started
            print(
                f"    🔄 poll #{polls} {short_id}... status={last_status} "
                f"elapsed={elapsed:.0f}s",
                flush=True,
            )
            if last_status in self.config.terminal_statuses:
                result = {
                    "sessionId": session_id,
                    "workflowId": workflow_id,
                    "status": last_status,
                    "polls": polls,
                }
                if last_status != "COMPLETED":
                    raise RuntimeError(
                        f"Session {short_id}... ended with status={last_status} "
                        f"after {polls} polls"
                    )
                return result

            time.sleep(self.config.poll_interval)

        raise TimeoutError(
            f"Session {short_id}... still {last_status} after "
            f"{self.config.execution_timeout:.0f}s ({polls} polls)"
        )
    
    def get_session_state(self, session_id: str) -> Dict:
        """Get session state."""
        url = f"{self.base_url}/sessions/session.state.get"
        params = {"sessionId": session_id}
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
    def create_llm_resource(
        self,
        *,
        name: str,
        llm_type: Union[str, LLMType],
        model_name: str,
        api_key: str,
        base_url: Optional[str] = None,
    ) -> str:
        """Create a catalog LLM via /resources/resource.save and return its rid."""
        url = f"{self.base_url}/resources/resource.save"
        raw_type = llm_type.value if isinstance(llm_type, LLMType) else str(llm_type).strip().lower()
        try:
            llm_type = LLMType(raw_type)
        except ValueError as exc:
            raise ValueError(
                f"Unsupported llm_type '{raw_type}'. Use "
                f"'{LLMType.GOOGLE_GENAI.value}' or '{LLMType.OPENAI.value}'."
            ) from exc

        if llm_type == LLMType.GOOGLE_GENAI:
            config = {
                "type": LLMType.GOOGLE_GENAI.value,
                "model_name": model_name,
                "api_key": api_key,
            }
        elif llm_type == LLMType.OPENAI:
            if not base_url:
                raise ValueError(
                    "base_url is required for openai llm_type "
                    "(set StressTestConfig.llm_base_url or pass --llm-base-url)."
                )
            config = {
                "type": LLMType.OPENAI.value,
                "model_name": model_name,
                "api_key": api_key,
                "base_url": base_url,
                "verify_ssl": True,
            }

        payload = {
            "category": "llms",
            "type": llm_type.value,
            "name": name,
            "config": config,
            "userId": self.config.user_id,
        }

        response = self.session.post(url, json=payload, timeout=self.config.creation_timeout)
        if response.status_code >= 400:
            detail = response.text[:500]
            raise requests.exceptions.HTTPError(
                f"{response.status_code} creating LLM resource: {detail}",
                response=response,
            )
        result = response.json()
        rid = result.get("rid")
        if not rid:
            raise RuntimeError(f"resource.save returned no rid: {result}")
        return rid

    def delete_resource(self, resource_id: str) -> bool:
        """Delete a catalog resource by id."""
        url = f"{self.base_url}/resources/resource.delete"
        params = {"resourceId": resource_id}

        try:
            response = self.session.delete(url, params=params)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"  ⚠️  Warning: Failed to delete resource {resource_id[:8]}...: {e}")
            return False

    def delete_blueprint(self, blueprint_id: str) -> bool:
        """Delete a blueprint."""
        url = f"{self.base_url}/blueprints/remove.blueprint"
        params = {"blueprintId": blueprint_id}
        
        try:
            response = self.session.delete(url, params=params)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"  ⚠️  Warning: Failed to delete blueprint {blueprint_id[:8]}...: {e}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        url = f"{self.base_url}/sessions/session.delete"
        params = {"sessionId": session_id}
        
        try:
            response = self.session.delete(url, params=params)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"  ⚠️  Warning: Failed to delete session {session_id[:8]}...: {e}")
            return False


# =============================================================================
# SAMPLE BLUEPRINT
# =============================================================================

def _normalize_llm_ref(llm_ref: str) -> str:
    """Ensure catalog LLM refs use the $ref: prefix Temporal mini-blueprints require."""
    ref = (llm_ref or "").strip()
    if not ref:
        raise ValueError("llm_ref must not be empty")
    if not ref.startswith("$ref:"):
        ref = f"$ref:{ref}"
    return ref


def resolve_blueprint_id(
    api_client: "SessionAPIClient",
    stress_config: StressTestConfig,
    blueprint_dict: Optional[Dict],
) -> Tuple[str, bool]:
    """
    Resolve which blueprint to use.

    Returns:
        (blueprint_id, created_by_test) — when created_by_test is False, do not delete it.
    """
    if stress_config.blueprint_id:
        blueprint_id = stress_config.blueprint_id.strip()
        print(f"📄 Using existing online blueprint: {blueprint_id}")
        return blueprint_id, False

    if blueprint_dict is None:
        raise ValueError(
            "No blueprint available. Pass --blueprint-id, --blueprint-path, "
            "or use the default stress blueprint."
        )

    blueprint_id = api_client.create_blueprint(blueprint_dict)
    print(f"✅ Blueprint created: {blueprint_id}")
    return blueprint_id, True


def get_stress_test_blueprint(llm_ref: str) -> Dict:
    """
    Returns a simple blueprint for stress testing.

    Uses a catalog LLM via `$ref:<rid>` (no inline LLM / api_key). This matches
    playground Temporal execution, which only packs `$ref:` deps into worker
    mini-blueprints.
    """
    catalog_llm = _normalize_llm_ref(llm_ref)
    return {
        "description": "A simple agent pipeline for stress testing session creation and execution",
        "name": "Stress Test Blueprint",
        
        # ----------------------------
        # Providers
        # ----------------------------
        "providers": [],
        
        # ----------------------------
        # LLM Definitions (catalog $ref only — no inline credentials)
        # ----------------------------
        "llms": [],
        
        # ----------------------------
        # Retriever
        # ----------------------------
        "retrievers": [],
        
        # ----------------------------
        # Tool Stubs
        # ----------------------------
        "tools": [],
        
        # ----------------------------
        # Conditions
        # ----------------------------
        "conditions": [],
        
        # ----------------------------
        # Nodes
        # ----------------------------
        "nodes": [
            {
                "rid": "user_question_node_rid",
                "name": "User Question Node",
                "type": "user_question_node",
                "config": {
                    "type": "user_question_node"
                }
            },
            {
                "rid": "simple_agent_rid",
                "name": "Simple Agent",
                "type": "custom_agent_node",
                "config": {
                    "type": "custom_agent_node",
                    "llm": catalog_llm,
                    "system_message": "You are a helpful assistant. Answer the user's question directly and concisely in one or two sentences."
                }
            },
            {
                "rid": "final_answer_node_rid",
                "name": "Final Answer Node",
                "type": "final_answer_node",
                "config": {
                    "type": "final_answer_node"
                }
            }
        ],
        
        # ----------------------------
        # Plan Steps
        # ----------------------------
        "plan": [
            {
                "uid": "user_input",
                "node": "user_question_node_rid",
                "meta": {
                    "display_name": "User Question",
                    "description": "The user inputs a question or request."
                }
            },
            {
                "uid": "agent",
                "after": "user_input",
                "node": "simple_agent_rid",
                "meta": {
                    "display_name": "Simple Agent",
                    "description": "Process the user's question and generate an answer."
                }
            },
            {
                "uid": "finalize",
                "after": "agent",
                "node": "final_answer_node_rid",
                "meta": {
                    "display_name": "Final Answer",
                    "description": "Provide the final answer to the user."
                }
            }
        ]
    }


# =============================================================================
# STRESS TEST HELPERS
# =============================================================================

class StressTestRunner:
    """Orchestrates stress test execution."""
    
    def __init__(self, config: StressTestConfig, client: SessionAPIClient):
        self.config = config
        self.client = client
        self.metrics = SessionMetrics()
        self.lock = threading.Lock()
    
    def create_session_with_metrics(self, blueprint_id: str, index: int) -> Tuple[Optional[str], bool, float, Optional[str]]:
        """
        Create a session and track metrics.
        
        Returns: (session_id, success, duration, error_message)
        """
        start_time = time.time()
        session_id = None
        success = False
        error_msg = None
        
        try:
            # Don't send metadata - let it default to SessionMeta()
            # API has issues converting dict to SessionMeta object
            session_id = self.client.create_session(
                blueprint_id=blueprint_id,
                metadata=None
            )
            success = True
            duration = time.time() - start_time
            
            with self.lock:
                self.metrics.add_create_success(duration)
            
            return session_id, success, duration, None
            
        except requests.exceptions.Timeout:
            duration = time.time() - start_time
            error_msg = "Timeout"
            with self.lock:
                self.metrics.add_create_failure("timeout")
            return None, False, duration, error_msg
            
        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            error_type = type(e).__name__
            # Try to get response body for more details
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg = f"{error_type}: {error_detail.get('error', str(e))}"
                except:
                    error_msg = f"{error_type}: {e.response.text[:200]}"
            with self.lock:
                self.metrics.add_create_failure(error_type)
            return None, False, duration, error_msg
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Unknown error: {str(e)}"
            with self.lock:
                self.metrics.add_create_failure("unknown")
            return None, False, duration, error_msg
    
    def execute_session_with_metrics(
        self, 
        session_id: str, 
        inputs: Dict,
        index: int
    ) -> Tuple[Optional[Dict], bool, float, Optional[str]]:
        """
        Run a session via config.exec_mode and track metrics.

        Returns: (result, success, duration, error_message)
        """
        start_time = time.time()
        result = None
        success = False
        error_msg = None
        
        try:
            result = self.client.run_session(session_id, inputs)
            
            success = True
            duration = time.time() - start_time
            
            with self.lock:
                self.metrics.add_execute_success(duration)
            
            return result, success, duration, None

        except TimeoutError as e:
            duration = time.time() - start_time
            error_msg = str(e)
            with self.lock:
                self.metrics.add_execute_failure("timeout")
            return None, False, duration, error_msg

        except RuntimeError as e:
            duration = time.time() - start_time
            error_msg = str(e)
            with self.lock:
                self.metrics.add_execute_failure("terminal_not_completed")
            return None, False, duration, error_msg
            
        except requests.exceptions.Timeout:
            duration = time.time() - start_time
            error_msg = "Timeout"
            with self.lock:
                self.metrics.add_execute_failure("timeout")
            return None, False, duration, error_msg
            
        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            error_type = type(e).__name__
            # Try to get response body for more details
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg = f"{error_type}: {error_detail.get('error', str(e))}"
                except:
                    error_msg = f"{error_type}: {e.response.text[:200]}"
            with self.lock:
                self.metrics.add_execute_failure(error_type)
            return None, False, duration, error_msg
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Unknown error: {str(e)}"
            with self.lock:
                self.metrics.add_execute_failure("unknown")
            return None, False, duration, error_msg
    
    def run_concurrent_creation(self, blueprint_id: str) -> List[str]:
        """
        Create multiple sessions concurrently.
        
        Returns: List of successfully created session IDs
        """
        session_ids = []
        
        print(f"\n🚀 Creating {self.config.num_sessions} sessions with concurrency={self.config.concurrent_create}")
        
        with ThreadPoolExecutor(max_workers=self.config.concurrent_create) as executor:
            futures = {
                executor.submit(self.create_session_with_metrics, blueprint_id, i): i
                for i in range(self.config.num_sessions)
            }
            
            for future in as_completed(futures):
                index = futures[future]
                try:
                    session_id, success, duration, error_msg = future.result(timeout=self.config.creation_timeout)
                    if success and session_id:
                        session_ids.append(session_id)
                        print(f"  ✅ Session {index + 1}/{self.config.num_sessions} created in {duration:.2f}s: {session_id[:8]}...")
                    else:
                        print(f"  ❌ Session {index + 1}/{self.config.num_sessions} failed: {error_msg}")
                except Exception as e:
                    print(f"  ❌ Session {index + 1}/{self.config.num_sessions} error: {e}")
        
        return session_ids
    
    def _record_execution_future(
        self,
        future,
        index: int,
        session_id: str,
        total: int,
        results: List[Dict],
        future_timeout: float,
    ) -> None:
        """Collect one completed run future and print outcome."""
        try:
            result, success, duration, error_msg = future.result(timeout=future_timeout)
            if success and result:
                results.append(result)
                status = result.get("status", "?")
                if "polls" in result:
                    detail = f"{status} ({result.get('polls')} polls)"
                elif "chunks_received" in result:
                    detail = f"{status} ({result.get('chunks_received')} chunks)"
                else:
                    detail = str(status)
                print(
                    f"  ✅ Session {index + 1}/{total} "
                    f"{session_id[:8]}... {detail} in {duration:.2f}s",
                    flush=True,
                )
            else:
                print(
                    f"  ❌ Session {index + 1}/{total} "
                    f"{session_id[:8]}... failed: {error_msg}",
                    flush=True,
                )
        except Exception as e:
            print(
                f"  ❌ Session {index + 1}/{total} "
                f"{session_id[:8]}... error: {e}",
                flush=True,
            )

    def run_concurrent_execution(self, session_ids: List[str], inputs: Dict) -> List[Dict]:
        """
        Run sessions (submit or execute) with optional concurrency ramp-up.

        Returns: List of successful execution results
        """
        results: List[Dict] = []
        total = len(session_ids)
        max_concurrent = max(1, self.config.concurrent_execute)
        mode_label = (
            f"execute{'+stream' if self.config.use_streaming else ''}"
            if self.config.exec_mode == "execute"
            else "submit+poll"
        )
        timing_detail = (
            f"poll every {self.config.poll_interval}s, "
            f"timeout {self.config.execution_timeout:.0f}s"
            if self.config.exec_mode == "submit"
            else f"timeout {self.config.execution_timeout:.0f}s"
        )
        ramp_enabled = self.config.ramp_interval > 0
        if ramp_enabled:
            current_limit = max(1, min(self.config.ramp_start, max_concurrent))
            ramp_step = max(1, self.config.ramp_step)
            print(
                f"\n⚡ Running {total} sessions ({mode_label}) with RAMP-UP: "
                f"start={current_limit}, step=+{ramp_step} every "
                f"{self.config.ramp_interval:.0f}s, max={max_concurrent} "
                f"({timing_detail})",
                flush=True,
            )
        else:
            current_limit = max_concurrent
            print(
                f"\n⚡ Running {total} sessions ({mode_label}) with concurrency="
                f"{max_concurrent} (no ramp; {timing_detail})",
                flush=True,
            )

        future_timeout = self.config.execution_timeout + 60.0
        pending = list(enumerate(session_ids))
        next_idx = 0
        active: Dict = {}
        last_ramp_at = time.time()

        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            def _fill_slots():
                nonlocal next_idx
                while next_idx < total and len(active) < current_limit:
                    i, session_id = pending[next_idx]
                    next_idx += 1
                    fut = executor.submit(
                        self.execute_session_with_metrics, session_id, inputs, i
                    )
                    active[fut] = (i, session_id)
                    print(
                        f"    🚀 started in-flight {len(active)}/{current_limit} "
                        f"(queued remaining {total - next_idx}): "
                        f"session {i + 1} {session_id[:8]}...",
                        flush=True,
                    )

            _fill_slots()

            while active or next_idx < total:
                if (
                    ramp_enabled
                    and current_limit < max_concurrent
                    and (time.time() - last_ramp_at) >= self.config.ramp_interval
                ):
                    current_limit = min(max_concurrent, current_limit + ramp_step)
                    last_ramp_at = time.time()
                    print(
                        f"  📈 Ramped concurrency → {current_limit}/{max_concurrent}",
                        flush=True,
                    )
                    _fill_slots()

                if not active:
                    _fill_slots()
                    if not active:
                        break

                done, _ = wait(
                    list(active.keys()),
                    timeout=1.0,
                    return_when=FIRST_COMPLETED,
                )
                for fut in done:
                    index, session_id = active.pop(fut)
                    self._record_execution_future(
                        fut, index, session_id, total, results, future_timeout
                    )
                    _fill_slots()

        return results
    
    def print_metrics_summary(self):
        """Print formatted metrics summary."""
        summary = self.metrics.get_summary()
        
        print("\n" + "=" * 80)
        print("📊 STRESS TEST METRICS SUMMARY")
        print("=" * 80)
        
        print(f"\n⏱️  Total Time: {summary['total_time']:.2f}s")
        
        print("\n📝 Session Creation:")
        print(f"  • Successful: {summary['creation']['successful']}")
        print(f"  • Failed: {summary['creation']['failed']}")
        print(f"  • Avg Time: {summary['creation']['avg_time']:.3f}s")
        print(f"  • Min Time: {summary['creation']['min_time']:.3f}s")
        print(f"  • Max Time: {summary['creation']['max_time']:.3f}s")
        print(f"  • Throughput: {summary['creation']['throughput']:.2f} sessions/sec")
        
        print("\n⚡ Session Execution:")
        print(f"  • Successful: {summary['execution']['successful']}")
        print(f"  • Failed: {summary['execution']['failed']}")
        print(f"  • Avg Time: {summary['execution']['avg_time']:.3f}s")
        print(f"  • Min Time: {summary['execution']['min_time']:.3f}s")
        print(f"  • Max Time: {summary['execution']['max_time']:.3f}s")
        print(f"  • Throughput: {summary['execution']['throughput']:.2f} executions/sec")
        
        if summary['errors']:
            print("\n❌ Errors:")
            for error_type, count in summary['errors'].items():
                print(f"  • {error_type}: {count}")
        
        print("\n" + "=" * 80)


# =============================================================================
# PYTEST FIXTURES
# =============================================================================

@pytest.fixture
def stress_config(request):
    """Configuration fixture with CLI / env overrides."""
    config = StressTestConfig()
    
    # Allow CLI overrides
    if hasattr(request.config.option, 'stress_sessions'):
        config.num_sessions = request.config.option.stress_sessions
    if hasattr(request.config.option, 'stress_concurrent'):
        config.concurrent_execute = request.config.option.stress_concurrent
    if getattr(request.config.option, 'stress_ramp_start', None) is not None:
        config.ramp_start = request.config.option.stress_ramp_start
    if getattr(request.config.option, 'stress_ramp_step', None) is not None:
        config.ramp_step = request.config.option.stress_ramp_step
    if getattr(request.config.option, 'stress_ramp_interval', None) is not None:
        config.ramp_interval = request.config.option.stress_ramp_interval
    if hasattr(request.config.option, 'stress_base_url') and request.config.option.stress_base_url:
        config.base_url = request.config.option.stress_base_url
    if hasattr(request.config.option, 'blueprint_path'):
        config.blueprint_path = request.config.option.blueprint_path
    if getattr(request.config.option, 'blueprint_id', None):
        config.blueprint_id = request.config.option.blueprint_id.strip()
        # Existing online blueprint already has its own LLM wiring
        config.create_llm = False
    if hasattr(request.config.option, 'input_text'):
        config.input_text = request.config.option.input_text
    if getattr(request.config.option, 'stress_exec_mode', None):
        config.exec_mode = request.config.option.stress_exec_mode
    if hasattr(request.config.option, 'use_streaming'):
        config.use_streaming = request.config.option.use_streaming

    # Optional CLI overrides for LLM fields (config defaults are the normal path)
    if getattr(request.config.option, 'llm_type', None):
        raw_llm_type = request.config.option.llm_type.strip().lower()
        try:
            config.llm_type = LLMType(raw_llm_type)
        except ValueError as exc:
            raise pytest.UsageError(
                f"Unsupported --llm-type '{raw_llm_type}'. Use "
                f"'{LLMType.GOOGLE_GENAI.value}' or '{LLMType.OPENAI.value}'."
            ) from exc
    if getattr(request.config.option, 'llm_model', None):
        config.llm_model = request.config.option.llm_model
    if getattr(request.config.option, 'llm_base_url', None):
        config.llm_base_url = request.config.option.llm_base_url
    if getattr(request.config.option, 'llm_name', None):
        config.llm_name = request.config.option.llm_name

    # --llm-ref wins: reuse existing catalog LLM, do not create
    if getattr(request.config.option, 'llm_ref', None):
        config.llm_ref = _normalize_llm_ref(request.config.option.llm_ref)
        config.create_llm = False
    elif getattr(request.config.option, 'create_llm', False):
        config.create_llm = True

    # API key: CLI > STRESS_LLM_API_KEY > LLM_API_KEY
    cli_key = getattr(request.config.option, 'llm_api_key', None)
    config.llm_api_key = (
        cli_key
        or os.environ.get("STRESS_LLM_API_KEY")
        or os.environ.get("LLM_API_KEY")
    )

    if getattr(request.config.option, 'stress_no_cleanup', False):
        config.cleanup_sessions = False
    if getattr(request.config.option, 'stress_insecure', False):
        config.verify_ssl = False
    
    return config


@pytest.fixture
def api_client(stress_config):
    """API client fixture."""
    return SessionAPIClient(stress_config)


@pytest.fixture
def catalog_llm(stress_config, api_client):
    """
    Resolve the catalog LLM `$ref` for the default stress blueprint.

    - `--create-llm`: POST /resources/resource.save, wire `$ref:<rid>`, delete on teardown
    - `--llm-ref`: reuse an existing catalog LLM
    - skipped when `--blueprint-path` or `--blueprint-id` supplies the workflow
    """
    if stress_config.blueprint_path or stress_config.blueprint_id:
        yield None
        return

    created_rid: Optional[str] = None

    if stress_config.create_llm:
        if not stress_config.llm_api_key:
            pytest.fail(
                "LLM create is enabled (StressTestConfig.create_llm=True) but no API key "
                "was found. Set STRESS_LLM_API_KEY / LLM_API_KEY or pass --llm-api-key, "
                "or reuse an existing LLM with --llm-ref."
            )
        unique_name = f"{stress_config.llm_name}_{uuid.uuid4().hex[:8]}"
        print(f"🧠 Creating catalog LLM '{unique_name}' "
              f"(type={stress_config.llm_type}, model={stress_config.llm_model})")
        created_rid = api_client.create_llm_resource(
            name=unique_name,
            llm_type=stress_config.llm_type,
            model_name=stress_config.llm_model,
            api_key=stress_config.llm_api_key,
            base_url=stress_config.llm_base_url,
        )
        llm_ref = _normalize_llm_ref(created_rid)
        stress_config.llm_ref = llm_ref
        print(f"   ✅ Created catalog LLM: {llm_ref}")
    elif stress_config.llm_ref:
        llm_ref = _normalize_llm_ref(stress_config.llm_ref)
        stress_config.llm_ref = llm_ref
        print(f"📄 Using existing catalog LLM: {llm_ref}")
    else:
        pytest.fail(
            "No LLM configured. Set StressTestConfig.create_llm=True with an API key, "
            "or pass --llm-ref <catalog-rid>."
        )

    yield llm_ref

    if created_rid:
        print(f"🧹 Deleting auto-created catalog LLM {created_rid[:8]}...")
        if api_client.delete_resource(created_rid):
            print("  ✅ Catalog LLM deleted")


@pytest.fixture
def test_blueprint(stress_config, catalog_llm) -> Optional[Dict]:
    """Blueprint dict to upload, or None when using --blueprint-id."""
    if stress_config.blueprint_id:
        return None

    if stress_config.blueprint_path:
        from pathlib import Path
        
        blueprint_file = Path(stress_config.blueprint_path)
        if not blueprint_file.exists():
            pytest.skip(f"Blueprint file not found: {stress_config.blueprint_path}")
        
        print(f"📄 Loading blueprint from: {stress_config.blueprint_path}")
        with open(blueprint_file, 'r') as f:
            blueprint = yaml.safe_load(f)
        
        blueprint_name = blueprint.get('name', 'Unknown')
        print(f"   Blueprint: {blueprint_name}")
        return blueprint

    return get_stress_test_blueprint(catalog_llm)


@pytest.fixture
def stress_runner(stress_config, api_client):
    """Stress test runner fixture."""
    return StressTestRunner(stress_config, api_client)


# =============================================================================
# STRESS TESTS
# =============================================================================
# Note: CLI options (--stress-sessions, --stress-concurrent, --stress-base-url) 
# are defined in tests/conftest.py

@pytest.mark.e2e
@pytest.mark.stress
@pytest.mark.session_management
class TestSessionStressSubmit:
    """E2E stress tests; default submit+poll, switchable via --stress-exec-mode."""
    
    def test_concurrent_session_creation_and_execution(
        self,
        stress_config: StressTestConfig,
        api_client: SessionAPIClient,
        test_blueprint: Optional[Dict],
        stress_runner: StressTestRunner
    ):
        """
        Concurrent create + run (submit/poll or execute) until complete.
        """
        blueprint_id = None
        owns_blueprint = False
        session_ids = []
        mode_label = (
            f"execute{'+stream' if stress_config.use_streaming else ''}"
            if stress_config.exec_mode == "execute"
            else "submit + status poll"
        )
        
        try:
            print(f"\n{'=' * 80}")
            print(f"🧪 STARTING E2E SESSION STRESS TEST ({mode_label})")
            print(f"{'=' * 80}")
            print(f"Configuration:")
            print(f"  • Total Sessions: {stress_config.num_sessions}")
            print(f"  • Concurrent Creates: {stress_config.concurrent_create}")
            print(f"  • Max concurrent runs: {stress_config.concurrent_execute}")
            if stress_config.ramp_interval > 0:
                print(
                    f"  • Ramp-up: start={stress_config.ramp_start}, "
                    f"step=+{stress_config.ramp_step} every "
                    f"{stress_config.ramp_interval:.0f}s"
                )
            else:
                print("  • Ramp-up: disabled (immediate full concurrency)")
            print(f"  • Mode: {mode_label}")
            if stress_config.exec_mode == "submit":
                print(f"  • Poll interval: {stress_config.poll_interval}s")
            print(f"  • Per-session timeout: {stress_config.execution_timeout:.0f}s")
            print(f"  • API: {stress_config.base_url}{stress_config.api_prefix}")
            print(f"  • User: {stress_config.user_id}")
            if stress_config.blueprint_id:
                print(f"  • Blueprint ID: {stress_config.blueprint_id}")
            if stress_config.create_llm:
                print(f"  • LLM mode: create ({stress_config.llm_type}/{stress_config.llm_model})")
            if stress_config.llm_ref:
                print(f"  • Catalog LLM: {stress_config.llm_ref}")
            
            stress_runner.metrics.total_start_time = time.time()
            
            # PHASE 1: Blueprint Setup
            print(f"\n{'=' * 80}")
            print("📋 PHASE 1: Blueprint Setup")
            print(f"{'=' * 80}")
            
            blueprint_id, owns_blueprint = resolve_blueprint_id(
                api_client, stress_config, test_blueprint
            )
            
            # PHASE 2: Concurrent Session Creation
            print(f"\n{'=' * 80}")
            print("📋 PHASE 2: Concurrent Session Creation")
            print(f"{'=' * 80}")
            
            session_ids = stress_runner.run_concurrent_creation(blueprint_id)
            
            # Assert creation success
            assert len(session_ids) > 0, "No sessions were created successfully"
            creation_success_rate = len(session_ids) / stress_config.num_sessions
            print(f"\n✅ Created {len(session_ids)}/{stress_config.num_sessions} sessions ({creation_success_rate * 100:.1f}% success)")
            
            # PHASE 3: Run sessions to completion
            print(f"\n{'=' * 80}")
            print(f"📋 PHASE 3: Run Until Complete ({mode_label})")
            print(f"{'=' * 80}")
            
            test_inputs = {
                "user_prompt": stress_config.input_text
            }
            
            results = stress_runner.run_concurrent_execution(session_ids, test_inputs)
            
            # Assert execution success
            assert len(results) > 0, "No sessions completed successfully"
            execution_success_rate = len(results) / len(session_ids)
            print(f"\n✅ Completed {len(results)}/{len(session_ids)} sessions ({execution_success_rate * 100:.1f}% success)")
            
            stress_runner.metrics.total_end_time = time.time()
            
            # PHASE 4: Verification — tolerate partial failure (same bar as execution_success_rate)
            if stress_config.verify_status:
                print(f"\n{'=' * 80}")
                print("📋 PHASE 4: Session Status Verification")
                print(f"{'=' * 80}")
                
                completed_count = 0
                for i, session_id in enumerate(session_ids):
                    try:
                        status = api_client.get_session_status(session_id)
                        print(f"  • Session {i + 1} ({session_id[:8]}...): {status}")
                        if status == "COMPLETED":
                            completed_count += 1
                    except Exception as e:
                        print(f"  • Session {i + 1} ({session_id[:8]}...): Error getting status - {e}")

                completed_rate = completed_count / len(session_ids)
                assert completed_rate >= 0.8, (
                    f"COMPLETED rate too low: {completed_count}/{len(session_ids)} "
                    f"({completed_rate * 100:.1f}%)"
                )
            
            # PHASE 5: Metrics Report
            stress_runner.print_metrics_summary()
            
            # Final Assertions
            assert creation_success_rate >= 0.9, f"Creation success rate too low: {creation_success_rate * 100:.1f}%"
            assert execution_success_rate >= 0.8, f"Execution success rate too low: {execution_success_rate * 100:.1f}%"
            
            print("\n" + "=" * 80)
            print(f"✅ STRESS TEST PASSED ({mode_label})")
            print("=" * 80 + "\n")
            
        finally:
            # CLEANUP PHASE
            print(f"\n{'=' * 80}")
            print("🧹 CLEANUP PHASE")
            print(f"{'=' * 80}")

            if not stress_config.cleanup_sessions:
                print("  ⏭️  --stress-no-cleanup: leaving sessions/chats in place")
                for session_id in session_ids:
                    print(f"     session: {session_id}")
                if blueprint_id:
                    print(f"  ⏭️  Leaving blueprint {blueprint_id[:8]}... in place")
                print("✅ Cleanup skipped\n")
            else:
                # Delete sessions
                if session_ids:
                    print(f"Deleting {len(session_ids)} sessions...")
                    deleted_count = 0
                    for session_id in session_ids:
                        if api_client.delete_session(session_id):
                            deleted_count += 1
                    print(f"  ✅ Deleted {deleted_count}/{len(session_ids)} sessions")

                # Only delete blueprints this test created
                if blueprint_id and owns_blueprint:
                    print(f"Deleting blueprint {blueprint_id[:8]}...")
                    if api_client.delete_blueprint(blueprint_id):
                        print(f"  ✅ Blueprint deleted")
                elif blueprint_id:
                    print(f"  ⏭️  Leaving existing blueprint {blueprint_id[:8]}... in place")

                print("✅ Cleanup complete\n")
    
    def test_rapid_sequential_sessions(
        self,
        stress_config: StressTestConfig,
        api_client: SessionAPIClient,
        test_blueprint: Optional[Dict]
    ):
        """
        Test rapid sequential session creation and execution.
        
        This validates:
        - System handles rapid consecutive operations
        - No resource leaks or blocking
        - Maintains performance consistency
        """
        blueprint_id = None
        owns_blueprint = False
        session_ids = []
        
        try:
            print(f"\n{'=' * 80}")
            print("🧪 RAPID SEQUENTIAL SESSION TEST")
            print(f"{'=' * 80}")
            
            blueprint_id, owns_blueprint = resolve_blueprint_id(
                api_client, stress_config, test_blueprint
            )
            
            num_rapid_sessions = 10
            # ✅ CORRECTED INPUT FORMAT
            test_inputs = {"user_prompt": stress_config.input_text}
            
            timings = []
            
            print(f"\n🚀 Creating and executing {num_rapid_sessions} sessions rapidly...")
            
            for i in range(num_rapid_sessions):
                start = time.time()
                
                # Create
                session_id = api_client.create_session(blueprint_id)
                session_ids.append(session_id)
                
                result = api_client.run_session(session_id, test_inputs)
                
                duration = time.time() - start
                timings.append(duration)
                
                if "polls" in result:
                    detail = f"{result.get('status')}, {result.get('polls')} polls"
                elif "chunks_received" in result:
                    detail = f"{result.get('status')}, {result.get('chunks_received')} chunks"
                else:
                    detail = str(result.get("status", "ok"))
                print(
                    f"  ✅ Session {i + 1}/{num_rapid_sessions}: {duration:.2f}s "
                    f"({detail})"
                )
            
            avg_time = sum(timings) / len(timings)
            print(f"\n📊 Average time per session: {avg_time:.2f}s")
            
            # Assert performance doesn't degrade significantly
            first_half_avg = sum(timings[:5]) / 5
            second_half_avg = sum(timings[5:]) / 5
            degradation = (second_half_avg - first_half_avg) / first_half_avg if first_half_avg > 0 else 0
            
            print(f"  • First half avg: {first_half_avg:.2f}s")
            print(f"  • Second half avg: {second_half_avg:.2f}s")
            print(f"  • Degradation: {degradation * 100:.1f}%")
            
            assert degradation < 0.5, f"Performance degraded too much: {degradation * 100:.1f}%"
            
            print("\n✅ RAPID SEQUENTIAL TEST PASSED\n")
            
        finally:
            # CLEANUP PHASE
            print(f"\n{'=' * 80}")
            print("🧹 CLEANUP PHASE")
            print(f"{'=' * 80}")

            if not stress_config.cleanup_sessions:
                print("  ⏭️  --stress-no-cleanup: leaving sessions/chats in place")
                for session_id in session_ids:
                    print(f"     session: {session_id}")
                if blueprint_id:
                    print(f"  ⏭️  Leaving blueprint {blueprint_id[:8]}... in place")
                print("✅ Cleanup skipped\n")
            else:
                # Delete sessions
                if session_ids:
                    print(f"Deleting {len(session_ids)} sessions...")
                    deleted_count = 0
                    for session_id in session_ids:
                        if api_client.delete_session(session_id):
                            deleted_count += 1
                    print(f"  ✅ Deleted {deleted_count}/{len(session_ids)} sessions")

                if blueprint_id and owns_blueprint:
                    print(f"Deleting blueprint {blueprint_id[:8]}...")
                    if api_client.delete_blueprint(blueprint_id):
                        print(f"  ✅ Blueprint deleted")
                elif blueprint_id:
                    print(f"  ⏭️  Leaving existing blueprint {blueprint_id[:8]}... in place")

                print("✅ Cleanup complete\n")


# =============================================================================
# CUSTOM BLUEPRINT TEST (for your specific blueprint)
# =============================================================================

@pytest.mark.e2e
@pytest.mark.stress
@pytest.mark.custom_blueprint
class TestCustomBlueprintStressSubmit:
    """Stress tests using your custom blueprint (mode via --stress-exec-mode)."""
    
    @pytest.fixture
    def custom_blueprint(self, stress_config, catalog_llm) -> Optional[Dict]:
        """
        Load your custom blueprint - from file or default.
        
        None when --blueprint-id is set. Otherwise --blueprint-path or the
        default stress blueprint wired to catalog_llm.
        """
        if stress_config.blueprint_id:
            return None

        if stress_config.blueprint_path:
            from pathlib import Path
            
            blueprint_file = Path(stress_config.blueprint_path)
            if not blueprint_file.exists():
                pytest.skip(f"Blueprint file not found: {stress_config.blueprint_path}")
            
            print(f"📄 Loading custom blueprint from: {stress_config.blueprint_path}")
            with open(blueprint_file, 'r') as f:
                blueprint = yaml.safe_load(f)
            
            blueprint_name = blueprint.get('name', 'Unknown')
            print(f"   Blueprint: {blueprint_name}")
            return blueprint

        return get_stress_test_blueprint(catalog_llm)
    
    @pytest.fixture
    def custom_inputs(self, stress_config):
        """Define inputs specific to your blueprint."""
        # ✅ CORRECTED INPUT FORMAT - matches your actual usage
        # Uses --input-text CLI option if provided
        return {
            "user_prompt": stress_config.input_text
        }
    
    def test_custom_blueprint_stress(
        self,
        stress_config: StressTestConfig,
        api_client: SessionAPIClient,
        custom_blueprint: Optional[Dict],
        custom_inputs: Dict,
        stress_runner: StressTestRunner
    ):
        """
        Stress test with your custom blueprint.
        
        Modify this test to match your blueprint's specific needs.
        """
        blueprint_id = None
        owns_blueprint = False
        session_ids = []
        
        try:
            print(f"\n{'=' * 80}")
            print("🧪 CUSTOM BLUEPRINT STRESS TEST")
            print(f"{'=' * 80}")
            
            stress_runner.metrics.total_start_time = time.time()
            
            blueprint_id, owns_blueprint = resolve_blueprint_id(
                api_client, stress_config, custom_blueprint
            )
            
            # Create sessions concurrently
            session_ids = stress_runner.run_concurrent_creation(blueprint_id)
            assert len(session_ids) > 0, "Failed to create sessions"
            
            # Execute sessions in parallel
            results = stress_runner.run_concurrent_execution(session_ids, custom_inputs)
            assert len(results) > 0, "Failed to execute sessions"
            
            stress_runner.metrics.total_end_time = time.time()
            
            # Print metrics
            stress_runner.print_metrics_summary()
            
            # Assertions
            creation_rate = len(session_ids) / stress_config.num_sessions
            execution_rate = len(results) / len(session_ids)
            
            assert creation_rate >= 0.9, f"Creation success rate too low: {creation_rate * 100:.1f}%"
            assert execution_rate >= 0.8, f"Execution success rate too low: {execution_rate * 100:.1f}%"
            
            print("\n✅ CUSTOM BLUEPRINT STRESS TEST PASSED\n")
            
        finally:
            # CLEANUP PHASE
            print(f"\n{'=' * 80}")
            print("🧹 CLEANUP PHASE")
            print(f"{'=' * 80}")

            if not stress_config.cleanup_sessions:
                print("  ⏭️  --stress-no-cleanup: leaving sessions/chats in place")
                for session_id in session_ids:
                    print(f"     session: {session_id}")
                if blueprint_id:
                    print(f"  ⏭️  Leaving blueprint {blueprint_id[:8]}... in place")
                print("✅ Cleanup skipped\n")
            else:
                # Delete sessions
                if session_ids:
                    print(f"Deleting {len(session_ids)} sessions...")
                    deleted_count = 0
                    for session_id in session_ids:
                        if api_client.delete_session(session_id):
                            deleted_count += 1
                    print(f"  ✅ Deleted {deleted_count}/{len(session_ids)} sessions")

                if blueprint_id and owns_blueprint:
                    print(f"Deleting blueprint {blueprint_id[:8]}...")
                    if api_client.delete_blueprint(blueprint_id):
                        print(f"  ✅ Blueprint deleted")
                elif blueprint_id:
                    print(f"  ⏭️  Leaving existing blueprint {blueprint_id[:8]}... in place")

                print("✅ Cleanup complete\n")

