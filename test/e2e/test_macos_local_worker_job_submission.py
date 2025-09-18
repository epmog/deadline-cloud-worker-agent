# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
macOS-specific e2e tests for job submission using the local worker agent fixture.

This test module verifies that the local worker agent can successfully process jobs
on macOS systems, providing an alternative to EC2-based testing for local development
and CI environments.
"""

import logging
import os
import platform
import pytest
from typing import Callable

from deadline_test_fixtures import (
    DeadlineClient,
    DeadlineWorkerConfiguration,
    TaskStatus,
)

from .conftest import DeadlineResources
from .fixtures.local_worker import LocalWorkerProcess
from .utils import submit_sleep_job, submit_custom_job

LOG = logging.getLogger(__name__)


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="macOS-specific tests - only run on Darwin systems"
)
class TestMacOSLocalWorkerJobSubmission:
    """
    Test class for macOS-specific job submission scenarios using local worker agents.
    
    These tests verify that the local worker fixture can successfully process
    various types of jobs on macOS, providing confidence that the worker agent
    functions correctly in local development environments.
    """

    def test_macos_local_worker_success_job(
        self,
        deadline_resources: DeadlineResources,
        deadline_client: DeadlineClient,
        worker_config: DeadlineWorkerConfiguration,
        local_worker_factory: Callable[[DeadlineWorkerConfiguration, any], LocalWorkerProcess],
    ) -> None:
        """
        Test that a local worker on macOS can successfully process a simple sleep job.
        
        This is the macOS equivalent of the test_success method from test_job_submissions.py,
        but using the local worker fixture instead of an EC2 instance.
        """
        # GIVEN - Create a local worker on macOS
        worker = local_worker_factory(
            config=worker_config,
            fleet=deadline_resources.fleet,
        )
        
        # Verify the worker is running
        assert worker.is_running(), "Local worker should be running on macOS"
        
        # WHEN - Submit a sleep job
        job = submit_sleep_job(
            "macOS Local Worker Success Test",
            deadline_client,
            deadline_resources.farm,
            deadline_resources.queue_a,
        )
        
        # THEN - Wait for job completion and verify success
        LOG.info(f"Waiting for job {job.id} to complete on macOS local worker")
        job.wait_until_complete(client=deadline_client)
        LOG.info(f"Job result on macOS: {job}")
        
        assert job.task_run_status == TaskStatus.SUCCEEDED, \
            f"Job should succeed on macOS local worker, but got status: {job.task_run_status}"
    
    def test_macos_local_worker_custom_script_job(
        self,
        deadline_resources: DeadlineResources,
        deadline_client: DeadlineClient,
        worker_config: DeadlineWorkerConfiguration,
        local_worker_factory: Callable[[DeadlineWorkerConfiguration, any], LocalWorkerProcess],
    ) -> None:
        """
        Test that a local worker on macOS can execute custom shell scripts.
        
        This test verifies that the worker can handle more complex job types
        beyond simple sleep commands.
        """
        # GIVEN - Create a local worker on macOS
        worker = local_worker_factory(
            config=worker_config,
            fleet=deadline_resources.fleet,
        )
        
        assert worker.is_running(), "Local worker should be running on macOS"
        
        # WHEN - Submit a job with a custom macOS-specific script
        macos_script = """#!/bin/bash
# macOS-specific commands to verify the environment
echo "Running on macOS: $(sw_vers -productName) $(sw_vers -productVersion)"
echo "Architecture: $(uname -m)"
echo "Hostname: $(hostname)"
echo "Current user: $(whoami)"
echo "Working directory: $(pwd)"
echo "Environment variables:"
env | grep -E "(HOME|USER|PATH)" | head -5
echo "macOS local worker job completed successfully"
"""
        
        job = submit_custom_job(
            "macOS Local Worker Custom Script Test",
            deadline_client,
            deadline_resources.farm,
            deadline_resources.queue_a,
            macos_script,
        )
        
        # THEN - Wait for job completion and verify success
        LOG.info(f"Waiting for custom script job {job.id} to complete on macOS local worker")
        job.wait_until_complete(client=deadline_client)
        LOG.info(f"Custom script job result on macOS: {job}")
        
        assert job.task_run_status == TaskStatus.SUCCEEDED, \
            f"Custom script job should succeed on macOS local worker, but got status: {job.task_run_status}"
    
    def test_macos_local_worker_environment_validation(
        self,
        deadline_resources: DeadlineResources,
        deadline_client: DeadlineClient,
        worker_config: DeadlineWorkerConfiguration,
        local_worker_factory: Callable[[DeadlineWorkerConfiguration, any], LocalWorkerProcess],
    ) -> None:
        """
        Test that validates the macOS environment is properly set up for the local worker.
        
        This test ensures that the worker has access to necessary system resources
        and can execute jobs in the expected environment.
        """
        # GIVEN - Create a local worker on macOS
        worker = local_worker_factory(
            config=worker_config,
            fleet=deadline_resources.fleet,
        )
        
        assert worker.is_running(), "Local worker should be running on macOS"
        
        # Verify worker directories exist and are accessible
        assert worker.config_file.exists(), "Worker config file should exist"
        assert worker.persistence_dir.exists(), "Worker persistence directory should exist"
        assert worker.logs_dir.exists(), "Worker logs directory should exist"
        
        # WHEN - Submit a job that validates the macOS environment
        validation_script = """#!/bin/bash
