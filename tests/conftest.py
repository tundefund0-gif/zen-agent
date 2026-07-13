"""Shared fixtures and configuration for tests."""
import os
import pytest

from config import config

# Exclude stress test from pytest collection
collect_ignore = ["stress_test.py"]

has_opencode = bool(os.environ.get("OPENGATE_API_KEY"))
has_composio = bool(os.environ.get("COMPOSIO_API_KEY"))
has_all_keys = has_opencode and has_composio

skip_if_no_opencode = pytest.mark.skipif(not has_opencode, reason="OPENGATE_API_KEY not set")
skip_if_no_composio = pytest.mark.skipif(not has_composio, reason="COMPOSIO_API_KEY not set")
skip_if_no_keys = pytest.mark.skipif(not has_all_keys, reason="API keys not set")
