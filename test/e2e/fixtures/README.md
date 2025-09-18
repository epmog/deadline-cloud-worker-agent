# Local Worker Test Fixture

This module provides test fixtures for running worker agents locally on the current machine for testing purposes.

## Overview

The local worker fixture allows you to:
- Spin up a worker agent process on the current machine
- Configure it with a specific fleet
- Use custom worker configurations
- Test worker behavior without needing EC2 instances or Docker containers

## Fixtures

### Session-Scoped Fixtures (Recommended)

#### `local_worker_factory`

A **session-scoped** factory fixture that creates local worker processes. Workers created by this factory persist for the entire test session, making them efficient for test suites with multiple tests.

Returns a callable that takes:
- `config`: A `DeadlineWorkerConfiguration` object
- `fleet`: A `Fleet` object specifying which fleet the worker should join

Returns a `LocalWorkerProcess` object.

#### `local_worker`

A **session-scoped** convenience fixture that creates a single local worker using the default fleet from `deadline_resources.fleet`. The worker persists for the entire test session.

### Function-Scoped Fixtures (For Fresh Workers)

#### `function_local_worker_factory`

A **function-scoped** factory fixture that creates fresh local worker processes for each test function. Use this when you need clean worker state for each test.

#### `function_local_worker`

A **function-scoped** convenience fixture that creates a fresh local worker for each test function.

## Usage Examples

### Session-Scoped Usage (Recommended)

```python
def test_my_worker_behavior(
    deadline_resources: DeadlineResources,
    worker_config: DeadlineWorkerConfiguration,
    local_worker_factory: Callable[[DeadlineWorkerConfiguration, Fleet], LocalWorkerProcess],
) -> None:
    # Create a session-scoped local worker with a specific fleet
    worker = local_worker_factory(
        config=worker_config,
        fleet=deadline_resources.scaling_fleet,
    )
    
    # Test worker behavior
    assert worker.is_running()
    
    # Worker persists for the entire test session
    # Cleanup happens automatically at session end
```

### Function-Scoped Usage (Fresh Workers)

```python
def test_my_worker_behavior_fresh(
    deadline_resources: DeadlineResources,
    worker_config: DeadlineWorkerConfiguration,
    function_local_worker_factory: Callable[[DeadlineWorkerConfiguration, Fleet], LocalWorkerProcess],
) -> None:
    # Create a fresh local worker for this test only
    worker = function_local_worker_factory(
        config=worker_config,
        fleet=deadline_resources.scaling_fleet,
    )
    
    # Test worker behavior
    assert worker.is_running()
    
    # Worker is cleaned up after this test function
```

### Custom Configuration

```python
def test_worker_with_custom_config(
    deadline_resources: DeadlineResources,
    worker_config: DeadlineWorkerConfiguration,
    local_worker_factory: Callable[[DeadlineWorkerConfiguration, Fleet], LocalWorkerProcess],
) -> None:
    # Modify the configuration
    custom_config = dataclasses.replace(
        worker_config,
        retain_session_dir=True,
        cleanup_session_user_processes=False,
    )
    
    # Create worker with custom config
    worker = local_worker_factory(
        config=custom_config,
        fleet=deadline_resources.fleet,
    )
    
    # Test with custom configuration
    assert worker.is_running()
```

### Using the Convenience Fixtures

```python
def test_session_worker(
    local_worker: LocalWorkerProcess,  # Session-scoped
) -> None:
    # Session worker is already created and running
    assert local_worker.is_running()
    
    # Access worker properties
    logs = local_worker.get_logs()
    assert isinstance(logs, str)
    
    # Worker persists across multiple tests in the session

def test_function_worker(
    function_local_worker: LocalWorkerProcess,  # Function-scoped
) -> None:
    # Fresh worker created for this test
    assert function_local_worker.is_running()
    
    # This worker is cleaned up after this test
```

## LocalWorkerProcess Methods

- `is_running()`: Check if the worker process is still running
- `stop()`: Stop the worker process gracefully
- `get_logs()`: Get the worker log content as a string

## LocalWorkerProcess Properties

- `process`: The underlying `subprocess.Popen` object
- `config_file`: Path reference (worker is configured via environment variables)
- `persistence_dir`: Path to the worker persistence directory
- `logs_dir`: Path to the worker logs directory
- `fleet`: The Fleet object the worker is configured for

## Environment Variables

The fixture respects the same environment variables as other worker fixtures:

- `WORKER_AGENT_WHL_PATH`: Path to a specific worker agent wheel file
- `WORKER_AGENT_REQUIREMENT_SPECIFIER`: PEP 508 requirement specifier for the worker agent

## Notes

### Session-Scoped Fixtures (Default)
- Workers persist for the entire test session, improving test performance
- Automatic cleanup happens at the end of the test session
- Ideal for test suites where worker state can be shared across tests
- More efficient for large test suites

### Function-Scoped Fixtures
- Fresh workers created for each test function
- Automatic cleanup after each test function
- Use when you need clean worker state for each test
- Slightly slower due to worker creation/cleanup overhead

### Configuration Method
- Workers are configured entirely through environment variables
- No config file is created or required
- All worker settings are passed via `DEADLINE_WORKER_*` environment variables
- This approach avoids the need for config file path overrides

### General
- Each worker gets its own temporary directories for persistence and logs
- The fixture handles graceful shutdown with fallback to force kill if needed
- Workers run in the same Python environment as the test suite
- Suitable for testing worker configuration and behavior without infrastructure overhead

## Recent Changes

### Fixed Config File Issue
Previously, the fixture attempted to pass a config file via `--config-path` command line argument, but the worker agent doesn't support this parameter. The fixture now uses environment variables for all configuration, which is the supported method for overriding worker settings.

## Limitations

- Requires the worker agent source code to be available in the test environment
- May not perfectly replicate production deployment scenarios
- Limited to testing on the same machine/OS as the test runner
- Does not test cross-network communication scenarios that EC2/Docker workers provide