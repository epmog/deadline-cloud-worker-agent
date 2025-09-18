# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Local worker fixture for spinning up a worker agent on the current machine.
"""

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Generator, Optional, Any
import pytest
import signal
import sys
from dataclasses import dataclass


from deadline_test_fixtures import (
    DeadlineWorkerConfiguration,
    Fleet,
)

LOG = logging.getLogger(__name__)


@dataclass
class LocalWorkerProcess:
    """Represents a local worker agent process running on the current machine."""
    
    process: subprocess.Popen
    config_file: Path
    persistence_dir: Path
    logs_dir: Path
    fleet: Any  # Fleet when available
    
    def stop(self) -> None:
        """Stop the worker agent process."""
        if self.process and self.process.poll() is None:
            LOG.info("Stopping local worker process")
            try:
                # Send SIGTERM first for graceful shutdown
                self.process.terminate()
                
                # Wait up to 30 seconds for graceful shutdown
                try:
                    self.process.wait(timeout=30)
                    LOG.info("Local worker process stopped gracefully")
                except subprocess.TimeoutExpired:
                    LOG.warning("Worker process did not stop gracefully, forcing kill")
                    self.process.kill()
                    self.process.wait()
                    
            except Exception as e:
                LOG.error(f"Error stopping worker process: {e}")
                try:
                    self.process.kill()
                    self.process.wait()
                except:
                    pass
    
    def is_running(self) -> bool:
        """Check if the worker process is still running."""
        return self.process and self.process.poll() is None
    
    def get_logs(self) -> str:
        """Get the worker logs."""
        log_files = list(self.logs_dir.glob("*.log"))
        if not log_files:
            return "No log files found"
        
        # Get the most recent log file
        latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
        try:
            return latest_log.read_text()
        except Exception as e:
            return f"Error reading log file: {e}"


def create_worker_config_file(
    config: DeadlineWorkerConfiguration,
    fleet: Fleet,
    config_path: Path,
    persistence_dir: Path,
    logs_dir: Path,
) -> None:
    """Create a minimal worker configuration file for the local worker."""
    
    config_content = f"""# Local worker configuration for testing
farm_id = "{fleet.farm.id}"
fleet_id = "{fleet.id}"

# Directories
worker_persistence_dir = "{persistence_dir}"
worker_logs_dir = "{logs_dir}"

# Logging
verbose = true
structured_logs = false
local_session_logs = true

