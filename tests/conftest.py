"""Shared pytest fixtures and path setup.

Adds ``src/`` to ``sys.path`` so the engine modules can be imported as
top-level modules (e.g. ``import quant_engine``) without installing the package.
All tests here exercise pure logic only — no network, DB, or API keys.
"""

import os
import sys

import pytest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


@pytest.fixture
def rising_prices():
    """A clean monotonically rising price series."""
    return [float(p) for p in range(100, 160)]


@pytest.fixture
def falling_prices():
    """A clean monotonically falling price series."""
    return [float(p) for p in range(160, 100, -1)]
