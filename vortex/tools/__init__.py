"""Tool package — import side-effects register tools into the central registry."""
from .registry import registry

# Import tool modules so they self-register
from . import (  # noqa: F401
    web_tools,
    file_tools,
    code_tools,
    shell_tools,
    memory_tools,
    crypto_tools,
    meta_tools,
    delegate_tool,
)

__all__ = ["registry"]
