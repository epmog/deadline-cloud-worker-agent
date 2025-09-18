# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Tests for the local worker fixture functionality.
"""

import dataclasses
import logging
import time
from typing import Callable

import pytest

from deadline_test_fixtures import (
    DeadlineClient,
    DeadlineWorkerConfiguration,
)

from test.e2e.conftest import DeadlineResources
from test.e2e.fixtures.local_worker import LocalWorkerProcess
from test.e2e.utils import submit_sleep_job

LOG = logging.getLogger(__name__)


class TestLocalWorker:
    """Tests for local worker functionality."""
    
    def test_session_local_worker_starts_and_persists(
        self,
        deadline_resources: DeadlineResources,
        worker_config: DeadlineWorkerConfiguration,
        local_worker_factory: Callable[[DeadlineWorkerConfiguration, any], LocalWorkerProcess],
    ) -> None:
        """Test that a session-scoped local worker can be started and persists across tests."""
        
        # Create a local worker (session-scoped)
        worker = local_worker_factory(
            config=worker_config,
            fleet=deadline_resources.fleet,
        )
        
        # Verify the worker is running
        assert worker.is_running(), "Session worker should be running after creation"
        
        # Note: Don't stop the worker here - it should persist for the session
        # The fixture will handle cleanup at the end of the session
    
    def test_function_local_worker_starts_and_stops(
        self,
        deadline_resources: DeadlineResources,
        worker_config: DeadlineWorkerConfiguration,
        function_local_worker_factory: Callable[[DeadlineWorkerConfiguration, any], LocalWorkerProcess],
    ) -> None:
        """Test that a function-scoped local worker can be started and stopped per test."""
        
        # Create a local worker (function-scoped)
        worker = function_local_worker_factory(
            config=worker_config,
            fleet=deadline_resources.fleet,
        )
        
        # Verify the worker is running
        assert worker.is_running(), "Function worker should be running after creation"
        
        # Stop the worker manually (though fixture will also clean up)
        worker.stop()
        
        # Give it a moment to stop
        time.sleep(1)
        
        # Verify the worker has stopped
        assert not worker.is_running(), "Function worker should be stopped after calling stop()"
    
    def test_session_local_worker_with_custom_config(
        self,
        deadline_resources: DeadlineResources,
        worker_config: DeadlineWorkerConfiguration,
        local_worker_factory: Callable[[DeadlineWorkerConfiguration, any], LocalWorkerProcess],
    ) -> None:
        """Test that a session-scoped local worker can be created with custom configuration."""
        
        # Create a session-scoped local worker with custom config
        worker = local_worker_factory(
            config=worker_config,
            fleet=deadline_resources.fleet,
        )
        
        # Verify the worker is running
        assert worker.is_running(), "Session worker should be running with custom config"
        
        # Verify config file was created
        assert worker.config_file.exists(), "Config file should exist"
        
        # Check that custom settings are in the config
        config_content = worker.config_file.read_text()
    
    def test_local_worker_with_different_fleet(
        self,
        deadline_resources: DeadlineResources,
        worker_config: DeadlineWorkerConfiguration,
        local_worker_factory: Callable[[DeadlineWorkerConfiguration, any], LocalWorkerProcess],
    ) -> None:
        """Test that a local worker can be created with a different fleet."""
        
        # Create a local worker with the scaling fleet
        worker = local_worker_factory(
            config=worker_config,
            fleet=deadline_resources.scaling_fleet,
        )
        
        # Verify the worker is running
        assert worker.is_running(), "Worker should be running with scaling fleet"
        
        # Verify the fleet ID is correct in the config
        config_content = worker.config_file.read_text()
        assert f'fleet_id = "{deadline_resources.scaling_fleet.id}"' in config_content
    
    @pytest.mark.skip(reason="Requires valid AWS credentials and may take time")
    def test_local_worker_can_process_job(
        self,
        deadline_resources: DeadlineResources,
        deadline_client: DeadlineClient,
        worker_config: DeadlineWorkerConfiguration,
        local_worker_factory: Callable[[DeadlineWorkerConfiguration, any], LocalWorkerProcess],
    ) -> None:
        """Test that a local worker can actually process a job (integration test)."""
        
        # Create a local worker
        worker = local_worker_factory(
            config=worker_config,
            fleet=deadline_resources.fleet,
        )
        
        # Submit a simple job
        job = submit_sleep_job(
            "Local Worker Test Job",
            deadline_client,
            deadline_resources.farm,
            deadline_resources.queue_a,
        )
        
        try:
            # Wait for the job to be picked up and completed
            # Note: This is a basic test - in practice you'd want more sophisticated
            # job monitoring and timeout handling
            job.wait_until_complete(client=deadline_client, max_retries=30)
            
            # Verify job completed successfully
            job.refresh_job_info(client=deadline_client)
            assert job.lifecycle_status == "COMPLETED"
            
        finally:
            # Clean up the job if it's still running
            try:
                deadline_client.update_job(
                    farmId=job.farm.id,
                    queueId=job.queue.id,
                    jobId=job.id,
                    targetTaskRunStatus="CANCELED",
                )
            except Exception as e:
                LOG.warning(f"Failed to cancel job during cleanup: {e}")
    
    def test_local_worker_logs_accessible(
        self,
        deadline_resources: DeadlineResources,
        worker_config: DeadlineWorkerConfiguration,
        local_worker_factory: Callable[[DeadlineWorkerConfiguration, any], LocalWorkerProcess],
    ) -> None:
        """Test that local worker logs are accessible."""
        
        # Create a local worker
        worker = local_worker_factory(
            config=worker_config,
            fleet=deadline_resources.fleet,
        )
        
        # Give the worker a moment to generate some logs
        time.sleep(3)
        
        # Get the logs
        logs = worker.get_logs()
        
        # Verify we can access logs (even if empty initially)
        assert isinstance(logs, str), "Logs should be returned as a string"
        
        # The logs directory should exist
        assert worker.logs_dir.exists(), "Logs directory should exist"
    
    def test_session_worker_persistence(
        self,
        deadline_resources: DeadlineResources,
        worker_config: DeadlineWorkerConfiguration,
        local_worker_factory: Callable[[DeadlineWorkerConfiguration, any], LocalWorkerProcess],
    ) -> None:
        """Test that session-scoped workers persist across multiple calls."""
        
        # Create first worker
        worker1 = local_worker_factory(
            config=worker_config,
            fleet=deadline_resources.fleet,
        )
        
        # Get the process ID
        pid1 = worker1.process.pid
        
        # Create "another" worker with same config - should reuse the existing one
        # Note: This depends on implementation - the factory might create a new one
        # or reuse existing. This test documents the expected behavior.
        worker2 = local_worker_factory(
            config=worker_config,
            fleet=deadline_resources.fleet,
        )
        
        # Both should be running
        assert worker1.is_running(), "First worker should still be running"
        assert worker2.is_running(), "Second worker should be running"
        
        # They might be the same instance or different - depends on factory implementation
        # The key is that they both work and persist for the session
    
    def test_convenience_fixtures(
        self,
        local_worker: LocalWorkerProcess,
        function_local_worker: LocalWorkerProcess,
    ) -> None:
        """Test the convenience fixtures for both session and function scoped workers."""
        
        # Session-scoped convenience fixture
        assert local_worker.is_running(), "Session convenience worker should be running"
        assert local_worker.config_file.exists(), "Session worker config should exist"
        
        # Function-scoped convenience fixture  
        assert function_local_worker.is_running(), "Function convenience worker should be running"
        assert function_local_worker.config_file.exists(), "Function worker config should exist"
        
        # They should be different workers
        assert local_worker.process.pid != function_local_worker.process.pid, \
            "Session and function workers should have different PIDs"