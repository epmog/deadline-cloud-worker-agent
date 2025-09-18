# macOS Local Worker E2E Tests

This directory contains end-to-end tests specifically designed for macOS systems using the local worker agent fixture.

## Overview

The macOS e2e tests provide an alternative to EC2-based testing by running worker agents directly on the local macOS machine. This is particularly useful for:

- **Local Development**: Test worker functionality without AWS infrastructure
- **CI/CD Pipelines**: Run tests in macOS GitHub Actions or similar environments  
- **Quick Validation**: Faster feedback loop during development
- **Cost Efficiency**: No EC2 instance costs for basic functionality testing

## Test Files

### `test_macos_local_worker_job_submission.py`
Main test file containing macOS-specific job submission tests:

- **`TestMacOSLocalWorkerJobSubmission`**: Core job processing tests
  - `test_macos_local_worker_success_job`: Basic sleep job success test
  - `test_macos_local_worker_custom_script_job`: Custom shell script execution
  - `test_macos_local_worker_with_scaling_fleet`: Scaling fleet configuration
  - `test_macos_local_worker_environment_validation`: Environment setup validation
  - `test_macos_local_worker_logs_accessible`: Log generation and access

- **`TestMacOSLocalWorkerPerformance`**: Performance-focused tests
  - `test_macos_local_worker_startup_time`: Worker startup performance

### `run_macos_tests.py`
Convenient test runner script with environment validation:

```bash
# Run all macOS tests
./test/e2e/run_macos_tests.py

# Run specific test pattern
./test/e2e/run_macos_tests.py -k "success_job"

# Run with output capture disabled (see print statements)
./test/e2e/run_macos_tests.py -s

# Run in quiet mode
./test/e2e/run_macos_tests.py -q
```

## Prerequisites

### System Requirements
- **macOS (Darwin)**: Tests automatically skip on non-macOS systems
- **Python 3.8+**: With pytest installed
- **AWS Credentials**: Configured for Deadline Cloud access

### Environment Variables
Required environment variables (see `test/e2e/config-template.sh`):

```bash
export FARM_ID="farm-1234567890abcdef"
export QUEUE_A_ID="queue-1234567890abcdef" 
export FLEET_ID="fleet-1234567890abcdef"
export SCALING_QUEUE_ID="queue-0987654321fedcba"
export SCALING_FLEET_ID="fleet-0987654321fedcba"
export JOB_STORAGE_PROFILE_ID="sp-1234567890abcdef"
export JOBS_RUN_AS_AGENT_USER_QUEUE_ID="queue-agent123456"
export NON_VALID_ROLE_QUEUE_ID="queue-invalid123456"
```

### Python Dependencies
```bash
pip install pytest deadline-test-fixtures
```

## Running Tests

### Method 1: Using the Runner Script (Recommended)
```bash
# From project root
./test/e2e/run_macos_tests.py
```

The runner script will:
- ✅ Validate macOS environment
- ✅ Check required environment variables  
- ✅ Verify pytest availability
- 🚀 Run tests with appropriate options

### Method 2: Direct pytest
```bash
# From project root
pytest test/e2e/test_macos_local_worker_job_submission.py -v
```

### Method 3: Specific Test Classes
```bash
# Run only job submission tests
pytest test/e2e/test_macos_local_worker_job_submission.py::TestMacOSLocalWorkerJobSubmission -v

# Run only performance tests  
pytest test/e2e/test_macos_local_worker_job_submission.py::TestMacOSLocalWorkerPerformance -v
```

## Test Architecture

### Local Worker Fixture Integration
Tests use the session-scoped `local_worker_factory` fixture from `test/e2e/fixtures/local_worker.py`:

```python
def test_example(
    deadline_resources: DeadlineResources,
    deadline_client: DeadlineClient, 
    worker_config: DeadlineWorkerConfiguration,
    local_worker_factory: Callable,
) -> None:
    # Create local worker
    worker = local_worker_factory(
        config=worker_config,
        fleet=deadline_resources.fleet,
    )
    
    # Submit and run job
    job = submit_sleep_job("Test Job", deadline_client, ...)
    job.wait_until_complete(client=deadline_client)
    
    assert job.task_run_status == TaskStatus.SUCCEEDED
```

