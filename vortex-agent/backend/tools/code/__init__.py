"""Code capability — extended codeforge with sandbox"""
from ..legacy import CodeForgeTool
import ast, tempfile, subprocess, sys, os
from pathlib import Path
from ..base import ToolResult
from paths import vortex_home

WORKSPACE = vortex_home() / "workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)

class CodeAnalyzeTool:
    name = "code.analyze"
    description = "Static analysis of Python code"
    input_schema = {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}
    permissions = ["read"]
    risk_level = "low"
    timeout = 5
    category = "code"
    @staticmethod
    def execute(code: str) -> ToolResult:
        try:
            tree = ast.parse(code)
            funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            imports = [n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import) for _ in [1]]
            return ToolResult("success", {"functions": funcs, "imports": imports, "lines": len(code.splitlines())}, "Analyzed")
        except SyntaxError as e:
            return ToolResult("error", {}, f"Syntax error: {e}")

class CodeTestTool:
    name = "code.test"
    description = "Run pytest/unittest on a code snippet that contains tests"
    input_schema = {"type": "object", "properties": {"code": {"type": "string"}, "timeout": {"type": "integer", "default": 15}}, "required": ["code"]}
    permissions = ["execute"]
    risk_level = "medium"
    timeout = 20
    category = "code"
    @staticmethod
    def execute(code: str, timeout: int = 15) -> ToolResult:
        # reuse codeforge sandbox but include test running
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=str(WORKSPACE))
        try:
            tmp.write(code)
            tmp.close()
            proc = subprocess.run([sys.executable, "-I", tmp.name], capture_output=True, text=True, timeout=timeout, cwd=str(WORKSPACE))
            out = proc.stdout[:4000] + proc.stderr[:2000]
            if proc.returncode == 0:
                return ToolResult("success", {"output": out}, "Tests passed")
            return ToolResult("error", {"output": out}, f"Tests failed exit {proc.returncode}")
        except subprocess.TimeoutExpired:
            return ToolResult("error", {}, f"Timeout after {timeout}s")
        finally:
            try:
                os.unlink(tmp.name)
            except:
                pass

CODE_TOOLS = [CodeAnalyzeTool, CodeTestTool, CodeForgeTool]
