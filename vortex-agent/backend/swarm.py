"""Vortex swarm: VortexAgent (the OS) + VortexBot (teammates) + autonomy."""
from __future__ import annotations

import re
from tools import TOOL_CLASSES, ToolResult, build_toolbelt, run_tool

CODE_BLOCK = re.compile(r"```(?:python)?\s*(.*?)```", re.S)

FIB_BENCH = """
import time
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
t = time.time()
r = fib(90)
print(f"fib(90)={r} in {time.time()-t:.5f}s")
"""


def _extract_code(msg):
    m = CODE_BLOCK.search(msg)
    if m:
        return m.group(1).strip()
    m = re.search(r"(?:calculate|compute|eval)\s+(.+)", msg, re.I)
    if m:
        return f"print({m.group(1).strip().rstrip('?.!')})"
    return None


def _split_hide(rest):
    rest = rest.strip(" :")
    if "|" in rest:
        payload, _, cover = rest.partition("|")
        return payload.strip(), cover.strip()
    if " in " in rest:
        payload, _, cover = rest.partition(" in ")
        return payload.strip(), cover.strip()
    return rest, ""


class VortexBot:
    def __init__(self, agent, name, role):
        self.agent = agent
        self.name = name
        self.role = role
        self.tools = {t.name: t for t in TOOL_CLASSES}
        # also expose extended tools from the shared belt
        for n, t in agent.toolbelt.items():
            self.tools.setdefault(n, t)
        self.message_count = 0

    # ── entry point ──
    def handle(self, message, from_bot=None):
        self.message_count += 1
        ctx = self.agent.vector.recall(f"{self.role} {message}", n=2)

        if self.role == "orchestrator":
            reply = self._chief(message)
        else:
            route = self._route(message)
            if route:
                tool_name, args = route
                result = self._call(tool_name, args)
                reply = self._format(tool_name, result)
            else:
                reply = self._role_reply(message, ctx)

        self.agent.memory.save_message(f"bot:{self.name}", reply)
        self.agent.vector.remember(
            f"[{self.name}/{self.role}] {message} -> {reply[:200]}"
        )
        return reply

    # ── chief: plan + delegate + merge ──
    def _chief(self, message):
        low = message.lower().strip()

        # Kick the full autonomous loop for goal-style requests
        if low.startswith("/auto ") or low.startswith("/mission "):
            goal = message.split(" ", 1)[1].strip()
            return self._run_autonomous(goal)

        if low.startswith("/translate"):
            return self._delegate("cipher", message)
        if low.startswith("/run"):
            return self._delegate("architect", message)
        if low.startswith("/hide") or low.startswith("/reveal"):
            return self._delegate("cipher", message)

        plan = self._plan(message)
        # Complex / multi-step goals → autonomous agent
        if self._wants_autonomy(low, plan):
            return self._run_autonomous(message)

        if not plan:
            return (
                "🌪️ Chief online. I coordinate the swarm and can run fully "
                "autonomous missions.\n"
                "  • Give me a goal (research / build / secure / calculate)\n"
                "  • Or `/auto <goal>` to force the autonomous loop\n"
                "  • Bots: researcher · architect · cipher · scout"
            )

        parts, findings = [], []
        for bot_name, task in plan:
            if bot_name == "cipher":
                continue
            sub = self._delegate(bot_name, task)
            parts.append((bot_name, sub))
            findings.append(sub)

        if any(b == "cipher" for b, _ in plan):
            payload = " FINDINGS: " + " | ".join(findings)[:400]
            sub = self._delegate("cipher", "hide" + payload)
            parts.append(("cipher", sub))

        self.agent.skills.save(
            "multi_bot_analysis",
            "Delegate analysis + build + secure across the swarm, then merge.",
            [n for n, _ in parts],
        )

        merged = "\n\n".join(f"━━ [{n}] ━━\n{r}" for n, r in parts)
        return f"🧩 Merged swarm result:\n\n{merged}"

    def _run_autonomous(self, goal: str) -> str:
        """Run a synchronous autonomous mission and return the result."""
        print(f"   🤖 Launching autonomous mission: {goal[:80]}")
        mission = self.agent.auto.run_sync(goal, max_steps=12)
        status = mission.get("status")
        result = mission.get("result") or mission.get("error") or "(no result)"
        steps = mission.get("step_count", 0)
        header = f"🤖 Autonomous mission [{mission['id']}] — {status} · {steps} steps"
        return f"{header}\n\n{result}"

    @staticmethod
    def _wants_autonomy(low: str, plan) -> bool:
        triggers = (
            "research",
            "investigate",
            "autonomous",
            "on your own",
            "figure out",
            "write a report",
            "build me",
            "create a",
            "look up",
            "find out",
            "full analysis",
            "end to end",
            "end-to-end",
        )
        if any(t in low for t in triggers):
            return True
        # multi-domain plan → better as one autonomous run
        if len(plan) >= 2:
            return True
        return False

    def _plan(self, message):
        low = message.lower()
        plan = []
        if any(
            k in low
            for k in ("research", "analyze", "analyse", "find", "investigate", "search")
        ):
            plan.append(("researcher", message))
        if any(
            k in low
            for k in (
                "code",
                "build",
                "write",
                "script",
                "benchmark",
                "calculate",
                "fibonacci",
                "performance",
            )
        ):
            plan.append(("architect", message))
        if any(k in low for k in ("secure", "hide", "encrypt", "secret", "steg")):
            plan.append(("cipher", message))
        if any(k in low for k in ("browse", "web", "fetch", "url", "scrape")):
            plan.append(("scout", message))
        return plan

    def _delegate(self, bot_name, task):
        if bot_name not in self.agent.bots:
            return f"(bot '{bot_name}' offline)"
        print(f"   📨 {self.name} → {bot_name}: {task[:60]}")
        self.agent.memory.log_event("delegate", f"{self.name}->{bot_name}:{task[:60]}")
        return self.agent.bots[bot_name].handle(task, from_bot=self.name)

    # ── specialist routing ──
    def _route(self, msg):
        low = msg.lower()
        code = _extract_code(msg)
        if code:
            return "codeforge", {"code": code}

        if self.role == "coding":
            if any(k in low for k in ("fibonacci", "benchmark", "performance")):
                return "codeforge", {"code": FIB_BENCH}
            if any(k in low for k in ("calculate", "compute", "math")):
                m = re.search(r"(?:calculate|compute)\s+(.+)", msg, re.I)
                expr = m.group(1).strip().rstrip("?.!") if m else "2+2"
                return "calculator", {"expression": expr}
            return None

        if self.role == "security":
            if any(k in low for k in ("reveal", "decode", "extract")):
                return "steganography", {
                    "action": "decode",
                    "stego": self.agent.memory.get_kv("last_stego") or msg,
                }
            if any(k in low for k in ("translate", "obfuscate", "conlang")):
                text = re.sub(
                    r"^(please\s+)?(translate|obfuscate|conlang)\w*\s*:?\s*",
                    "",
                    msg,
                    flags=re.I,
                )
                return "glossopetrae", {"text": text or msg}
            payload, cover = _split_hide(
                re.sub(r"^(hide|secure|encrypt)\s*", "", msg, flags=re.I)
            )
            return "steganography", {
                "action": "encode",
                "payload": payload or msg,
                "cover": cover,
            }

        if self.role == "research":
            if any(k in low for k in ("search", "research", "find", "look up", "what is")):
                q = re.sub(
                    r"^(please\s+)?(search|research|find|look up|what is)\s*",
                    "",
                    msg,
                    flags=re.I,
                )
                return "web_search", {"query": q or msg, "max_results": 5}
            return None

        if self.role == "scout":
            url_m = re.search(r"https?://\S+", msg)
            if url_m:
                return "http_fetch", {"url": url_m.group(0)}
            return "web_search", {"query": msg, "max_results": 5}

        return None

    def _role_reply(self, message, ctx):
        ctx_txt = "\n".join(f"   • {c[:100]}" for c in ctx)
        if self.role == "research":
            return (
                f"🔍 Researcher on '{message[:50]}':\n"
                f"- ready to search / analyze\n"
                + (f"Recall:\n{ctx_txt}" if ctx_txt else "")
            )
        if self.role == "coding":
            return (
                f"🏗️ Architect: plan drafted for '{message[:50]}'. "
                "Provide code, say 'benchmark', or 'calculate <expr>'."
            )
        if self.role == "security":
            return "🔒 Cipher standing by. Say 'hide <payload>' or 'translate <text>'."
        if self.role == "scout":
            return "🛰️ Scout ready. Give me a query or URL to fetch."
        return f"[{self.name}] ack: {message[:50]}"

    # ── tool execution + bug learning ──
    def _call(self, tool_name, args):
        result = run_tool(self.tools, tool_name, args)
        self.agent.memory.log_event(
            "tool_call", f"{self.name}:{tool_name}:{result.status}"
        )
        if result.status == "error":
            self.agent.bugs.add(
                {
                    "bot": self.name,
                    "tool": tool_name,
                    "symptoms": [result.message[:60]],
                    "fix": "review args",
                }
            )
        if (
            tool_name == "steganography"
            and args.get("action") == "encode"
            and result.status == "success"
        ):
            self.agent.memory.set_kv("last_stego", result.data["encoded"])
        return result

    def _format(self, tool_name, r):
        if r.status != "success":
            return f"⚠️ {tool_name} failed: {r.message}"
        if tool_name == "glossopetrae":
            return f"🗿 Glossopetrae: {r.data['translated']}"
        if tool_name == "steganography":
            return (
                f"🔐 Hidden:\n{r.data['encoded']}"
                if "encoded" in r.data
                else f"🔓 Revealed: {r.data.get('decoded')}"
            )
        if tool_name == "codeforge":
            return f"⚙️ Output:\n{r.data.get('output', '(no output)')}"
        if tool_name == "calculator":
            return f"🧮 {r.data.get('expression')} = {r.data.get('result')}"
        if tool_name == "web_search":
            lines = [f"🔎 Search: {r.data.get('query')}"]
            for item in r.data.get("results") or []:
                lines.append(
                    f"  • {item.get('title')}\n    {item.get('snippet', '')[:160]}\n    {item.get('url', '')}"
                )
            return "\n".join(lines)
        if tool_name == "http_fetch":
            return (
                f"📄 Fetched {r.data.get('url')}:\n"
                f"{(r.data.get('text') or '')[:800]}"
            )
        if tool_name == "write_file":
            return f"📝 Wrote {r.data.get('path')} ({r.data.get('bytes')} bytes)"
        if tool_name == "read_file":
            return f"📖 {r.data.get('path')}:\n{(r.data.get('content') or '')[:800]}"
        if tool_name == "list_files":
            files = r.data.get("files") or []
            listing = "\n".join(
                f"  • {f['path']} ({f['size']}b)" for f in files[:40]
            )
            return f"📁 {r.message}\n{listing}"
        if tool_name == "shell":
            return f"$ exit {r.data.get('code')}\n{r.data.get('stdout', '')}"
        return r.message or str(r.data)


