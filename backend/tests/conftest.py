"""Pytest fixtures for E.L.O backend tests."""

from src.core import asyncio_compat  # noqa: F401  — Windows fix before any async test

import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"
