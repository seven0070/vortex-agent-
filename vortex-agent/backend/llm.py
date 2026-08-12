"""LLM brain — OpenAI / Anthropic when keyed, offline planner otherwise."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional


SYSTEM_PROMPT = """You are Vortex, an autonomous multi-agent AI system.
You plan carefully, use tools, observe results, and iterate until the goal is done.
Be concise. Prefer concrete actions over chatter.
When using tools, reply ONLY with a JSON object:
{"thought":"...","action":"tool_name","args":{...}}
When the goal is complete (or you need to answer the user), reply ONLY with:
{"thought":"...","action":"finish","args":{"result":"your final answer"}}
Available tools will be listed in the user message.
Never invent tool results — always call tools to get real data.
"""


class LLMBrain:
    """Thin multi-provider client with a capable offline fallback."""

    def __init__(self):
        self.provider = "offline"
        self.model = os.getenv("VORTEX_MODEL", "")
        self.api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("VORTEX_API_KEY")
            or ""
        )
        if os.getenv("OPENAI_API_KEY"):
            self.provider = "openai"
            self.model = self.model or "gpt-4o-mini"
        elif os.getenv("ANTHROPIC_API_KEY"):
            self.provider = "anthropic"
            self.model = self.model or "claude-3-5-haiku-latest"
        elif os.getenv("VORTEX_API_KEY") and os.getenv("VORTEX_BASE_URL"):
            self.provider = "openai_compat"
            self.model = self.model or "gpt-4o-mini"

    def chat(
        self,
        messages: List[Dict[str, str]],
        tools_desc: str = "",
        temperature: float = 0.2,
    ) -> str:
        if self.provider == "offline":
            return self._offline(messages, tools_desc)
        try:
            if self.provider == "openai":
                return self._openai(messages, tools_desc, temperature)
            if self.provider == "anthropic":
                return self._anthropic(messages, tools_desc, temperature)
            if self.provider == "openai_compat":
                return self._openai_compat(messages, tools_desc, temperature)
        except Exception as e:
            return json.dumps(
                {
                    "thought": f"LLM error ({e}); finishing with best effort.",
                    "action": "finish",
                    "args": {"result": f"Provider error: {e}"},
                }
            )
        return self._offline(messages, tools_desc)

    # ── providers ──────────────────────────────────────────────────────────
    def _openai(self, messages, tools_desc, temperature) -> str:
        from urllib import request

        body = {
            "model": self.model,
            "temperature": temperature,
            "messages": self._with_system(messages, tools_desc),
        }
        req = request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]

    def _openai_compat(self, messages, tools_desc, temperature) -> str:
        from urllib import request

        base = os.getenv("VORTEX_BASE_URL", "").rstrip("/")
        body = {
            "model": self.model,
            "temperature": temperature,
            "messages": self._with_system(messages, tools_desc),
        }
        req = request.Request(
            f"{base}/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]

    def _anthropic(self, messages, tools_desc, temperature) -> str:
        from urllib import request

        sys_msg = SYSTEM_PROMPT
        if tools_desc:
            sys_msg += f"\n\nTools:\n{tools_desc}"
        anth_msgs = [
            {"role": m["role"] if m["role"] != "system" else "user", "content": m["content"]}
            for m in messages
            if m["role"] != "system"
        ]
        body = {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": temperature,
            "system": sys_msg,
            "messages": anth_msgs,
        }
        req = request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(body).encode(),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        return data["content"][0]["text"]

    @staticmethod
    def _with_system(messages, tools_desc) -> List[Dict[str, str]]:
        sys = SYSTEM_PROMPT
        if tools_desc:
            sys += f"\n\nTools:\n{tools_desc}"
        out = [{"role": "system", "content": sys}]
        for m in messages:
            if m["role"] == "system":
                continue
            out.append(m)
        return out

    # ── offline planner (no API key required) ──────────────────────────────
    def _offline(self, messages: List[Dict[str, str]], tools_desc: str) -> str:
        """Heuristic ReAct planner that works fully offline."""
        raw_goal = ""
        observations: List[str] = []
        for m in messages:
            if m["role"] == "user" and m["content"].startswith("Observation:"):
                observations.append(m["content"])
            elif m["role"] == "user" and not raw_goal:
                raw_goal = m["content"]

        user_goal = self._clean_goal(raw_goal)

        # Already have enough observations → finish
        if len(observations) >= 1 and self._looks_done(user_goal, observations):
            summary = self._summarize(user_goal, observations)
            return json.dumps(
                {
                    "thought": "I have enough information to answer.",
                    "action": "finish",
                    "args": {"result": summary},
                }
            )

        # After a successful web_search with real URLs, deepen via http_fetch once
        if observations:
            last = observations[-1]
            already_fetched = any("Fetched" in o for o in observations)
            if (
                not already_fetched
                and '"results"' in last
                and "Offline knowledge" not in last
            ):
                um = re.search(r'https?://[^\\"\s]+', last)
                if um:
                    return json.dumps(
                        {
                            "thought": "Top search hit looks useful — fetching the page.",
                            "action": "http_fetch",
                            "args": {"url": um.group(0)},
                        }
                    )

        goal = user_goal.lower()
        # Static plan index ignores opportunistic http_fetch observations
        fetch_bonus = sum(1 for o in observations if "Fetched" in o)
        plan_step = max(0, len(observations) - fetch_bonus)

        plan = self._build_plan(goal, user_goal)
        if plan_step < len(plan):
            action, args, thought = plan[plan_step]
            return json.dumps({"thought": thought, "action": action, "args": args})

        summary = self._summarize(user_goal, observations) if observations else (
            "I couldn't find a concrete tool path for that goal. "
            "Try being more specific — e.g. 'research X and write a report', "
            "'calculate 2**20', 'hide secret in cover text', or 'run python code'."
        )
        return json.dumps(
            {
                "thought": "Plan exhausted; returning best result.",
                "action": "finish",
                "args": {"result": summary},
            }
        )

    @staticmethod
    def _clean_goal(raw: str) -> str:
        """Strip the autonomous runner wrapper down to the user's goal text."""
        if not raw:
            return ""
        m = re.search(r"GOAL:\s*(.+?)(?:\nWorkspace:|\nComplete this goal|\Z)", raw, re.S | re.I)
        if m:
            return m.group(1).strip()
        return raw.strip()

    def _build_plan(self, goal: str, original: str) -> List[tuple]:
        """Return ordered (action, args, thought) steps."""
        plan: List[tuple] = []

        # math / calculate / bare arithmetic
        m = re.search(
            r"(?:calculate|compute|eval|what is|what's)\s+(.+?)(?:\?|$)",
            original,
            re.I,
        )
        bare_math = re.fullmatch(r"[\d\s+\-*/%^().]+", original.strip())
        if (
            m
            or bare_math
            or any(op in goal for op in ("calculate", "compute", "math", "fibonacci", "fib("))
            or re.search(r"\d+\s*[\+\-\*/^]\s*\d+", original)
        ):
            if "fibonacci" in goal or re.search(r"\bfib\b", goal):
                n = 90
                nm = re.search(r"fib(?:onacci)?\s*\(?\s*(\d+)", goal)
                if nm:
                    n = int(nm.group(1))
                code = (
                    "import time\n"
                    "def fib(n):\n"
                    "    a,b=0,1\n"
                    "    for _ in range(n): a,b=b,a+b\n"
                    "    return a\n"
                    f"t=time.time(); r=fib({n}); "
                    f"print(f'fib({n})={{r}} in {{time.time()-t:.5f}}s')"
                )
                plan.append(("codeforge", {"code": code}, f"Benchmark fib({n}) via CodeForge."))
            else:
                expr = m.group(1).strip().rstrip("?.!") if m else self._extract_expr(original)
                expr = expr or original.strip()
                plan.append(
                    ("calculator", {"expression": expr}, f"Evaluate expression: {expr}")
                )
            return plan

        # code execution
        code = self._extract_code(original)
        if code or any(k in goal for k in ("run code", "execute", "python", "script")):
            plan.append(
                (
                    "codeforge",
                    {"code": code or "print('hello from vortex')"},
                    "Run the provided Python in the sandbox.",
                )
            )
            return plan

        # steganography
        if any(k in goal for k in ("hide", "steganograph", "conceal", "encode secret")):
            payload, cover = self._split_hide(original)
            plan.append(
                (
                    "steganography",
                    {"action": "encode", "payload": payload, "cover": cover},
                    "Hide the payload inside cover text.",
                )
            )
            return plan
        if any(k in goal for k in ("reveal", "decode", "extract secret")):
            plan.append(
                (
                    "steganography",
                    {"action": "decode", "stego": original},
                    "Reveal any hidden payload.",
                )
            )
            return plan

        # conlang / translate
        if any(k in goal for k in ("translate", "conlang", "obfuscate", "glossopetrae")):
            text = re.sub(
                r"^(please\s+)?(translate|conlang|obfuscate)\w*\s*:?\s*",
                "",
                original,
                flags=re.I,
            )
            plan.append(
                ("glossopetrae", {"text": text or original}, "Translate into the conlang.")
            )
            return plan

        # web research + report pipeline
        if any(
            k in goal
            for k in (
                "research",
                "investigate",
                "find out",
                "look up",
                "search",
                "analyze",
                "analyse",
                "report",
                "summarize",
                "what is",
                "who is",
                "explain",
            )
        ):
            topic = self._topic(original)
            plan.append(
                ("web_search", {"query": topic, "max_results": 5}, f"Search the web for: {topic}")
            )
            # http_fetch is inserted dynamically by the runner when a URL exists
            plan.append(
                (
                    "write_file",
                    {
                        "path": f"reports/{self._slug(topic)}.md",
                        "content": f"# Report: {topic}\n\n(auto-filled from research)\n",
                        "from_research": True,
                    },
                    "Write a structured research report to the workspace.",
                )
            )
            plan.append(
                (
                    "remember",
                    {"text": f"Researched: {topic}", "from_research": True},
                    "Store key findings in long-term memory.",
                )
            )
            return plan

        # file write
        if any(k in goal for k in ("write file", "create file", "save to", "write a")):
            path_m = re.search(r"(?:file|to)\s+[\"']?([\w./-]+\.\w+)", original, re.I)
            path = path_m.group(1) if path_m else "notes/output.txt"
            content = original
            plan.append(
                (
                    "write_file",
                    {"path": path, "content": content},
                    f"Write content to {path}.",
                )
            )
            return plan

        # list / read files
        if any(k in goal for k in ("list files", "ls ", "show files", "workspace")):
            plan.append(("list_files", {"path": "."}, "List workspace files."))
            return plan
        if "read " in goal or "open file" in goal:
            path_m = re.search(r"(?:read|open)\s+[\"']?([\w./-]+)", original, re.I)
            path = path_m.group(1) if path_m else "notes/output.txt"
            plan.append(("read_file", {"path": path}, f"Read {path}."))
            return plan

        # notes / remember
        if any(k in goal for k in ("remember", "note that", "save note")):
            plan.append(
                ("remember", {"text": original}, "Store this in long-term memory.")
            )
            return plan
        if any(k in goal for k in ("recall", "what do you know", "memory")):
            plan.append(("recall", {"query": original}, "Search long-term memory."))
            return plan

        # shell / system info
        if any(k in goal for k in ("system info", "uname", "disk", "whoami", "hostname")):
            plan.append(
                ("shell", {"command": "uname -a && whoami && df -h / | tail -1"}, "Gather system info.")
            )
            return plan

        # generic multi-bot style goal → research + code + note
        if any(k in goal for k in ("build", "create", "make", "automate", "agent")):
            topic = self._topic(original)
            plan.append(
                ("web_search", {"query": topic, "max_results": 3}, f"Research approach for: {topic}")
            )
            plan.append(
                (
                    "write_file",
                    {
                        "path": f"plans/{self._slug(topic)}.md",
                        "content": f"# Plan: {topic}\n\n## Goal\n{original}\n\n## Steps\n1. Research\n2. Implement\n3. Verify\n",
                        "from_research": True,
                    },
                    "Draft an execution plan in the workspace.",
                )
            )
            plan.append(
                (
                    "codeforge",
                    {
                        "code": (
                            f"print('Vortex autonomous scaffold for: {topic[:60]}')\n"
                            "print('status=ready')\n"
                        )
                    },
                    "Smoke-test a tiny scaffold in the sandbox.",
                )
            )
            return plan

        # fallback: try web search on the raw goal, then finish
        plan.append(
            ("web_search", {"query": original[:120], "max_results": 5}, "Search for relevant info.")
        )
        plan.append(
            (
                "remember",
                {"text": f"User asked: {original[:200]}", "from_research": True},
                "Remember the query context.",
            )
        )
        return plan

    # ── helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def _extract_code(msg: str) -> Optional[str]:
        m = re.search(r"```(?:python)?\s*(.*?)```", msg, re.S)
        if m:
            return m.group(1).strip()
        return None

    @staticmethod
    def _extract_expr(msg: str) -> str:
        # Prefer the longest arithmetic-looking span
        candidates = re.findall(r"[0-9]+(?:\s*[+\-*/%^()]\s*[0-9]+)+", msg)
        if candidates:
            return max(candidates, key=len).strip()
        m = re.search(r"([0-9]+(?:\s*[+\-*/%^().eE]\s*[0-9]+)*)", msg)
        return m.group(1).strip() if m else msg.strip() or "2+2"

    @staticmethod
    def _split_hide(msg: str):
        rest = re.sub(
            r"^(please\s+)?(hide|secure|encrypt|conceal)\s*",
            "",
            msg,
            flags=re.I,
        ).strip(" :")
        # Hide payload 'X' in Y  /  Hide "X" inside Y
        m = re.search(
            r"(?:payload\s+)?['\"]([^'\"]+)['\"]\s+(?:in|inside|within)\s+(.+)",
            rest,
            re.I,
        )
        if m:
            return m.group(1).strip(), m.group(2).strip()
        m = re.search(r"(?:payload\s+)?['\"]([^'\"]+)['\"]", rest, re.I)
        if m:
            return m.group(1).strip(), "The weather is quite pleasant today."
        if "|" in rest:
            payload, _, cover = rest.partition("|")
            return payload.strip(), cover.strip()
        if " in " in rest:
            payload, _, cover = rest.partition(" in ")
            payload = re.sub(r"^payload\s+", "", payload, flags=re.I).strip()
            return payload.strip(), cover.strip()
        rest = re.sub(r"^payload\s+", "", rest, flags=re.I).strip()
        return rest or "secret", "The weather is quite pleasant today."

    @staticmethod
    def _topic(msg: str) -> str:
        cleaned = re.sub(
            r"^(please\s+)?(research|investigate|find out about|look up|search for|"
            r"analyze|analyse|summarize|explain|what is|who is|report on)\s*",
            "",
            msg,
            flags=re.I,
        )
        cleaned = re.sub(r"\s+and\s+(write|create|save|build).*$", "", cleaned, flags=re.I)
        return cleaned.strip(" ?.!:")[:120] or msg[:120]

    @staticmethod
    def _slug(text: str) -> str:
        s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return (s[:48] or "note")

    @staticmethod
    def _looks_done(goal: str, observations: List[str]) -> bool:
        # finish after a successful tool that fully answers simple goals
        joined = " ".join(observations).lower()
        ok = any(
            o.lower().startswith("observation: ok") or " ok —" in o.lower() or o.strip().lower().startswith("ok")
            for o in observations
        )
        errs_only = (not ok) and "error" in joined
        if errs_only:
            return len(observations) >= 3
        g = goal.lower()
        # research / multi-step pipelines
        if any(k in g for k in ("research", "report", "analyze", "analyse", "investigate", "build", "create")):
            wrote = any("wrote " in o.lower() for o in observations)
            return wrote or len(observations) >= 3
        # single-shot tools (calc, code, stego, shell, files…)
        if ok and len(observations) >= 1:
            return True
        return len(observations) >= 2

    @staticmethod
    def _summarize(goal: str, observations: List[str]) -> str:
        lines = ["## Autonomous result", f"**Goal:** {goal}", "", "### Steps taken"]
        for i, obs in enumerate(observations, 1):
            body = re.sub(r"^Observation:\s*", "", obs).strip()
            lines.append(f"{i}. {body[:500]}")
        lines.append("")
        lines.append("### Summary")
        last = re.sub(r"^Observation:\s*", "", observations[-1]).strip() if observations else ""
        # calculator
        m = re.search(r"Result\s*=\s*([^\s|]+)", last)
        if m:
            lines.append(f"Answer: **{m.group(1)}**")
            return "\n".join(lines)
        # codeforge stdout
        out = re.search(r'"output":\s*"((?:\\.|[^"\\])*)"', last)
        if out:
            val = bytes(out.group(1), "utf-8").decode("unicode_escape")
            lines.append(val.strip() or last[:1500])
            return "\n".join(lines)
        # stego encoded
        enc = re.search(r'"encoded":\s*"((?:\\.|[^"\\])*)"', " ".join(observations))
        if enc:
            val = bytes(enc.group(1), "utf-8").decode("unicode_escape")
            lines.append("Hidden payload:\n" + val)
            return "\n".join(lines)
        # shell stdout
        sh = re.search(r'"stdout":\s*"((?:\\.|[^"\\])*)"', last)
        if sh:
            val = bytes(sh.group(1), "utf-8").decode("unicode_escape")
            lines.append(val.strip() or last[:1500])
            return "\n".join(lines)
        # write_file path
        wp = re.search(r"Wrote\s+(\S+)", " ".join(observations))
        if wp:
            lines.append(f"Artifact written to `{wp.group(1)}`.")
            return "\n".join(lines)
        lines.append(last[:1500] or "Task completed.")
        return "\n".join(lines)


def parse_action(raw: str) -> Dict[str, Any]:
    """Extract a structured action from model output."""
    raw = raw.strip()
    # fenced json
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    if m:
        raw = m.group(1)
    # bare json object
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            if "action" in data:
                return {
                    "thought": data.get("thought", ""),
                    "action": data["action"],
                    "args": data.get("args") or data.get("parameters") or {},
                }
        except json.JSONDecodeError:
            pass
    # fallback: treat whole thing as final answer
    return {"thought": "", "action": "finish", "args": {"result": raw}}
