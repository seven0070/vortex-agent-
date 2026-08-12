"""LLM brain — multi-provider + offline ReAct planner (Hermes runtime_provider spirit)."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional


SYSTEM_HINT = "Follow the tool protocol. JSON only."


class LLMBrain:
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

    def chat(self, messages: List[Dict[str, str]], tools_desc: str = "", system: str = "") -> str:
        if self.provider == "offline":
            return OfflinePlanner().plan(messages, tools_desc)
        try:
            if self.provider == "openai":
                return self._openai(messages, system or SYSTEM_HINT)
            if self.provider == "anthropic":
                return self._anthropic(messages, system or SYSTEM_HINT)
            if self.provider == "openai_compat":
                return self._compat(messages, system or SYSTEM_HINT)
        except Exception as e:
            return json.dumps(
                {
                    "thought": f"LLM error ({e}); finishing best-effort.",
                    "action": "finish",
                    "args": {"result": f"Provider error: {e}"},
                }
            )
        return OfflinePlanner().plan(messages, tools_desc)

    def _openai(self, messages, system) -> str:
        from urllib import request

        body = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [{"role": "system", "content": system}, *messages],
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
        with request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]

    def _compat(self, messages, system) -> str:
        from urllib import request

        base = os.getenv("VORTEX_BASE_URL", "").rstrip("/")
        body = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [{"role": "system", "content": system}, *messages],
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
        with request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]

    def _anthropic(self, messages, system) -> str:
        from urllib import request

        anth = [
            {"role": m["role"] if m["role"] != "system" else "user", "content": m["content"]}
            for m in messages
            if m["role"] != "system"
        ]
        body = {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": 0.2,
            "system": system,
            "messages": anth,
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
        with request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
        return data["content"][0]["text"]


def parse_action(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    if m:
        raw = m.group(1)
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
    return {"thought": "", "action": "finish", "args": {"result": raw}}


# ── Offline planner ─────────────────────────────────────────────────────────
class OfflinePlanner:
    def plan(self, messages: List[Dict[str, str]], tools_desc: str = "") -> str:
        raw_goal, observations = "", []
        for m in messages:
            c = m.get("content") or ""
            if m["role"] == "user" and c.startswith("Observation:"):
                observations.append(c)
            elif m["role"] == "user" and not raw_goal:
                raw_goal = c
        goal = self._clean(raw_goal)

        if observations and self._done(goal, observations):
            return json.dumps(
                {
                    "thought": "Enough information to finish.",
                    "action": "finish",
                    "args": {"result": self._summarize(goal, observations)},
                }
            )

        # opportunistic fetch after live search
        if observations:
            last = observations[-1]
            if (
                '"results"' in last
                and "Offline knowledge" not in last
                and not any("Fetched" in o for o in observations)
            ):
                um = re.search(r'https?://[^\\"\s]+', last)
                if um:
                    return json.dumps(
                        {
                            "thought": "Fetching top search hit.",
                            "action": "http_fetch",
                            "args": {"url": um.group(0)},
                        }
                    )

        fetch_bonus = sum(1 for o in observations if "Fetched" in o)
        step = max(0, len(observations) - fetch_bonus)
        plan = self._build(goal.lower(), goal)
        if step < len(plan):
            action, args, thought = plan[step]
            return json.dumps({"thought": thought, "action": action, "args": args})

        summary = (
            self._summarize(goal, observations)
            if observations
            else (
                "No concrete tool path. Try: research X and write a report, "
                "calculate 2**20, hide secret in cover text, or run python code."
            )
        )
        return json.dumps(
            {
                "thought": "Plan exhausted.",
                "action": "finish",
                "args": {"result": summary},
            }
        )

    @staticmethod
    def _clean(raw: str) -> str:
        if not raw:
            return ""
        m = re.search(
            r"GOAL:\s*(.+?)(?:\nWorkspace:|\nComplete this goal|\nSystem:|\Z)",
            raw,
            re.S | re.I,
        )
        return m.group(1).strip() if m else raw.strip()

    def _build(self, goal: str, original: str) -> List[tuple]:
        plan: List[tuple] = []

        m = re.search(
            r"(?:calculate|compute|eval|what is|what's)\s+(.+?)(?:\?|$)",
            original,
            re.I,
        )
        bare = re.fullmatch(r"[\d\s+\-*/%^().]+", original.strip())
        if (
            m
            or bare
            or any(k in goal for k in ("calculate", "compute", "math", "fibonacci", "fib("))
            or re.search(r"\d+\s*[\+\-\*/^]\s*\d+", original)
        ):
            if "fibonacci" in goal or re.search(r"\bfib\b", goal):
                n = 90
                nm = re.search(r"fib(?:onacci)?\s*\(?\s*(\d+)", goal)
                if nm:
                    n = int(nm.group(1))
                code = (
                    "import time\ndef fib(n):\n a,b=0,1\n"
                    " for _ in range(n): a,b=b,a+b\n return a\n"
                    f"t=time.time(); r=fib({n}); print(f'fib({n})={{r}} in {{time.time()-t:.5f}}s')"
                )
                plan.append(("execute_code", {"code": code}, f"Benchmark fib({n})."))
            else:
                expr = m.group(1).strip().rstrip("?.!") if m else self._expr(original)
                plan.append(("calculator", {"expression": expr or original.strip()}, f"Eval {expr}"))
            return plan

        code = self._code(original)
        if code or any(k in goal for k in ("run code", "execute", "python", "script")):
            plan.append(
                ("execute_code", {"code": code or "print('hello from vortex')"}, "Run Python.")
            )
            return plan

        if any(k in goal for k in ("hide", "steganograph", "conceal", "encode secret")):
            payload, cover = self._hide(original)
            plan.append(
                (
                    "steganography",
                    {"action": "encode", "payload": payload, "cover": cover},
                    "Hide payload.",
                )
            )
            return plan
        if any(k in goal for k in ("reveal", "decode", "extract secret")):
            plan.append(
                ("steganography", {"action": "decode", "stego": original}, "Reveal payload.")
            )
            return plan

        if any(k in goal for k in ("translate", "conlang", "obfuscate", "glossopetrae")):
            text = re.sub(
                r"^(please\s+)?(translate|conlang|obfuscate)\w*\s*:?\s*",
                "",
                original,
                flags=re.I,
            )
            plan.append(("glossopetrae", {"text": text or original}, "Conlang translate."))
            return plan

        if any(
            k in goal
            for k in (
                "research", "investigate", "find out", "look up", "search",
                "analyze", "analyse", "report", "summarize", "what is", "who is", "explain",
            )
        ):
            topic = self._topic(original)
            plan.append(("web_search", {"query": topic, "max_results": 5}, f"Search: {topic}"))
            plan.append(
                (
                    "write_file",
                    {
                        "path": f"reports/{self._slug(topic)}.md",
                        "content": "",
                        "from_research": True,
                    },
                    "Write research report.",
                )
            )
            plan.append(
                (
                    "memory_store",
                    {"text": f"Researched: {topic}", "from_research": True, "tag": "research"},
                    "Remember findings.",
                )
            )
            return plan

        if any(k in goal for k in ("list files", "ls ", "show files", "workspace")):
            plan.append(("list_files", {"path": "."}, "List workspace."))
            return plan

        if any(k in goal for k in ("system info", "uname", "disk", "whoami", "hostname")):
            plan.append(
                (
                    "terminal",
                    {"command": "uname -a && whoami && df -h / | tail -1"},
                    "System intel.",
                )
            )
            return plan

        if any(k in goal for k in ("remember", "note that", "save note")):
            plan.append(("memory_store", {"text": original}, "Store note."))
            return plan
        if any(k in goal for k in ("recall", "what do you know", "memory")):
            plan.append(("memory_recall", {"query": original}, "Recall memory."))
            return plan

        # Council — multi-domain / deliberate goals
        if any(
            k in goal
            for k in (
                "council",
                "deliberate",
                "debate",
                "pros and cons",
                "weigh",
                "committee",
                "vote on",
                "should we",
            )
        ) or (
            sum(
                1
                for k in (
                    "research",
                    "build",
                    "secure",
                    "strategy",
                    "design",
                    "risk",
                )
                if k in goal
            )
            >= 2
        ):
            plan.append(
                (
                    "convene_council",
                    {"goal": original, "auto_execute": True},
                    "Convene the Agent Council to deliberate and execute.",
                )
            )
            return plan

        if any(k in goal for k in ("build", "create", "make", "automate", "delegate")):
            topic = self._topic(original)
            plan.append(("web_search", {"query": topic, "max_results": 3}, f"Research {topic}"))
            plan.append(
                (
                    "write_file",
                    {
                        "path": f"plans/{self._slug(topic)}.md",
                        "content": "",
                        "from_research": True,
                    },
                    "Draft plan.",
                )
            )
            plan.append(
                (
                    "execute_code",
                    {"code": f"print('Vortex scaffold: {topic[:50]}')\nprint('status=ready')"},
                    "Smoke test.",
                )
            )
            return plan

        plan.append(("web_search", {"query": original[:120], "max_results": 5}, "Search goal."))
        plan.append(
            (
                "memory_store",
                {"text": f"User asked: {original[:200]}", "tag": "query"},
                "Remember query.",
            )
        )
        return plan

    @staticmethod
    def _code(msg: str) -> Optional[str]:
        m = re.search(r"```(?:python)?\s*(.*?)```", msg, re.S)
        return m.group(1).strip() if m else None

    @staticmethod
    def _expr(msg: str) -> str:
        cands = re.findall(r"[0-9]+(?:\s*[+\-*/%^()]\s*[0-9]+)+", msg)
        if cands:
            return max(cands, key=len).strip()
        m = re.search(r"([0-9]+(?:\s*[+\-*/%^().eE]\s*[0-9]+)*)", msg)
        return m.group(1).strip() if m else msg.strip() or "2+2"

    @staticmethod
    def _hide(msg: str):
        rest = re.sub(
            r"^(please\s+)?(hide|secure|encrypt|conceal)\s*", "", msg, flags=re.I
        ).strip(" :")
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
            p, _, c = rest.partition("|")
            return p.strip(), c.strip()
        if " in " in rest:
            p, _, c = rest.partition(" in ")
            p = re.sub(r"^payload\s+", "", p, flags=re.I).strip()
            return p, c.strip()
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
        return s[:48] or "note"

    @staticmethod
    def _done(goal: str, observations: List[str]) -> bool:
        ok = any(o.lower().startswith("observation: ok") for o in observations)
        joined = " ".join(observations).lower()
        if not ok and "error" in joined:
            return len(observations) >= 3
        g = goal.lower()
        # council tool is one-shot (deliberation + exec inside)
        if any(k in g for k in ("council", "deliberate", "debate", "committee")) or "convene_council" in joined:
            return ok and len(observations) >= 1
        if any(k in g for k in ("research", "report", "analyze", "analyse", "investigate", "build", "create")):
            return any("wrote " in o.lower() for o in observations) or len(observations) >= 3
        return ok and len(observations) >= 1

    @staticmethod
    def _summarize(goal: str, observations: List[str]) -> str:
        lines = ["## Autonomous result", f"**Goal:** {goal}", "", "### Steps taken"]
        for i, obs in enumerate(observations, 1):
            body = re.sub(r"^Observation:\s*", "", obs).strip()
            lines.append(f"{i}. {body[:500]}")
        lines.append("")
        lines.append("### Summary")
        last = re.sub(r"^Observation:\s*", "", observations[-1]).strip() if observations else ""
        m = re.search(r"Result\s*=\s*([^\s|]+)", last)
        if m:
            lines.append(f"Answer: **{m.group(1)}**")
            return "\n".join(lines)
        out = re.search(r'"output":\s*"((?:\\.|[^"\\])*)"', last)
        if out:
            lines.append(bytes(out.group(1), "utf-8").decode("unicode_escape").strip())
            return "\n".join(lines)
        enc = re.search(r'"encoded":\s*"((?:\\.|[^"\\])*)"', " ".join(observations))
        if enc:
            lines.append(
                "Hidden payload:\n" + bytes(enc.group(1), "utf-8").decode("unicode_escape")
            )
            return "\n".join(lines)
        sh = re.search(r'"stdout":\s*"((?:\\.|[^"\\])*)"', last)
        if sh:
            lines.append(bytes(sh.group(1), "utf-8").decode("unicode_escape").strip())
            return "\n".join(lines)
        wp = re.search(r"Wrote\s+(\S+)", " ".join(observations))
        if wp:
            lines.append(f"Artifact written to `{wp.group(1)}`.")
            return "\n".join(lines)
        # council payload
        if "council" in last.lower() or "decision" in last.lower():
            cm = re.search(r'"result":\s*"((?:\\.|[^"\\])*)"', last)
            if cm:
                try:
                    lines.append(bytes(cm.group(1), "utf-8").decode("unicode_escape")[:2000])
                    return "\n".join(lines)
                except Exception:
                    pass
            lines.append(last[:2000])
            return "\n".join(lines)
        lines.append(last[:1500] or "Task completed.")
        return "\n".join(lines)
