"""Vortex swarm: VortexAgent (the OS) + VortexBot (teammates) — upgraded to Council + Sovereign + Governance + Orchestration + Resolution + Observability."""
import re
import time
from typing import Dict, Any, Optional

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
    # try math compilation first
    try:
        from self_improve import compile_math
        cm = compile_math(msg)
        if cm:
            # extract inner code from print(...)
            # cm is like "print(6 * 7)"
            inner = cm[len("print("):-1] if cm.startswith("print(") else cm
            return cm
    except:
        pass
    m = re.search(r"(?:calculate|compute|eval)\s+(.+)", msg, re.I)
    if m:
        expr = m.group(1).strip().rstrip('?.!')
        # attempt to translate times etc via compile_math
        try:
            from self_improve import compile_math
            cm2 = compile_math(f"calculate {expr}")
            if cm2:
                return cm2
        except:
            pass
        return f"print({expr})"
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

        # hybrid memory recall
        ctx = []
        try:
            # vector recall
            ctx = self.agent.vector.recall(f"{self.role} {message}", n=2)
        except:
            ctx = []
        # enhanced recall from new memory system if available
        try:
            if hasattr(self.agent.memory, 'recall'):
                enhanced = self.agent.memory.recall(f"{self.role} {message}", n=2)
                ctx.extend([str(r)[:100] for r in enhanced[:2]])
        except:
            pass

        if self.role == "orchestrator":
            reply = self._chief(message)
        elif self.role == "improve":
            reply = self._improve(message)
        else:
            self._route_source = None
            route = self._route(message, ctx)
            source = self._route_source or "builtin"
            if not route:
                learned = self.agent.rsi.suggest_route(message, self.role)
                if learned:
                    route = (learned[0], learned[1])
                    source = "learned"
            if route:
                tool_name, args = route
                # governance check before tool execution
                try:
                    if self.agent.governance:
                        dec = self.agent.governance.evaluate(task=f"bot:{self.name} tool:{tool_name}", context={"tool": tool_name, "args": args, "agent": self.name}, agent=self.name, action="execute")
                        if dec["action"] == "DENY":
                            result = ToolResult("error", {}, f"Governance DENY: {dec['reason']}")
                        else:
                            result = self._call(tool_name, args)
                    else:
                        result = self._call(tool_name, args)
                except:
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
                try:
                    self.agent._turn_rescued = True
                except Exception:
                    pass

        self.agent.memory.save_message(f"bot:{self.name}", reply)
        self.agent.vector.remember(f"[{self.name}/{self.role}] {message} -> {reply[:200]}")
        # also store in new memory system
        try:
            if hasattr(self.agent.memory, 'agent_memory'):
                self.agent.memory.agent_memory.remember(self.name, f"{message[:80]} -> {reply[:120]}", kind="interaction")
        except:
            pass

        self.agent.rsi.observe(
            task=message, reply=reply, bot=self.name,
            tool=self._last.get("tool"), status=self._last.get("status"),
            route=self._last.get("route"),
            latency_ms=int((time.time() - t0) * 1000),
            rescued=bool(self._last.get("rescued")),
        )
        return reply

    # ── chief: now can use orchestration graph for complex tasks ──
    def _chief(self, message):
        low = message.lower().strip()

        # slash commands routed to specialists (unchanged)
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

        # If explicit orchestrate prefix, use full graph (avoid recursion on auto-detect)
        if low.startswith("orchestrate:") and self.agent.graph:
            try:
                goal = message[len("orchestrate:"):].strip() or message
                return self.agent.run_orchestrated(goal, original_message=message)
            except Exception as e:
                print(f"[chief] orchestration fallback: {e}")
                # fallback to legacy

        # Rapid path: learned/compiled intent beats multi-bot plan
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
            # Phase 3: chief reasons for real before falling back to the greeting.
            # This is the main entry point (/api/chat + CLI), so a canned answer here
            # was the most visible symptom of the missing brain.
            try:
                from reasoning import llm_route, llm_role_reply
                route = llm_route(message, "general")
                if route:
                    tool_name, args = route
                    result = self._call(tool_name, args)
                    if result.status == "error":
                        retry = self.agent.rsi.retry_tool(tool_name, args, result.message)
                        if retry:
                            result, _ = retry
                    self._last = {"tool": tool_name, "status": result.status, "route": "llm"}
                    return f"🧬 reasoned route → {tool_name}\n" + self._format(tool_name, result)
                smart = llm_role_reply("general", "vortex", message)
                if smart:
                    return smart
            except Exception:
                pass

            # check sovereign objectives for context
            sov_ctx = ""
            try:
                if self.agent.sovereign:
                    sov_ctx = f"\nSovereign: {self.agent.sovereign.identity.whoami()} | top priority: {self.agent.sovereign.priorities.top()}"
            except:
                pass
            return ("🌪️ Chief here. I coordinate the swarm: researcher, architect, cipher, improver. "
                    "Give me a task that spans research/build/security and I'll delegate and merge. "
                    "Say /improve to inspect rapid self-improvement, or /evolve to run a cycle." + sov_ctx)

        # Council deliberation via explicit orchestration graph node (avoid recursion in chief)
        # Auto-council disabled for stability; council available via /api/council/deliberate and orchestration graph
        if False and self.agent.council and len(plan) >= 2:
            pass

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
        try:
            self.agent._turn_steps.append(f"delegate → {bot_name}: {task[:80]}")
        except Exception:
            pass
        return self.agent.bots[bot_name].handle(task, from_bot=self.name)

    # ── improver bot ──
    def _improve(self, message):
        low = message.lower()
        if any(k in low for k in ("cycle", "evolve", "now", "run", "/evolve")):
            cycle = self.agent.rsi.run_cycle()
            decision = cycle["decision"]
            icon = "🚀" if decision == "promoted" else "↩️"
            evo = cycle.get("evolution")
            evo_txt = f"\nEvolution: {evo.get('decision')} {evo.get('reason','')[:100]}" if evo else ""
            return (f"{icon} Improvement cycle {decision}.\n"
                    f"{cycle['notes']}{evo_txt}\n\n{self.agent.rsi.report()}")
        if "eval" in low:
            if "benchmark" in low or "vortex" in low:
                try:
                    from evals import VortexBenchmark
                    vb = VortexBenchmark(self.agent)
                    res = vb.run_comprehensive(persist=False)
                    from evals import format_suite
                    return format_suite(res)
                except Exception as e:
                    return f"benchmark error: {e}"
            from evals import format_suite, run_suite
            return format_suite(run_suite(self.agent, name="manual"))
        if "council" in low and self.agent.council:
            return f"🏛️ Council members: {list(self.agent.council.members.keys())}\nWeights: {self.agent.council.weights}"
        if "governance" in low and self.agent.governance:
            pol = self.agent.governance.policy.list_policies()
            return f"⚖️ Governance policies: {len(pol)} active\n" + "\n".join(f"  • {p['name']} → {p['action']}" for p in pol[:6])
        if "sovereign" in low and self.agent.sovereign:
            ctx = self.agent.sovereign.context()
            return f"👑 Sovereign: {ctx['identity'].get('name')} | mode={ctx['state'].get('mode')} | objectives={len(ctx['objectives'])}"
        return ("🧬 Improver online. I close the loop: observe → rescue → "
                "reflect → eval → promote.\n\n" + self.agent.rsi.report() +
                "\n\nSay 'run cycle' to mutate and keep only score gains.\n"
                "Try: eval benchmark / council / governance / sovereign")

    # ── specialist routing ──
    def _route(self, msg, ctx=None):
        low = msg.lower()
        code = _extract_code(msg)
        if code:
            return "codeforge", {"code": code}

        # Phase 3: semantic routing via LLM (no-op when unconfigured)
        try:
            from reasoning import llm_route
            smart = llm_route(msg, self.role, ctx)
            if smart:
                self._route_source = "llm"
                return smart
        except Exception:
            pass

        if self.role == "coding":
            learned = self.agent.rsi.suggest_route(msg, self.role)
            if learned:
                return learned[0], learned[1]
            # math compilation
            try:
                from self_improve import compile_math, compile_fib
                cm = compile_math(msg)
                if cm:
                    return "codeforge", {"code": cm}
                if "fibonacci" in low:
                    fib = compile_fib(msg)
                    if fib:
                        return "codeforge", {"code": fib}
            except:
                pass
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
        # Phase 3: real reasoning when a model is configured; templates otherwise.
        try:
            from reasoning import llm_role_reply
            smart = llm_role_reply(self.role, self.name, message, ctx)
            if smart:
                return smart
        except Exception:
            pass

        ctx_txt = "\n".join(f"   • {c[:100]}" for c in ctx) if ctx else ""
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

        # per-turn accounting so skill capture knows how complex this turn was
        try:
            self.agent._turn_tool_calls += 1
            self.agent._turn_steps.append(f"{self.name}: {tool_name}({str(args)[:60]})")
        except Exception:
            pass
        self.agent.memory.log_event("tool_call", f"{self.name}:{tool_name}:{result.status}")
        if result.status == "error":
            self.agent.bugs.add({"bot": self.name, "tool": tool_name,
                                 "symptoms": [result.message[:60]], "fix": "review args"})
        if tool_name == "steganography" and args.get("action") == "encode" and result.status == "success":
            self.agent.memory.set_kv("last_stego", result.data["encoded"])

        # observability
        try:
            if self.agent.observability:
                self.agent.observability.metrics.record_tool_call(tool_name, result.status, 0)
        except:
            pass

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
    """The OS: owns bots, memory, vector store, skills, bugs, plus new layers."""
    def __init__(self, memory):
        self.memory = memory
        from vector_memory import VectorMemory
        from skills import SkillLibrary, BugLibrary
        self.vector = VectorMemory()
        self.skills = SkillLibrary()
        self.bugs = BugLibrary()
        self.bots = {}
        self.rsi = RapidSelfImprovement(self)

        # per-turn accounting for autonomous skill capture
        self._turn_tool_calls = 0
        self._turn_steps = []
        self._turn_rescued = False
        self.skill_manager = None
        try:
            from skill_manage import SkillManager
            self.skill_manager = SkillManager(self)
        except Exception as e:
            print(f"[agent] skill manager not loaded: {e}")

        self.code_evolution = None

        # ── new layers (import lazily to avoid circular) ──
        self.governance = None
        self.sovereign = None
        self.council = None
        self.resolver = None
        self.graph = None
        self.observability = None
        self.tool_registry = None
        self.state_manager = None

        try:
            from governance import Governance
            self.governance = Governance(memory=self.memory)
        except Exception as e:
            print(f"[agent] governance not loaded: {e}")

        try:
            from sovereign import Sovereign
            self.sovereign = Sovereign(memory=self.memory)
        except Exception as e:
            print(f"[agent] sovereign not loaded: {e}")

        try:
            from council import VortexCouncil
            self.council = VortexCouncil(agent=self, memory=self.memory, governance=self.governance)
        except Exception as e:
            print(f"[agent] council not loaded: {e}")

        try:
            from resolution import VortexResolver
            self.resolver = VortexResolver(memory=self.memory, governance=self.governance)
        except Exception as e:
            print(f"[agent] resolver not loaded: {e}")

        try:
            from observability import Observability
            self.observability = Observability(memory=self.memory)
        except Exception as e:
            print(f"[agent] observability not loaded: {e}")

        try:
            from tools import get_registry
            self.tool_registry = get_registry(governance=self.governance)
        except Exception as e:
            print(f"[agent] tool registry not loaded: {e}")

        try:
            from code_evo_init import init_code_evolution
            init_code_evolution(self)
        except Exception as e:
            print(f"[agent] code evolution not loaded: {e}")

        try:
            from orchestration import StateManager, create_default_graph
            self.state_manager = StateManager()
            # graph uses agent, memory, tools, governance, resolver, council
            self.graph = create_default_graph(
                agent=self,
                memory=self.memory,
                tools=self.tool_registry.tools if self.tool_registry else {t.name: t for t in TOOL_CLASSES},
                governance=self.governance,
                resolver=self.resolver,
                council=self.council,
                observability=self.observability
            )
        except Exception as e:
            print(f"[agent] orchestration graph not loaded: {e}")

        # spawn legacy bots + council specialist bots mapping
        for name, role in [("chief", "orchestrator"), ("researcher", "research"),
                           ("architect", "coding"), ("cipher", "security"),
                           ("improver", "improve")]:
            self.spawn_bot(name, role, quiet=True)

        # additional council roles as bots for richer deliberation (optional)
        council_bots = [
            ("planner", "planning"),
            ("critic", "critic"),
            ("strategist", "strategy"),
            ("verifier", "verification"),
        ]
        for name, role in council_bots:
            if name not in self.bots:
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

        # Hermes-inspired: durable session turn + autonomous profile capture
        try:
            if getattr(self.memory, "sessions", None):
                self.memory.sessions.record("user", message)
        except Exception:
            pass
        try:
            self.capture_profile_facts(message)
        except Exception:
            pass

        # observability trace start
        trace_id = None
        if self.observability:
            try:
                trace_id = self.observability.tracer.start_trace(goal=message, generation_id=self.memory.current_generation())
            except:
                pass

        reply = self.bots["chief"].handle(message)

        # observability finish
        if self.observability and trace_id:
            try:
                self.observability.tracer.finish_trace(trace_id, final_outcome=reply[:200], score=0.7)
                self.observability.metrics.inc("chat_total")
            except:
                pass

        # sovereign lifecycle awareness
        if self.sovereign:
            try:
                self.sovereign.state.add_learning(f"chat: {message[:60]} -> {reply[:60]}")
            except:
                pass

        # record the reply for cross-session recall
        try:
            if getattr(self.memory, "sessions", None):
                self.memory.sessions.record("assistant", reply)
        except Exception:
            pass

        # autonomous skill creation after a complex turn (Hermes skill_manage)
        try:
            self.maybe_capture_skill(message, reply)
        except Exception:
            pass

        return reply

    # ── Hermes-inspired capabilities ──
    def capture_profile_facts(self, message: str) -> dict:
        """Self-nudging memory: persist durable facts into MEMORY.md / USER.md."""
        prof = getattr(self.memory, "profile", None)
        if not prof:
            return {}
        from profile_memory import extract_profile_facts
        found = extract_profile_facts(message)
        written = {"user": [], "memory": []}
        for f in found.get("user", []):
            if prof.remember_user(f).get("written"):
                written["user"].append(f)
        for f in found.get("memory", []):
            if prof.remember(f).get("written"):
                written["memory"].append(f)
        return written

    def maybe_capture_skill(self, goal: str, reply: str) -> Optional[dict]:
        """After a complex turn, write down how it was done."""
        if not self.skill_manager:
            return None
        calls = self._turn_tool_calls
        steps = self._turn_steps
        self._turn_tool_calls, self._turn_steps = 0, []
        if not self.skill_manager.is_complex(tool_calls=calls, steps=len(steps),
                                             rescued=self._turn_rescued):
            self._turn_rescued = False
            return None
        self._turn_rescued = False
        return self.skill_manager.capture(
            goal=goal, steps=steps or [f"reply: {reply[:120]}"],
            success="error" not in reply.lower()[:60],
        )

    def recall_sessions(self, query: str, limit: int = 5) -> list:
        """Cross-session keyword recall — 'what did we discuss about X'."""
        if not getattr(self.memory, "sessions", None):
            return []
        return self.memory.sessions.search(query, limit=limit)

    def run_orchestrated(self, goal: str, original_message: str = None) -> str:
        """Full orchestration path: Goal → Understand → Plan → Decompose → Route → Execute → Observe → Evaluate → Recover → Council → Resolution → Complete"""
        if not self.graph:
            return self.chat(goal)

        t0 = time.time()
        state = self.graph.run(goal=goal, original_message=original_message or goal, generation=self.memory.current_generation())

        latency_ms = int((time.time()-t0)*1000)
        # metrics
        if self.observability:
            try:
                self.observability.metrics.observe("orchestration_latency", latency_ms)
                for task in state.tasks:
                    self.observability.metrics.observe("task_latency", task.latency_ms)
            except:
                pass

        final = state.final_response or "Orchestration completed with no final response"
        # add resolution info
        if state.resolution:
            sel = state.resolution.get("selected", {})
            scores = sel.get("scores") or {}
            final += f"\n\n[Resolver selected {sel.get('id','?')} score={sel.get('total_score','?')} | scores={scores}]"

        # governance audit already happens inside tools

        return final

    def council_deliberate(self, goal: str):
        if not self.council:
            return {"error": "council not loaded"}
        return self.council.deliberate(goal=goal)

    def resolve_candidates(self, candidates, goal=""):
        if not self.resolver:
            return {"error": "resolver not loaded"}
        return self.resolver.resolve(candidates, goal=goal)