# Host configuration
no_shutdown = {str(getattr(config, 'allow_shutdown', True)).lower()}
"""

    # Add job users if specified
    if hasattr(config, 'job_users') and config.job_users:
        job_user = config.job_users[0]
        config_content += f'\nposix_job_user = "{job_user.user}:{job_user.group}"\n'

    # Add Windows job users if specified
    if hasattr(config, 'windows_job_users') and config.windows_job_users:
        config_content += f'\nwindows_job_user = "{config.windows_job_users[0]}"\n'

    # Add other configuration options
    if hasattr(config, 'disallow_instance_profile') and config.disallow_instance_profile:
        config_content += f"\nallow_instance_profile = false\n"
    
    if hasattr(config, 'no_local_session_logs') and config.no_local_session_logs:
        config_content += f"\nlocal_session_logs = false\n"
    
    if hasattr(config, 'session_root_dir') and config.session_root_dir:
        config_content += f'\nsession_root_dir = "{config.session_root_dir}"\n'

    config_path.write_text(config_content)
    LOG.info(f"Created worker config file at {config_path}")


def create_worker_env_vars(
    config: DeadlineWorkerConfiguration,
    fleet: Fleet,
    persistence_dir: Path,
    logs_dir: Path,
) -> dict[str, str]:
    """Create environment variables for the local worker configuration."""
    
    env_vars = {
        "DEADLINE_WORKER_FARM_ID": fleet.farm.id,
        "DEADLINE_WORKER_FLEET_ID": fleet.id,
        "DEADLINE_WORKER_PERSISTENCE_DIR": str(persistence_dir),
        "DEADLINE_WORKER_LOGS_DIR": str(logs_dir),
        "DEADLINE_WORKER_VERBOSE": "true",
        "DEADLINE_WORKER_STRUCTURED_LOGS": "false",
        "DEADLINE_WORKER_LOCAL_SESSION_LOGS": "true",
        "DEADLINE_WORKER_NO_SHUTDOWN": str(getattr(config, 'allow_shutdown', False)).lower(),
    }

    # Add job users if specified
    if hasattr(config, 'job_users') and config.job_users:
        # For POSIX job user, use the first one if available
        job_user = config.job_users[0]
        env_vars["DEADLINE_WORKER_POSIX_JOB_USER"] = f"{job_user.user}:{job_user.group}"

    # Add Windows job users if specified
    if hasattr(config, 'windows_job_users') and config.windows_job_users:
        env_vars["DEADLINE_WORKER_WINDOWS_JOB_USER"] = config.windows_job_users[0]

    # Add other configuration options
    if hasattr(config, 'disallow_instance_profile') and config.disallow_instance_profile:
        env_vars["DEADLINE_WORKER_ALLOW_INSTANCE_PROFILE"] = "false"
    
    if hasattr(config, 'no_local_session_logs') and config.no_local_session_logs:
        env_vars["DEADLINE_WORKER_LOCAL_SESSION_LOGS"] = "false"
    
    if hasattr(config, 'session_root_dir') and config.session_root_dir:
        env_vars["DEADLINE_WORKER_SESSION_ROOT_DIR"] = str(config.session_root_dir)

    LOG.info(f"Created worker environment variables for configuration")
    return env_vars


@pytest.fixture(scope="session")
def local_worker_factory(
    request: pytest.FixtureRequest,
) -> Generator[callable, None, None]:
    """
    Session-scoped factory fixture for creating local worker processes on the current machine.
    
    Returns a callable that takes a DeadlineWorkerConfiguration and Fleet,
    and returns a LocalWorkerProcess. Workers created by this factory will persist
    for the entire test session.
    """
    created_workers = []
    
    def _create_local_worker(
        config: Any,  # DeadlineWorkerConfiguration when available
        fleet: Any,   # Fleet when available
    ) -> LocalWorkerProcess:
        """Create and start a local worker process."""
        
        # Create temporary directories for this worker
        temp_dir = Path(tempfile.mkdtemp(prefix="local_worker_"))
        persistence_dir = temp_dir / "persistence"
        logs_dir = temp_dir / "logs"
        config_file = temp_dir / "worker.toml"
        
        persistence_dir.mkdir(exist_ok=True)
        logs_dir.mkdir(exist_ok=True)
        
        LOG.info(f"Creating local worker with temp dir: {temp_dir}")
        
        # Create the worker configuration file
        create_worker_config_file(
            config=config,
            fleet=fleet,
            config_path=config_file,
            persistence_dir=persistence_dir,
            logs_dir=logs_dir,
        )
        
        # Also create environment variables as backup
        worker_env_vars = create_worker_env_vars(
            config=config,
            fleet=fleet,
            persistence_dir=persistence_dir,
            logs_dir=logs_dir,
        )
        
        # Determine the worker agent command
        worker_agent_cmd = _get_worker_agent_command()
        
        # Start the worker process - try different approaches
        src_path = Path(__file__).parent.parent.parent / "src"
        env = dict(os.environ)
        
        # Add src to PYTHONPATH to ensure the module can be found
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{src_path}:{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = str(src_path)
        
        # Add worker configuration environment variables
        env.update(worker_env_vars)
        
        # Set environment variable to override config file path
        # This is a custom approach for testing - we'll patch the config loading
        env["DEADLINE_WORKER_CONFIG_FILE"] = str(config_file)
        
        # Create a Python script that patches the config path and runs the worker
        patch_script = temp_dir / "run_worker.py"
        patch_script.write_text(f"""#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# Add src to path for development
src_path = Path('{Path(__file__).parent.parent.parent / "src"}')
if src_path.exists():
    sys.path.insert(0, str(src_path))

# Monkey patch the DEFAULT_CONFIG_PATH to use our config file
try:
    import deadline_worker_agent.config.config_file as config_file_mod
    config_file_mod.DEFAULT_CONFIG_PATH[sys.platform] = Path('{config_file}')
    print(f'Patched config path to: {{config_file_mod.DEFAULT_CONFIG_PATH[sys.platform]}}')
    
    # Now run the worker agent
    from deadline_worker_agent.__main__ import init
    init()
except ImportError as e:
    print(f'Import error: {{e}}')
    sys.exit(1)
except Exception as e:
    print(f'Error: {{e}}')
    sys.exit(1)
