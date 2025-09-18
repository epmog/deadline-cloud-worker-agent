#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Example usage of the local worker fixture.

This file demonstrates how to use the local worker test fixture
in your test cases.
"""

import dataclasses
from typing import Callable, Any

import pytest

# Example test showing how to use the session-scoped local worker fixture
def test_example_session_local_worker_usage(
    deadline_resources,  # DeadlineResources fixture
    worker_config,       # DeadlineWorkerConfiguration fixture  
    local_worker_factory: Callable[[Any, Any], Any],  # Session-scoped LocalWorkerProcess factory
) -> None:
    """
    Example test demonstrating session-scoped local worker fixture usage.
    
    This test shows how to:
    1. Create a session-scoped local worker with a specific fleet
    2. Verify the worker is running
    3. Access worker properties
    4. Let the fixture handle cleanup at session end
    """
    
    # Create a session-scoped local worker using the default fleet
    worker = local_worker_factory(
        config=worker_config,
        fleet=deadline_resources.fleet,
    )
    
    # Verify the worker started successfully
    assert worker.is_running(), "Session worker should be running after creation"
    
    # Access worker properties
    assert worker.config_file.exists(), "Config file should exist"
    assert worker.persistence_dir.exists(), "Persistence directory should exist"
    assert worker.logs_dir.exists(), "Logs directory should exist"
    
    # Check the fleet configuration
    config_content = worker.config_file.read_text()
    assert f'fleet_id = "{deadline_resources.fleet.id}"' in config_content
    
    # Worker will persist for the entire test session and be cleaned up at session end


# Example test showing how to use the function-scoped local worker fixture
def test_example_function_local_worker_usage(
    deadline_resources,  # DeadlineResources fixture
    worker_config,       # DeadlineWorkerConfiguration fixture  
    function_local_worker_factory: Callable[[Any, Any], Any],  # Function-scoped LocalWorkerProcess factory
) -> None:
    """
    Example test demonstrating function-scoped local worker fixture usage.
    
    Use this when you need a fresh worker for each test.
    """
    
    # Create a function-scoped local worker using the default fleet
    worker = function_local_worker_factory(
        config=worker_config,
        fleet=deadline_resources.fleet,
    )
    
    # Verify the worker started successfully
    assert worker.is_running(), "Function worker should be running after creation"
    
    # Access worker properties
    assert worker.config_file.exists(), "Config file should exist"
    assert worker.persistence_dir.exists(), "Persistence directory should exist"
    assert worker.logs_dir.exists(), "Logs directory should exist"
    
    # Check the fleet configuration
    config_content = worker.config_file.read_text()
    assert f'fleet_id = "{deadline_resources.fleet.id}"' in config_content
    
    # Worker will be cleaned up after this test function completes


def test_example_custom_worker_config(
    deadline_resources,
    worker_config,
    local_worker_factory: Callable[[Any, Any], Any],
) -> None:
    """
    Example showing how to use custom worker configuration.
    """
    
    # Create a custom configuration
    custom_config = dataclasses.replace(
        worker_config,
        retain_session_dir=True,
        cleanup_session_user_processes=False,
    )
    
    # Create worker with custom config and scaling fleet
    worker = local_worker_factory(
        config=custom_config,
        fleet=deadline_resources.scaling_fleet,
    )
    
    # Verify custom settings are applied
    config_content = worker.config_file.read_text()
    assert "retain_session_dir = true" in config_content
    assert "cleanup_session_user_processes = false" in config_content
    assert f'fleet_id = "{deadline_resources.scaling_fleet.id}"' in config_content


def test_example_multiple_workers(
    deadline_resources,
    worker_config,
    local_worker_factory: Callable[[Any, Any], Any],
) -> None:
    """
    Example showing how to create multiple local workers.
    """
    
    # Create first worker with default fleet
    worker1 = local_worker_factory(
        config=worker_config,
        fleet=deadline_resources.fleet,
    )
    
    # Create second worker with scaling fleet
    worker2 = local_worker_factory(
        config=worker_config,
        fleet=deadline_resources.scaling_fleet,
    )
    
    # Both workers should be running
    assert worker1.is_running(), "First worker should be running"
    assert worker2.is_running(), "Second worker should be running"
    
    # They should have different configurations
    config1 = worker1.config_file.read_text()
    config2 = worker2.config_file.read_text()
    
    assert f'fleet_id = "{deadline_resources.fleet.id}"' in config1
    assert f'fleet_id = "{deadline_resources.scaling_fleet.id}"' in config2
    
    # Both workers will be automatically cleaned up


def test_example_worker_logs(
    deadline_resources,
    worker_config,
    local_worker_factory: Callable[[Any, Any], Any],
) -> None:
    """
    Example showing how to access worker logs.
    """
    
    worker = local_worker_factory(
        config=worker_config,
        fleet=deadline_resources.fleet,
    )
    
    # Get worker logs (may be empty initially)
    logs = worker.get_logs()
    assert isinstance(logs, str), "Logs should be returned as a string"
    
    # Logs directory should exist and be accessible
    assert worker.logs_dir.exists(), "Logs directory should exist"
    assert worker.logs_dir.is_dir(), "Logs path should be a directory"


# Example using the session-scoped convenience fixture
def test_example_session_convenience_fixture(
    local_worker,  # Session-scoped LocalWorkerProcess fixture (uses default fleet)
) -> None:
    """
    Example using the session-scoped convenience local_worker fixture.
    
    This fixture automatically creates a worker with the default configuration
    and fleet that persists for the entire test session.
    """
    
    # Worker is already created and running (session-scoped)
    assert local_worker.is_running(), "Session worker should already be running"
    
    # Access worker properties directly
    assert local_worker.config_file.exists()
    assert local_worker.persistence_dir.exists()
    assert local_worker.logs_dir.exists()
    
    # Worker persists for the entire session


# Example using the function-scoped convenience fixture
def test_example_function_convenience_fixture(
    function_local_worker,  # Function-scoped LocalWorkerProcess fixture
) -> None:
    """
    Example using the function-scoped convenience function_local_worker fixture.
    
    This fixture automatically creates a fresh worker for each test function.
    """
    
    # Worker is already created and running (fresh for this test)
    assert function_local_worker.is_running(), "Function worker should already be running"
    
    # Access worker properties directly
    assert function_local_worker.config_file.exists()
    assert function_local_worker.persistence_dir.exists()
    assert function_local_worker.logs_dir.exists()
    
    # Worker cleanup happens after this test function


if __name__ == "__main__":
    print("This file contains example usage of the local worker fixture.")
    print("Run with pytest to execute the example tests.")
    print("\nExample command:")
    print("  pytest test/e2e/fixtures/example_usage.py -v")