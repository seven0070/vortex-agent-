"""Vortex swarm: VortexAgent (the OS) + VortexBot (teammates)."""
import re
import time

from self_improve import RapidSelfImprovement, is_weak
from tools import TOOL_CLASSES, ToolResult

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
        self.message_count = 0
        self._last = {}

    # ── entry point ──
    def handle(self, message, from_bot=None):
        self.message_count += 1
        self._last = {}
        t0 = time.time()
        ctx = self.agent.vector.recall(f"{self.role} {message}", n=2)

        if self.role == "orchestrator":
            reply = self._chief(message)
        elif self.role == "improve":
            reply = self._improve(message)
        else:
            route = self._route(message)
            source = "builtin"
            if not route:
                learned = self.agent.rsi.suggest_route(message, self.role)
                if learned:
                    route = (learned[0], learned[1])
                    source = "learned"
            if route:
                tool_name, args = route
                result = self._call(tool_name, args)
                if result.status == "error":
                    retry = self.agent.rsi.retry_tool(tool_name, args, result.message)
                    if retry:
                        result, _mut = retry
                        source = "retry"
                self._last = {"tool": tool_name, "status": result.status, "route": source}
                reply = self._format(tool_name, result)
            else:
                reply = self._role_reply(message, ctx)

        if is_weak(reply):
            pack = self.agent.rsi.rescue(message, reply, self.name)
            if pack:
                reply = "🧬 Rescued mid-turn (learned this for next time):\n" + \
                        self._format(pack["tool"], pack["result"])
                self._last = {
                    "tool": pack["tool"], "status": "success",
                    "route": "rescue", "rescued": True,
                }

        self.agent.memory.save_message(f"bot:{self.name}", reply)
        self.agent.vector.remember(f"[{self.name}/{self.role}] {message} -> {reply[:200]}")
        self.agent.rsi.observe(
            task=message, reply=reply, bot=self.name,
            tool=self._last.get("tool"), status=self._last.get("status"),
            route=self._last.get("route"),
            latency_ms=int((time.time() - t0) * 1000),
            rescued=bool(self._last.get("rescued")),
        )
        return reply

    # ── chief: plan + delegate + merge ──
    def _chief(self, message):
        low = message.lower()

        # Phase-1 slash commands, routed to specialists
        if low.startswith("/translate"):
            return self._delegate("cipher", message)
        if low.startswith("/run"):
            rest = message[4:].strip()
            code = _extract_code(message) or rest or "print('hello vortex')"
            return self._delegate("architect", f"```python\n{code}\n```")
        if low.startswith("/hide") or low.startswith("/reveal"):
            return self._delegate("cipher", message)
        if low.startswith("/improve") or low.startswith("/evolve") \
                or low.startswith("/rsi") or low.startswith("/lessons"):
            return self._delegate("improver", message)
        if any(k in low for k in ("self-improve", "self improve", "rapid improve",
                                  "evolve yourself", "run rsi")):
            return self._delegate("improver", message)

        # Rapid path: a learned/compiled intent beats a multi-bot plan
        learned = self.agent.rsi.suggest_route(message, self.role)
        if learned:
            tool_name, args, meta = learned
            result = self._call(tool_name, args)
            if result.status == "error":
                retry = self.agent.rsi.retry_tool(tool_name, args, result.message)
                if retry:
                    result, _ = retry
            self._last = {
                "tool": tool_name, "status": result.status,
                "route": meta.get("kind", "learned"),
            }
            tag = "learned" if meta.get("kind") == "learned" else "compiled"
            return f"🧬 {tag} route → {tool_name}\n" + self._format(tool_name, result)

        plan = self._plan(message)
        if not plan:
            return ("🌪️ Chief here. I coordinate the swarm: researcher, architect, cipher, improver. "
                    "Give me a task that spans research/build/security and I'll delegate and merge. "
                    "Say /improve to inspect rapid self-improvement, or /evolve to run a cycle.")

        parts, findings = [], []
        # run non-cipher bots first
        for bot_name, task in plan:
            if bot_name == "cipher":
                continue
            sub = self._delegate(bot_name, task)
            parts.append((bot_name, sub))
            findings.append(sub)

        # cipher secures the combined findings
        if any(b == "cipher" for b, _ in plan):
            payload = " FINDINGS: " + " | ".join(findings)[:400]
            sub = self._delegate("cipher", "hide" + payload)
            parts.append(("cipher", sub))

        # save the successful delegation as a shared skill
        self.agent.skills.save(
            "multi_bot_analysis",
            "Delegate analysis + build + secure across the swarm, then merge.",
            [n for n, _ in parts],
        )

        merged = "\n\n".join(f"━━ [{n}] ━━\n{r}" for n, r in parts)
        return f"🧩 Merged swarm result:\n\n{merged}"

    def _plan(self, message):
        low = message.lower()
        plan = []
        if any(k in low for k in ("research", "analyze", "analyse", "find", "investigate")):
            plan.append(("researcher", message))
        if any(k in low for k in ("code", "build", "write", "script", "benchmark",
                                  "calculate", "fibonacci", "performance")):
            plan.append(("architect", message))
        if any(k in low for k in ("secure", "hide", "encrypt", "secret", "steg")):
            plan.append(("cipher", message))
        return plan

    def _delegate(self, bot_name, task):
        if bot_name not in self.agent.bots:
            return f"(bot '{bot_name}' offline)"
        print(f"   📨 {self.name} → {bot_name}: {task[:60]}")
        self.agent.memory.log_event("delegate", f"{self.name}->{bot_name}:{task[:60]}")
        return self.agent.bots[bot_name].handle(task, from_bot=self.name)

    # ── improver bot ──
    def _improve(self, message):
        low = message.lower()
        if any(k in low for k in ("cycle", "evolve", "now", "run", "/evolve")):
            cycle = self.agent.rsi.run_cycle()
            decision = cycle["decision"]
            icon = "🚀" if decision == "promoted" else "↩️"
            return (f"{icon} Improvement cycle {decision}.\n"
                    f"{cycle['notes']}\n\n{self.agent.rsi.report()}")
        if "eval" in low:
            from evals import format_suite, run_suite
            return format_suite(run_suite(self.agent, name="manual"))
        return ("🧬 Improver online. I close the loop: observe → rescue → "
                "reflect → eval → promote.\n\n" + self.agent.rsi.report() +
                "\n\nSay 'run cycle' to mutate and keep only score gains.")

    # ── specialist routing ──
    def _route(self, msg):
        low = msg.lower()
        code = _extract_code(msg)
        if code:
            return "codeforge", {"code": code}

        if self.role == "coding":
            learned = self.agent.rsi.suggest_route(msg, self.role)
            if learned:
                return learned[0], learned[1]
            if any(k in low for k in ("benchmark", "performance")) and "fibonacci" in low:
                return "codeforge", {"code": FIB_BENCH}
            if "fibonacci" in low:
                from self_improve import compile_fib
                fib = compile_fib(msg)
                if fib:
                    return "codeforge", {"code": fib}
                return "codeforge", {"code": FIB_BENCH}
            return None

        if self.role == "security":
            if any(k in low for k in ("reveal", "decode", "extract")):
                return "steganography", {"action": "decode",
                                         "stego": self.agent.memory.get_kv("last_stego") or msg}
            if any(k in low for k in ("translate", "obfuscate", "conlang")):
                text = re.sub(r"^(please\s+)?(translate|obfuscate|conlang)\w*\s*:?\s*", "", msg, flags=re.I)
                return "glossopetrae", {"text": text or msg}
            payload, cover = _split_hide(re.sub(r"^/?(hide|secure|encrypt)\s*", "", msg, flags=re.I))
            return "steganography", {"action": "encode", "payload": payload or msg, "cover": cover}

        return None

    def _role_reply(self, message, ctx):
        ctx_txt = "\n".join(f"   • {c[:100]}" for c in ctx)
        if self.role == "research":
            return (f"🔍 Researcher findings on '{message[:50]}':\n"
                    f"- primary signal detected\n- secondary correlation noted\n"
                    + (f"Recall from memory:\n{ctx_txt}" if ctx_txt else ""))
        if self.role == "coding":
            return f"🏗️ Architect: plan drafted for '{message[:50]}'. Provide code or say 'benchmark'."
        if self.role == "security":
            return f"🔒 Cipher standing by. Say 'hide <payload>' or 'translate <text>'."
        if self.role == "improve":
            return self.agent.rsi.report()
        return f"[{self.name}] ack: {message[:50]}"

    # ── tool execution + bug learning ──
    def _call(self, tool_name, args):
        tool = self.tools[tool_name]
        try:
            result = tool.execute(**args)
        except Exception as e:
            result = ToolResult("error", {}, f"Tool crashed: {e}")
        self.agent.memory.log_event("tool_call", f"{self.name}:{tool_name}:{result.status}")
        if result.status == "error":
            self.agent.bugs.add({"bot": self.name, "tool": tool_name,
                                 "symptoms": [result.message[:60]], "fix": "review args"})
        if tool_name == "steganography" and args.get("action") == "encode" and result.status == "success":
            self.agent.memory.set_kv("last_stego", result.data["encoded"])
        return result

    def _format(self, tool_name, r):
        if r.status != "success":
            return f"⚠️ {tool_name} failed: {r.message}"
        if tool_name == "glossopetrae":
            return f"🗿 Glossopetrae: {r.data['translated']}"
        if tool_name == "steganography":
            return f"🔐 Hidden:\n{r.data['encoded']}" if "encoded" in r.data else f"🔓 Revealed: {r.data.get('decoded')}"
        if tool_name == "codeforge":
            return f"⚙️ Output:\n{r.data.get('output', '(no output)')}"
        return r.message


class VortexAgent:
    """The OS: owns bots, memory, vector store, skills, bugs."""
    def __init__(self, memory):
        self.memory = memory
        from vector_memory import VectorMemory
        from skills import SkillLibrary, BugLibrary
        self.vector = VectorMemory()
        self.skills = SkillLibrary()
        self.bugs = BugLibrary()
        self.bots = {}
        self.rsi = RapidSelfImprovement(self)
        for name, role in [("chief", "orchestrator"), ("researcher", "research"),
                           ("architect", "coding"), ("cipher", "security"),
                           ("improver", "improve")]:
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
        return [{"name": b.name, "role": b.role, "messages": b.message_count, "status": "active"}
                for b in self.bots.values()]

    def chat(self, message):
        self.memory.save_message("user", message)
        return self.bots["chief"].handle(message)