""")
        
        # Try different execution methods
        cmd_options = [
            # Option 1: Use the patched script with the installed Python
            ["/Library/Frameworks/Python.framework/Versions/3.10/bin/python3", str(patch_script)],
            # Option 2: Use the patched script with current Python
            [sys.executable, str(patch_script)],
            # Option 3: Use installed script (will likely fail due to config path)
            ["deadline-worker-agent"],
        ]
        
        process = None
        last_error = None
        
        for cmd in cmd_options:
            LOG.info(f"Trying to start local worker with command: {' '.join(cmd[:2])}...")
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=temp_dir,
                    env=env,
                )
                
                # Give the process a moment to start and check if it fails immediately
                time.sleep(1)
                if process.poll() is None:
                    # Process is still running, success!
                    break
                else:
                    # Process exited immediately, try next option
                    stdout, _ = process.communicate()
                    last_error = f"Command failed: {' '.join(cmd)}\nOutput: {stdout}"
                    process = None
                    continue
                    
            except FileNotFoundError as e:
                last_error = f"Command not found: {' '.join(cmd)} - {e}"
                process = None
                continue
            except Exception as e:
                last_error = f"Failed to start command: {' '.join(cmd)} - {e}"
                process = None
                continue
        
        if process is None:
            raise RuntimeError(f"Failed to start worker with any method. Last error: {last_error}")
        
        try:
            # Give the process another moment to fully initialize
            time.sleep(1)
            
            # Final check if process is still running
            if process.poll() is not None:
                stdout, _ = process.communicate()
                raise RuntimeError(f"Worker process failed to start. Output: {stdout}")
            
            worker = LocalWorkerProcess(
                process=process,
                config_file=config_file,
                persistence_dir=persistence_dir,
                logs_dir=logs_dir,
                fleet=fleet,
            )
            
            created_workers.append(worker)
            LOG.info(f"Local worker started successfully with PID: {process.pid}")
            return worker
            
        except Exception as e:
            LOG.error(f"Failed to start local worker: {e}")
            # Clean up temp directory on failure
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
    
    yield _create_local_worker
    
    # Cleanup all created workers
    for worker in created_workers:
        try:
            worker.stop()
        except Exception as e:
            LOG.error(f"Error stopping worker during cleanup: {e}")
        
        # Clean up temp directories
        try:
            import shutil
            shutil.rmtree(worker.persistence_dir.parent, ignore_errors=True)
        except Exception as e:
            LOG.error(f"Error cleaning up temp directory: {e}")


def _get_worker_agent_command() -> str:
    """Get the command to run the worker agent."""
    # Check if we have a wheel file specified
    wheel_path = os.getenv("WORKER_AGENT_WHL_PATH")
    if wheel_path and Path(wheel_path).exists():
        return wheel_path
    
    # Check if we have a requirement specifier
    requirement = os.getenv("WORKER_AGENT_REQUIREMENT_SPECIFIER")
    if requirement:
        return requirement
    
    # Default to the current source code
    return "deadline-cloud-worker-agent"


@pytest.fixture(scope="session")
def local_worker(
    request: pytest.FixtureRequest,
    worker_config: Any,  # DeadlineWorkerConfiguration when available
    local_worker_factory: callable,
) -> Generator[LocalWorkerProcess, None, None]:
    """
    Session-scoped convenience fixture that creates a single local worker using the default fleet.
    
    The worker will persist for the entire test session, making it efficient for
    multiple tests that need a worker. Requires FLEET_ID environment variable to be set.
    """
    from test.e2e.conftest import DeadlineResources
    
    deadline_resources: DeadlineResources = request.getfixturevalue("deadline_resources")
    
    worker = local_worker_factory(
        config=worker_config,
        fleet=deadline_resources.fleet,
    )
    
    yield worker
    
    # Cleanup is handled by the factory fixture


@pytest.fixture(scope="function")
def function_local_worker_factory(
    request: pytest.FixtureRequest,
) -> Generator[callable, None, None]:
    """
    Function-scoped factory fixture for creating local worker processes.
    
    Use this when you need fresh workers for each test function.
    Workers created by this factory will be cleaned up after each test.
    """
    created_workers = []
    
    def _create_local_worker(
        config: Any,  # DeadlineWorkerConfiguration when available
        fleet: Any,   # Fleet when available
    ) -> LocalWorkerProcess:
        """Create and start a local worker process."""
        
        # Create temporary directories for this worker
        temp_dir = Path(tempfile.mkdtemp(prefix="local_worker_"))
        persistence_dir = temp_dir / "persistence"
        logs_dir = temp_dir / "logs"
        config_file = temp_dir / "worker.toml"
        
        persistence_dir.mkdir(exist_ok=True)
        logs_dir.mkdir(exist_ok=True)
        
        LOG.info(f"Creating function-scoped local worker with temp dir: {temp_dir}")
        
        # Create the worker configuration file
        create_worker_config_file(
            config=config,
            fleet=fleet,
            config_path=config_file,
            persistence_dir=persistence_dir,
            logs_dir=logs_dir,
        )
        
        # Also create environment variables as backup
        worker_env_vars = create_worker_env_vars(
            config=config,
            fleet=fleet,
            persistence_dir=persistence_dir,
            logs_dir=logs_dir,
        )
        
        # Start the worker process - try different approaches
        src_path = Path(__file__).parent.parent.parent / "src"
        env = dict(os.environ)
        
        # Add src to PYTHONPATH to ensure the module can be found
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{src_path}:{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = str(src_path)
        
        # Add worker configuration environment variables
        env.update(worker_env_vars)
        
        # Set environment variable to override config file path
        env["DEADLINE_WORKER_CONFIG_FILE"] = str(config_file)
        
        # Try the installed script first, then fall back to module execution
        cmd_options = [
            # Option 1: Use installed script (if package is installed)
            ["deadline-worker-agent"],
            # Option 2: Use module execution with PYTHONPATH and config file patching
            [sys.executable, "-c", f"""
