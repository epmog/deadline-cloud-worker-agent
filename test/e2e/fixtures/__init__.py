# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Test fixtures for e2e tests.
"""

from .local_worker import (
    LocalWorkerProcess, 
    local_worker_factory, 
    local_worker,
    function_local_worker_factory,
    function_local_worker,
)

__all__ = [
    "LocalWorkerProcess",
    "local_worker_factory",  # Session-scoped factory
    "local_worker",          # Session-scoped convenience fixture
    "function_local_worker_factory",  # Function-scoped factory
    "function_local_worker",          # Function-scoped convenience fixture
]