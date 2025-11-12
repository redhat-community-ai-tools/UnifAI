"""
End-to-End Stress Test for Session Creation and Execution

This test validates the system's ability to handle concurrent session
creation and parallel execution under load.

Test Phases:
1. Blueprint Setup - Create/load a test blueprint
2. Concurrent Creation - Create N sessions in parallel
3. Parallel Execution - Execute M sessions concurrently
4. Verification - Validate all sessions completed correctly
5. Metrics - Report performance statistics

Run with:
    pytest tests/e2e/test_session_stress.py -v -s
    pytest tests/e2e/test_session_stress.py -v -s --stress-sessions=50 --stress-concurrent=10
"""

import pytest
import requests
import time
import json
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import threading
from collections import defaultdict


# =============================================================================
# TEST CONFIGURATION
# =============================================================================

@dataclass
class StressTestConfig:
    """Configuration for stress test parameters."""
    # API Configuration
    base_url: str = "http://localhost:8002"
    # base_url: str = "http://unifai-multiagent-be-tag-ai--pipeline.apps.stc-ai-e1-pp.imap.p1.openshiftapps.com"
    api_prefix: str = "/api"
    
    # User Configuration
    user_id: str = "stress_test_user"
    
    # Blueprint Configuration
    blueprint_path: Optional[str] = None  # Path to YAML blueprint file
    input_text: str = "What is 2+2?"  # Input text for execution
    
    # Load Configuration
    num_sessions: int = 20  # Total sessions to create
    concurrent_create: int = 5  # Concurrent session creations
    concurrent_execute: int = 10  # Concurrent session executions
    
    # Timing Configuration
    creation_timeout: float = 30.0  # Per session creation
    execution_timeout: float = 60.0  # Per session execution
    total_timeout: float = 300.0  # Total test timeout
    
    # Retry Configuration
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Verification Configuration
    verify_state: bool = True
    verify_status: bool = True


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
    
    def execute_session(self, session_id: str, inputs: Dict) -> Dict:
        """Execute a session and return results."""
        url = f"{self.base_url}/sessions/user.session.execute"
        
        payload = {
            "sessionId": session_id,
            "inputs": inputs,
            "stream": False,
            "scope": "public"
        }
        
        response = self.session.post(
            url,
            json=payload,
            timeout=self.config.execution_timeout
        )
        response.raise_for_status()
        
        return response.json()
    
    def get_session_status(self, session_id: str) -> str:
        """Get session status."""
        url = f"{self.base_url}/sessions/session.status.get"
        params = {"sessionId": session_id}
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
    def get_session_state(self, session_id: str) -> Dict:
        """Get session state."""
        url = f"{self.base_url}/sessions/session.state.get"
        params = {"sessionId": session_id}
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
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