class VortexAgent:
    """The OS: owns bots, memory, vector store, skills, bugs, autonomy."""

    def __init__(self, memory):
        self.memory = memory
        from vector_memory import VectorMemory
        from skills import SkillLibrary, BugLibrary
        from autonomous import AutonomousAgent

        self.vector = VectorMemory()
        self.skills = SkillLibrary()
        self.bugs = BugLibrary()
        self.toolbelt = build_toolbelt(vector=self.vector, memory=memory)
        self.auto = AutonomousAgent(
            memory=memory, vector=self.vector, skills=self.skills, bugs=self.bugs
        )
        self.bots = {}
        for name, role in [
            ("chief", "orchestrator"),
            ("researcher", "research"),
            ("architect", "coding"),
            ("cipher", "security"),
            ("scout", "scout"),
        ]:
            self.spawn_bot(name, role, quiet=True)

    def spawn_bot(self, name, role="general", quiet=False):
        self.bots[name] = VortexBot(self, name, role)
        self.memory.log_event("spawn", name)
        if not quiet:
            print(f"   ✨ Spawned {name} ({role})")
        return self.bots[name]

    def kill_bot(self, name):
        if name in self.bots:
            del self.bots[name]
            self.memory.log_event("kill", name)
            return True
        return False

    def list_bots(self):
        return [
            {
                "name": b.name,
                "role": b.role,
                "messages": b.message_count,
                "status": "active",
            }
            for b in self.bots.values()
        ]

    def chat(self, message):
        self.memory.save_message("user", message)
        return self.bots["chief"].handle(message)
