"""Database capability — sqlite queries on memory"""
from ..base import ToolResult
import sqlite3
from paths import vortex_home

class DbQueryTool:
    name = "database.query"
    description = "Query Vortex memory.db (read-only SELECT)"
    input_schema = {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}
    permissions = ["read"]
    risk_level = "medium"
    timeout = 5
    category = "database"
    @staticmethod
    def execute(sql: str) -> ToolResult:
        # only allow SELECT
        if not sql.strip().lower().startswith("select"):
            return ToolResult("error", {}, "Only SELECT allowed")
        try:
            db = vortex_home() / "memory.db"
            conn = sqlite3.connect(str(db))
            rows = conn.execute(sql).fetchall()
            conn.close()
            return ToolResult("success", {"rows": rows[:50], "count": len(rows)}, f"Query returned {len(rows)} rows")
        except Exception as e:
            return ToolResult("error", {}, f"Query failed: {e}")

DATABASE_TOOLS = [DbQueryTool]
