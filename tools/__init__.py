"""
Tool functions for the agent.

Import all tools from submodules and expose them as a unified list.
"""

import logging
import os

BROWSER_TOOLS = []
SANDBOX_TOOLS = []

# Only load browser tools if PLAYWRIGHT_MCP_URL is configured
if os.getenv("PLAYWRIGHT_MCP_URL"):
    try:
        from tools.browser_session import BROWSER_TOOLS
    except ImportError as e:
        logging.warning(f"Browser tools unavailable (missing dependency): {e}")
        BROWSER_TOOLS = []

# Load sandbox tools if E2B_API_KEY is configured
if os.getenv("E2B_API_KEY"):
    try:
        from tools.code_sandbox import SANDBOX_TOOLS
    except ImportError as e:
        logging.warning(f"Sandbox tools unavailable (missing dependency): {e}")
        SANDBOX_TOOLS = []

# Aggregate all tools from different modules
TOOLS = [
    *BROWSER_TOOLS,
    *SANDBOX_TOOLS,
]

__all__ = ["TOOLS", "BROWSER_TOOLS", "SANDBOX_TOOLS"]
