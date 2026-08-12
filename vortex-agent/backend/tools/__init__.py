"""
Vortex Tool Ecosystem — proper capability layer (MCP-inspired)

Structure:
tools/
├── filesystem/
├── browser/
├── shell/
├── github/
├── database/
├── web/
├── code/
├── communication/
└── external/

Each tool declares:
name, description, input_schema, output_schema, permissions, risk_level, timeout, rollback_method

Governance decides whether Vortex can call it.

Backward compatibility: exposes TOOL_CLASSES, ToolResult, and TOOL_CLASSES legacy symbols so old `from tools import ...` keeps working.
"""
from .base import ToolCapability, ToolResult
from .legacy import TOOL_CLASSES, GlossopetraeTool, SteganographyTool, CodeForgeTool
from .registry import ToolRegistry

# Re-export extended lists for convenience
try:
    from .filesystem import FILESYSTEM_TOOLS
except: FILESYSTEM_TOOLS = []
try:
    from .shell import SHELL_TOOLS
except: SHELL_TOOLS = []
try:
    from .web import WEB_TOOLS
except: WEB_TOOLS = []
try:
    from .code import CODE_TOOLS
except: CODE_TOOLS = []
try:
    from .browser import BROWSER_TOOLS
except: BROWSER_TOOLS = []
try:
    from .github import GITHUB_TOOLS
except: GITHUB_TOOLS = []
try:
    from .database import DATABASE_TOOLS
except: DATABASE_TOOLS = []
try:
    from .communication import COMM_TOOLS
except: COMM_TOOLS = []
try:
    from .external import EXTERNAL_TOOLS
except: EXTERNAL_TOOLS = []

ALL_TOOLS = []
for lst in [TOOL_CLASSES, FILESYSTEM_TOOLS, SHELL_TOOLS, WEB_TOOLS, CODE_TOOLS, BROWSER_TOOLS, GITHUB_TOOLS, DATABASE_TOOLS, COMM_TOOLS, EXTERNAL_TOOLS]:
    ALL_TOOLS.extend(lst)

def get_registry(governance=None) -> ToolRegistry:
    return ToolRegistry(governance=governance)

__all__ = [
    "ToolCapability", "ToolResult",
    "TOOL_CLASSES",
    "GlossopetraeTool", "SteganographyTool", "CodeForgeTool",
    "ToolRegistry", "get_registry",
    "ALL_TOOLS",
]