def get_stress_test_blueprint() -> Dict:
    """
    Returns a simple blueprint for stress testing.
    
    This blueprint is designed to be:
    - Fast to execute (minimal external dependencies)
    - Reliable (no flaky external calls)
    - Deterministic (predictable outputs)
    
    Structure follows the standard blueprint format with rid-based references.
    """
    return {
        "description": "A simple agent pipeline for stress testing session creation and execution",
        "name": "Stress Test Blueprint",
        
        # ----------------------------
        # Providers
        # ----------------------------
        "providers": [],
        
        # ----------------------------
        # LLM Definitions
        # ----------------------------
        "llms": [
            {
                "rid": "stress_test_llm_rid",
                "name": "stress_test_llm",
                "type": "openai",
                "config": {
                    "type": "openai",
                    "model_name": "gemini-2.5-flash",
                    "api_key": "AIzaSyCnplFW816wfu0jNAyoxQQSQkNdX8yxgQc",
                    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai"
                }
            }
        ],
        
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
                    "llm": "stress_test_llm_rid",
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
        Execute a session and track metrics.
        
        Returns: (result, success, duration, error_message)
        """
        start_time = time.time()
        result = None
        success = False
        error_msg = None
        
        try:
            result = self.client.execute_session(session_id, inputs)
            success = True
            duration = time.time() - start_time
            
            with self.lock:
                self.metrics.add_execute_success(duration)
            
            return result, success, duration, None
            
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
    
    def run_concurrent_execution(self, session_ids: List[str], inputs: Dict) -> List[Dict]:
        """
        Execute multiple sessions concurrently.
        
        Returns: List of execution results
        """
        results = []
        
        print(f"\n⚡ Executing {len(session_ids)} sessions with concurrency={self.config.concurrent_execute}")
        
        with ThreadPoolExecutor(max_workers=self.config.concurrent_execute) as executor:
            futures = {
                executor.submit(self.execute_session_with_metrics, session_id, inputs, i): (i, session_id)
                for i, session_id in enumerate(session_ids)
            }
            
            for future in as_completed(futures):
                index, session_id = futures[future]
                try:
                    result, success, duration, error_msg = future.result(timeout=self.config.execution_timeout)
                    if success and result:
                        results.append(result)
                        print(f"  ✅ Execution {index + 1}/{len(session_ids)} completed in {duration:.2f}s")
                    else:
                        print(f"  ❌ Execution {index + 1}/{len(session_ids)} failed: {error_msg}")
                except Exception as e:
                    print(f"  ❌ Execution {index + 1}/{len(session_ids)} error: {e}")
        
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
    """Configuration fixture with CLI overrides."""
    config = StressTestConfig()
    
    # Allow CLI overrides
    if hasattr(request.config.option, 'stress_sessions'):
        config.num_sessions = request.config.option.stress_sessions
    if hasattr(request.config.option, 'stress_concurrent'):
        config.concurrent_execute = request.config.option.stress_concurrent
    if hasattr(request.config.option, 'blueprint_path'):
        config.blueprint_path = request.config.option.blueprint_path
    if hasattr(request.config.option, 'input_text'):
        config.input_text = request.config.option.input_text
    
    return config


@pytest.fixture
def api_client(stress_config):
    """API client fixture."""
    return SessionAPIClient(stress_config)


@pytest.fixture
def test_blueprint(stress_config):
    """Test blueprint fixture - loads from file if path provided."""
    if stress_config.blueprint_path:
        # Load from YAML file
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
    else:
        # Use default stress test blueprint
        return get_stress_test_blueprint()


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
class TestSessionStress:
    """End-to-end stress tests for session creation and execution."""
    
    def test_concurrent_session_creation_and_execution(
        self,
        stress_config: StressTestConfig,
        api_client: SessionAPIClient,
        test_blueprint: Dict,
        stress_runner: StressTestRunner
    ):
        """
        Test concurrent session creation and parallel execution.
        
        This test validates:
        1. System can handle multiple concurrent session creations
        2. Sessions can be executed in parallel
        3. All sessions complete successfully
        4. Performance meets acceptable thresholds
        """
        blueprint_id = None
        session_ids = []
        
        try:
            print(f"\n{'=' * 80}")
            print("🧪 STARTING E2E SESSION STRESS TEST")
            print(f"{'=' * 80}")
            print(f"Configuration:")
            print(f"  • Total Sessions: {stress_config.num_sessions}")
            print(f"  • Concurrent Creates: {stress_config.concurrent_create}")
            print(f"  • Concurrent Executes: {stress_config.concurrent_execute}")
            print(f"  • API: {stress_config.base_url}")
            
            stress_runner.metrics.total_start_time = time.time()
            
            # PHASE 1: Create Blueprint
            print(f"\n{'=' * 80}")
            print("📋 PHASE 1: Blueprint Setup")
            print(f"{'=' * 80}")
            
            blueprint_id = api_client.create_blueprint(test_blueprint)
            print(f"✅ Blueprint created: {blueprint_id}")
            
            # PHASE 2: Concurrent Session Creation
            print(f"\n{'=' * 80}")
            print("📋 PHASE 2: Concurrent Session Creation")
            print(f"{'=' * 80}")
            
            session_ids = stress_runner.run_concurrent_creation(blueprint_id)
            
            # Assert creation success
            assert len(session_ids) > 0, "No sessions were created successfully"
            creation_success_rate = len(session_ids) / stress_config.num_sessions
            print(f"\n✅ Created {len(session_ids)}/{stress_config.num_sessions} sessions ({creation_success_rate * 100:.1f}% success)")
            
            # PHASE 3: Parallel Session Execution
            print(f"\n{'=' * 80}")
            print("📋 PHASE 3: Parallel Session Execution")
            print(f"{'=' * 80}")
            
            # ✅ CORRECTED INPUT FORMAT - matches run_test_new_version
            test_inputs = {
                "user_prompt": stress_config.input_text
            }
            
            results = stress_runner.run_concurrent_execution(session_ids, test_inputs)
            
            # Assert execution success
            assert len(results) > 0, "No sessions executed successfully"
            execution_success_rate = len(results) / len(session_ids)
            print(f"\n✅ Executed {len(results)}/{len(session_ids)} sessions ({execution_success_rate * 100:.1f}% success)")
            
            stress_runner.metrics.total_end_time = time.time()
            
            # PHASE 4: Verification
            if stress_config.verify_status:
                print(f"\n{'=' * 80}")
                print("📋 PHASE 4: Session Status Verification")
                print(f"{'=' * 80}")
                
                completed_count = 0
                for i, session_id in enumerate(session_ids[:5]):  # Sample first 5
                    try:
                        status = api_client.get_session_status(session_id)
                        print(f"  • Session {i + 1}: {status}")
                        if status == "COMPLETED":
                            completed_count += 1
                    except Exception as e:
                        print(f"  • Session {i + 1}: Error getting status - {e}")
            
            # PHASE 5: Metrics Report
            stress_runner.print_metrics_summary()
            
            # Final Assertions
            assert creation_success_rate >= 0.9, f"Creation success rate too low: {creation_success_rate * 100:.1f}%"
            assert execution_success_rate >= 0.8, f"Execution success rate too low: {execution_success_rate * 100:.1f}%"
            
            print("\n" + "=" * 80)
            print("✅ STRESS TEST PASSED")
            print("=" * 80 + "\n")
            
        finally:
            # CLEANUP PHASE
            print(f"\n{'=' * 80}")
            print("🧹 CLEANUP PHASE")
            print(f"{'=' * 80}")
            
            # Delete sessions
            if session_ids:
                print(f"Deleting {len(session_ids)} sessions...")
                deleted_count = 0
                for session_id in session_ids:
                    if api_client.delete_session(session_id):
                        deleted_count += 1
                print(f"  ✅ Deleted {deleted_count}/{len(session_ids)} sessions")
            
            # Delete blueprint
            if blueprint_id:
                print(f"Deleting blueprint {blueprint_id[:8]}...")
                if api_client.delete_blueprint(blueprint_id):
                    print(f"  ✅ Blueprint deleted")
            
            print("✅ Cleanup complete\n")
    
    def test_rapid_sequential_sessions(
        self,
        stress_config: StressTestConfig,
        api_client: SessionAPIClient,
        test_blueprint: Dict
    ):
        """
        Test rapid sequential session creation and execution.
        
        This validates:
        - System handles rapid consecutive operations
        - No resource leaks or blocking
        - Maintains performance consistency
        """
        blueprint_id = None
        session_ids = []
        
        try:
            print(f"\n{'=' * 80}")
            print("🧪 RAPID SEQUENTIAL SESSION TEST")
            print(f"{'=' * 80}")
            
            # Create blueprint
            blueprint_id = api_client.create_blueprint(test_blueprint)
            print(f"✅ Blueprint created: {blueprint_id}")
            
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
                
                # Execute
                result = api_client.execute_session(session_id, test_inputs)
                
                duration = time.time() - start
                timings.append(duration)
                
                print(f"  ✅ Session {i + 1}/{num_rapid_sessions}: {duration:.2f}s")
            
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
            
            # Delete sessions
            if session_ids:
                print(f"Deleting {len(session_ids)} sessions...")
                deleted_count = 0
                for session_id in session_ids:
                    if api_client.delete_session(session_id):
                        deleted_count += 1
                print(f"  ✅ Deleted {deleted_count}/{len(session_ids)} sessions")
            
            # Delete blueprint
            if blueprint_id:
                print(f"Deleting blueprint {blueprint_id[:8]}...")
                if api_client.delete_blueprint(blueprint_id):
                    print(f"  ✅ Blueprint deleted")
            
            print("✅ Cleanup complete\n")


# =============================================================================
# CUSTOM BLUEPRINT TEST (for your specific blueprint)
# =============================================================================

@pytest.mark.e2e
@pytest.mark.stress
@pytest.mark.custom_blueprint
class TestCustomBlueprintStress:
    """Stress tests using your custom blueprint."""
    
    @pytest.fixture
    def custom_blueprint(self, stress_config):
        """
        Load your custom blueprint - from file or default.
        
        Uses --blueprint-path CLI option if provided, otherwise uses default.
        """
        if stress_config.blueprint_path:
            # Load from file specified in CLI
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
        else:
            # Default to stress test blueprint
            return get_stress_test_blueprint()
    
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
        custom_blueprint: Dict,
        custom_inputs: Dict,
        stress_runner: StressTestRunner
    ):
        """
        Stress test with your custom blueprint.
        
        Modify this test to match your blueprint's specific needs.
        """
        blueprint_id = None
        session_ids = []
        
        try:
            print(f"\n{'=' * 80}")
            print("🧪 CUSTOM BLUEPRINT STRESS TEST")
            print(f"{'=' * 80}")
            
            stress_runner.metrics.total_start_time = time.time()
            
            # Create blueprint
            blueprint_id = api_client.create_blueprint(custom_blueprint)
            print(f"✅ Custom blueprint created: {blueprint_id}")
            
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
            
            # Delete sessions
            if session_ids:
                print(f"Deleting {len(session_ids)} sessions...")
                deleted_count = 0
                for session_id in session_ids:
                    if api_client.delete_session(session_id):
                        deleted_count += 1
                print(f"  ✅ Deleted {deleted_count}/{len(session_ids)} sessions")
            
            # Delete blueprint
            if blueprint_id:
                print(f"Deleting blueprint {blueprint_id[:8]}...")
                if api_client.delete_blueprint(blueprint_id):
                    print(f"  ✅ Blueprint deleted")
            
            print("✅ Cleanup complete\n")

