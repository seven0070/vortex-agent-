"""Vortex Prime — Phase 1 orchestrator. Routes tasks to tools."""
import re
from tools import TOOL_CLASSES, ToolResult

CODE_BLOCK = re.compile(r"```(?:python)?\s*(.*?)```", re.S)


class VortexPrime:
    def __init__(self, memory):
        self.memory = memory
        self.tools = {t.name: t for t in TOOL_CLASSES}
        self.name = "vortex"

    # ── public entry point ──
    def handle(self, message: str) -> dict:
        self.memory.save_message("user", message)
        tool_calls = []

        route = self._route(message)
        if route:
            tool_name, args = route
            result = self._call_tool(tool_name, args)
            tool_calls.append({"tool": tool_name, "status": result.status,
                               "summary": result.message})
            response = self._format_tool_reply(tool_name, result)
        else:
            response = self._converse(message)

        self.memory.save_message("assistant", response,
                                 meta={"tool_calls": tool_calls})
        return {"response": response, "tool_calls": tool_calls}

    # ── tool execution + logging ──
    def _call_tool(self, tool_name: str, args: dict) -> ToolResult:
        tool = self.tools[tool_name]
        try:
            result = tool.execute(**args)
        except Exception as e:
            result = ToolResult("error", {}, f"Tool crashed: {e}")
        self.memory.log_event("tool_call", f"{tool_name}:{result.status}")
        if tool_name == "steganography" and args.get("action") == "encode" \
                and result.status == "success":
            self.memory.set_kv("last_stego", result.data["encoded"])
        return result

    # ── routing: decide which tool (if any) ──
    def _route(self, msg: str):
        m = msg.strip()
        low = m.lower()

        # explicit slash commands (deterministic)
        if low.startswith("/translate"):
            return "glossopetrae", {"text": m[len("/translate"):].strip(" :") or "the warrior sees the mountain"}
        if low.startswith("/run"):
            return "codeforge", {"code": self._extract_code(m) or "print('hello vortex')"}
        if low.startswith("/hide"):
            payload, cover = self._split_hide(m[len("/hide"):].strip())
            return "steganography", {"action": "encode", "payload": payload, "cover": cover}
        if low.startswith("/reveal"):
            stego = m[len("/reveal"):].strip() or self.memory.get_kv("last_stego") or ""
            return "steganography", {"action": "decode", "stego": stego}

        # natural-language heuristics
        code = self._extract_code(m)
        if code and any(k in low for k in ("run", "execute", "calculate", "compute", "eval")):
            return "codeforge", {"code": code}
        if any(k in low for k in ("translate", "conlang", "obfuscate")):
            text = re.sub(r"^(please\s+)?(translate|conlang|obfuscate)\w*\s*:?\s*", "", m, flags=re.I)
            return "glossopetrae", {"text": text or m}
        if any(k in low for k in ("hide", "encode", "steg")) and "payload" not in low:
            payload, cover = self._split_hide(re.sub(r"^(please\s+)?(hide|encode)\s*", "", m, flags=re.I))
            return "steganography", {"action": "encode", "payload": payload, "cover": cover}
        if any(k in low for k in ("reveal", "decode", "extract")):
            stego = self.memory.get_kv("last_stego") or ""
            if "<!--STEGO:" in m:
                stego = m
            return "steganography", {"action": "decode", "stego": stego}

        return None

    # ── helpers ──
    @staticmethod
    def _extract_code(msg: str):
        m = CODE_BLOCK.search(msg)
        if m:
            return m.group(1).strip()
        m = re.search(r"(?:calculate|compute|eval)\s+(.+)", msg, re.I)
        if m:
            return f"print({m.group(1).strip().rstrip('?.!')})"
        return None

    @staticmethod
    def _split_hide(rest: str):
        rest = rest.strip(" :")
        if "|" in rest:
            payload, _, cover = rest.partition("|")
            return payload.strip(), cover.strip()
        if " in " in rest:
            payload, _, cover = rest.partition(" in ")
            return payload.strip(), cover.strip()
        return rest, ""

    def _format_tool_reply(self, tool_name: str, r: ToolResult) -> str:
        if r.status != "success":
            return f"⚠️ {tool_name} failed: {r.message}"
        if tool_name == "glossopetrae":
            return f"🗿 Glossopetrae: {r.data['translated']}"
        if tool_name == "steganography":
            if "encoded" in r.data:
                return f"🔐 Hidden payload:\n{r.data['encoded']}"
            return f"🔓 Revealed: {r.data.get('decoded', '')}"
        if tool_name == "codeforge":
            return f"⚙️ Output:\n{r.data.get('output', '(no output)')}"
        return r.message

    def _converse(self, msg: str) -> str:
        low = msg.lower()
        if "who are you" in low or "help" in low:
            return ("I'm Vortex, your Phase-1 agent. I can:\n"
                    "  /translate <text>      — conlang + SVG\n"
                    "  /hide <payload> | <cover> — steganography\n"
                    "  /reveal                — decode last payload\n"
                    "  /run <code>            — sandboxed Python")
        if "hello" in low or "hi" in low:
            return "🌪️ Hello. The core brain is online. Try /help."
        # Phase 3: answer for real when a model is configured.
        try:
            from reasoning import llm_role_reply
            smart = llm_role_reply("general", "vortex", message)
            if smart:
                return smart
        except Exception:
            pass
        return ("🌪️ Understood. No LLM provider is configured, so I'm running in "
                "deterministic tool mode — set VORTEX_LLM_PROVIDER + an API key to enable "
                "live reasoning. My tools are ready — try /help.")