### Key Differences from EC2 Tests
- **No SSH**: Direct process management instead of remote commands
- **Local Filesystem**: Tests run on the same filesystem as the worker
- **Process Lifecycle**: Workers run as local subprocesses
- **Faster Startup**: No EC2 instance provisioning time
- **macOS-Specific**: Tests include macOS-specific commands and validations

## Recent Fixes

### Config File Command Line Argument Issue (Fixed)
**Problem**: The local worker fixture was trying to pass `--config-path` as a command line argument, but the worker agent doesn't support this parameter.

**Solution**: Updated the fixture to use environment variables for all worker configuration instead of config files. The worker agent supports all configuration options via `DEADLINE_WORKER_*` environment variables.

## Troubleshooting

### Common Issues

#### Tests Skip with "Not running on macOS"
```
SKIPPED [1] test_macos_local_worker_job_submission.py:25: macOS-specific tests - only run on Darwin systems
```
**Solution**: These tests only run on macOS. Use EC2 tests on other platforms.

#### Missing Environment Variables
```
❌ Missing required environment variables:
   - FARM_ID
   - QUEUE_A_ID
```
**Solution**: Source the configuration file:
```bash
source test/e2e/config-template.sh
```

#### Worker Startup Failures
```
RuntimeError: Worker process failed to start. Output: ...
```
**Solutions**:
- Check AWS credentials are configured
- Verify environment variables point to valid resources
- Check worker agent source code is available
- Review worker logs in temporary directories

#### Permission Issues
```
PermissionError: [Errno 13] Permission denied
```
**Solutions**:
- Ensure current user has write permissions
- Check temporary directory permissions
- Verify Python executable permissions

### Debug Mode
Run tests with output capture disabled to see detailed logs:
```bash
./test/e2e/run_macos_tests.py -s
```

Or with pytest directly:
```bash
pytest test/e2e/test_macos_local_worker_job_submission.py -s -v --log-cli-level=DEBUG
```

### Log Locations
Local worker logs are stored in temporary directories:
```
/tmp/local_worker_<random>/logs/
```

Access logs programmatically in tests:
```python
logs = worker.get_logs()
print(f"Worker logs: {logs}")
```

## Integration with CI/CD

### GitHub Actions Example
```yaml
name: macOS E2E Tests
on: [push, pull_request]

jobs:
  macos-tests:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements-test.txt
          
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-west-2
          
      - name: Run macOS E2E tests
        env:
          FARM_ID: ${{ secrets.FARM_ID }}
          QUEUE_A_ID: ${{ secrets.QUEUE_A_ID }}
          FLEET_ID: ${{ secrets.FLEET_ID }}
          SCALING_QUEUE_ID: ${{ secrets.SCALING_QUEUE_ID }}
          SCALING_FLEET_ID: ${{ secrets.SCALING_FLEET_ID }}
        run: ./test/e2e/run_macos_tests.py
```

## Contributing

When adding new macOS-specific tests:

1. **Use the `@pytest.mark.skipif` decorator** to ensure tests only run on macOS
2. **Include macOS-specific validations** where appropriate (e.g., `sw_vers` commands)
3. **Use the local worker factory** for consistent worker management
4. **Add appropriate logging** for debugging
5. **Update this README** if adding new test categories

### Example Test Template
```python
@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="macOS-specific tests - only run on Darwin systems"
)
def test_new_macos_feature(
    deadline_resources: DeadlineResources,
    deadline_client: DeadlineClient,
    worker_config: DeadlineWorkerConfiguration,
    local_worker_factory: Callable,
) -> None:
    """Test description for new macOS feature."""
    
    # GIVEN - Setup
    worker = local_worker_factory(config=worker_config, fleet=deadline_resources.fleet)
    assert worker.is_running()
    
    # WHEN - Action
    job = submit_custom_job("Test Name", deadline_client, ...)
    
    # THEN - Verification  
    job.wait_until_complete(client=deadline_client)
    assert job.task_run_status == TaskStatus.SUCCEEDED
```