"""Windows asyncio compatibility shim.

psycopg's async driver cannot use Windows' default ProactorEventLoop.
Importing this module switches the event loop policy to SelectorEventLoop
on Windows. No-op on other platforms.

Import at the top of every async entry point that touches the database:
    from src.core import asyncio_compat  # noqa: F401
"""

from __future__ import annotations

import asyncio
import sys

if sys.platform.startswith("win"):
    # Only set the policy once; subsequent imports are no-ops.
    current = asyncio.get_event_loop_policy()
    if not isinstance(current, asyncio.WindowsSelectorEventLoopPolicy):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