set -e  # Exit on any error

echo "=== macOS Environment Validation ==="

# Check macOS version
if ! sw_vers > /dev/null 2>&1; then
    echo "ERROR: sw_vers command not available - not running on macOS"
    exit 1
fi

echo "macOS Version: $(sw_vers -productVersion)"
echo "Build Version: $(sw_vers -buildVersion)"

# Check required commands are available
for cmd in whoami hostname pwd env; do
    if ! command -v "$cmd" > /dev/null 2>&1; then
        echo "ERROR: Required command '$cmd' not found"
        exit 1
    fi
done

# Check file system permissions
if [ ! -w "$(pwd)" ]; then
    echo "ERROR: No write permission in current directory"
    exit 1
fi

# Test file operations
test_file="macos_test_file.txt"
echo "Testing file operations" > "$test_file"
if [ ! -f "$test_file" ]; then
    echo "ERROR: Failed to create test file"
    exit 1
fi
rm "$test_file"

echo "=== Environment validation completed successfully ==="
"""
        
        job = submit_custom_job(
            "macOS Local Worker Environment Validation",
            deadline_client,
            deadline_resources.farm,
            deadline_resources.queue_a,
            validation_script,
        )
        
        # THEN - Wait for job completion and verify success
        LOG.info(f"Waiting for environment validation job {job.id} to complete on macOS")
        job.wait_until_complete(client=deadline_client)
        LOG.info(f"Environment validation job result on macOS: {job}")
        
        assert job.task_run_status == TaskStatus.SUCCEEDED, \
            f"Environment validation should succeed on macOS local worker, but got status: {job.task_run_status}"
    
    def test_macos_local_worker_logs_accessible(
        self,
        deadline_resources: DeadlineResources,
        deadline_client: DeadlineClient,
        worker_config: DeadlineWorkerConfiguration,
        local_worker_factory: Callable[[DeadlineWorkerConfiguration, any], LocalWorkerProcess],
    ) -> None:
        """
        Test that worker logs are properly generated and accessible on macOS.
        
        This test verifies that the local worker generates logs that can be
        accessed for debugging and monitoring purposes.
        """
        # GIVEN - Create a local worker on macOS
        worker = local_worker_factory(
            config=worker_config,
            fleet=deadline_resources.fleet,
        )
        
        assert worker.is_running(), "Local worker should be running on macOS"
        
        # WHEN - Submit a job and let it complete
        job = submit_sleep_job(
            "macOS Local Worker Logs Test",
            deadline_client,
            deadline_resources.farm,
            deadline_resources.queue_a,
        )
        
        job.wait_until_complete(client=deadline_client)
        assert job.task_run_status == TaskStatus.SUCCEEDED
        
        # THEN - Verify logs are accessible
        logs = worker.get_logs()
        assert isinstance(logs, str), "Logs should be returned as a string"
        
        # Check that logs directory contains files
        log_files = list(worker.logs_dir.glob("*.log"))
        LOG.info(f"Found {len(log_files)} log files in {worker.logs_dir}")
        
        # We should have at least some log content or files
        # (The exact content depends on the worker implementation)
        assert len(logs) > 0 or len(log_files) > 0, \
            "Worker should generate some logs or log files"


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="macOS-specific tests - only run on Darwin systems"
)
class TestMacOSLocalWorkerPerformance:
    """
    Performance-focused tests for macOS local worker to ensure it meets
    basic performance expectations.
    """
    
    def test_macos_local_worker_startup_time(
        self,
        deadline_resources: DeadlineResources,
        worker_config: DeadlineWorkerConfiguration,
        function_local_worker_factory: Callable[[DeadlineWorkerConfiguration, any], LocalWorkerProcess],
    ) -> None:
        """
        Test that local worker starts up in reasonable time on macOS.
        
        Uses function-scoped factory to test fresh worker startup.
        """
        import time
        
        # WHEN - Create a local worker and measure startup time
        start_time = time.time()
        
        worker = function_local_worker_factory(
            config=worker_config,
            fleet=deadline_resources.fleet,
        )
        
        startup_time = time.time() - start_time
        
        # THEN - Verify worker started and startup time is reasonable
        assert worker.is_running(), "Worker should start successfully on macOS"
        
        # Startup should be reasonably fast (less than 30 seconds)
        assert startup_time < 30.0, \
            f"Worker startup took {startup_time:.2f}s, which is longer than expected (30s)"
        
        LOG.info(f"macOS local worker started in {startup_time:.2f} seconds")


# Convenience function for running macOS-specific tests
def run_macos_tests():
    """
    Convenience function to run only the macOS-specific tests.
    
    Usage:
        pytest test/e2e/test_macos_local_worker_job_submission.py::run_macos_tests -v
    """
    if platform.system() != "Darwin":
        pytest.skip("macOS tests can only run on Darwin systems")
    
    # This function serves as a marker for running macOS tests
    pass


if __name__ == "__main__":
    print("macOS Local Worker Job Submission Tests")
    print(f"Current platform: {platform.system()}")
    
    if platform.system() == "Darwin":
        print("✓ Running on macOS - tests will execute")
        print("\nTo run these tests:")
        print("  pytest test/e2e/test_macos_local_worker_job_submission.py -v")
    else:
        print("✗ Not running on macOS - tests will be skipped")
        print(f"  Detected platform: {platform.system()}")
        print("  These tests require macOS (Darwin) to run")