import sys
import os
from pathlib import Path

# Patch the config file path before importing the worker agent
sys.path.insert(0, '{Path(__file__).parent.parent.parent / "src"}')

# Monkey patch the DEFAULT_CONFIG_PATH to use our config file
import deadline_worker_agent.config.config_file as config_file_mod
config_file_mod.DEFAULT_CONFIG_PATH[sys.platform] = Path('{config_file}')

# Now run the worker agent
from deadline_worker_agent.__main__ import init
init()
"""],
        ]
        
        process = None
        last_error = None
        
        for cmd in cmd_options:
            LOG.info(f"Trying to start function-scoped local worker with command: {' '.join(cmd[:2])}...")
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=temp_dir,
                    env=env,
                )
                
                # Give the process a moment to start and check if it fails immediately
                time.sleep(1)
                if process.poll() is None:
                    # Process is still running, success!
                    break
                else:
                    # Process exited immediately, try next option
                    stdout, _ = process.communicate()
                    last_error = f"Command failed: {' '.join(cmd)}\nOutput: {stdout}"
                    process = None
                    continue
                    
            except FileNotFoundError as e:
                last_error = f"Command not found: {' '.join(cmd)} - {e}"
                process = None
                continue
            except Exception as e:
                last_error = f"Failed to start command: {' '.join(cmd)} - {e}"
                process = None
                continue
        
        if process is None:
            raise RuntimeError(f"Failed to start function-scoped worker with any method. Last error: {last_error}")
        
        try:
            # Give the process another moment to fully initialize
            time.sleep(1)
            
            # Final check if process is still running
            if process.poll() is not None:
                stdout, _ = process.communicate()
                raise RuntimeError(f"Function-scoped worker process failed to start. Output: {stdout}")
            
            worker = LocalWorkerProcess(
                process=process,
                config_file=config_file,
                persistence_dir=persistence_dir,
                logs_dir=logs_dir,
                fleet=fleet,
            )
            
            created_workers.append(worker)
            LOG.info(f"Function-scoped local worker started successfully with PID: {process.pid}")
            return worker
            
        except Exception as e:
            LOG.error(f"Failed to start function-scoped local worker: {e}")
            # Clean up temp directory on failure
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
    
    yield _create_local_worker
    
    # Cleanup all created workers after each test function
    for worker in created_workers:
        try:
            worker.stop()
        except Exception as e:
            LOG.error(f"Error stopping function-scoped worker during cleanup: {e}")
        
        # Clean up temp directories
        try:
            import shutil
            shutil.rmtree(worker.persistence_dir.parent, ignore_errors=True)
        except Exception as e:
            LOG.error(f"Error cleaning up temp directory: {e}")


@pytest.fixture(scope="function")
def function_local_worker(
    request: pytest.FixtureRequest,
    worker_config: Any,  # DeadlineWorkerConfiguration when available
    function_local_worker_factory: callable,
) -> Generator[LocalWorkerProcess, None, None]:
    """
    Function-scoped convenience fixture that creates a fresh local worker for each test.
    
    Use this when you need a clean worker state for each test function.
    """
    from test.e2e.conftest import DeadlineResources
    
    deadline_resources: DeadlineResources = request.getfixturevalue("deadline_resources")
    
    worker = function_local_worker_factory(
        config=worker_config,
        fleet=deadline_resources.fleet,
    )
    
    yield worker
    
    # Cleanup is handled by the factory fixture