"""
Pytest fixtures for unitMail tests.

This module provides common fixtures used across test modules.
"""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class FeatureTestResults:
    """Track test results for feature verification tests."""

    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []

    def add_pass(self, test_name, details=""):
        self.passed.append((test_name, details))

    def add_fail(self, test_name, error):
        self.failed.append((test_name, str(error)))

    def add_warning(self, test_name, message):
        self.warnings.append((test_name, message))


@pytest.fixture
def results():
    """Provide a FeatureTestResults instance for tracking test outcomes."""
    return FeatureTestResults()
