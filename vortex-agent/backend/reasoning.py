"""
Vortex reasoning — Phase 3 brain wiring.

This is the layer that closes the gap the README used to hand-wave over: instead of
keyword matching and f-string templates, a real model decides *which tool to call* and
*what a specialist actually says*.

Every function here degrades to the previous deterministic behaviour when no LLM is
configured, so nothing regresses when you run offline.

Three capabilities:
  llm_route()        — semantic tool selection (replaces substring matching)
  llm_role_reply()   — a specialist genuinely reasoning in role (replaces templates)
  llm_council_analysis() — council members forming real independent positions
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from llm import get_llm

# ── tool catalogue shown to the router ──
ROUTER_TOOLS = {
    "codeforge": "Execute Python code in a sandbox. Use for ANY math, calculation, "
                 "algorithm, benchmark, fibonacci, data processing, or 'what is X' "
                 "numeric question. You must supply complete runnable code that prints the answer.",
    "glossopetrae": "Translate text into a procedurally generated conlang and render SVG. "
                    "Use ONLY for explicit translate/conlang/obfuscate-language requests.",
    "steganography": "Hide a secret payload inside benign cover text, or decode/reveal one. "
                     "Use ONLY for explicit hide/conceal/encode/reveal/decode requests.",
    "filesystem.read": "Read a file from the workspace. Requires 'path'.",
    "filesystem.write": "Write a file to the workspace. Requires 'path' and 'content'.",
    "filesystem.list": "List files in the workspace.",
    "shell.exec": "Run a sandboxed shell command. Requires 'command'.",
    "code.analyze": "Static analysis of Python source. Requires 'code'.",
    "web.search": "Search local knowledge/memory. Requires 'query'.",
}

ROUTER_SYSTEM = """You are the Vortex router. Map the user's message to exactly one tool call, or to no tool.

Available tools:
{tools}

Rules:
- Any arithmetic, numeric reasoning, algorithm or benchmark -> codeforge with complete Python that PRINTS the result.
- Multi-step reasoning ("if X then Y, how many...") -> codeforge, encode the whole reasoning chain as code that prints the final answer.
- "write/show me code for X" -> codeforge with the code, ending in a print or demo call.
- Only choose glossopetrae or steganography when the user explicitly asks to translate/conlang, or hide/reveal a secret.
- If plain conversation, explanation or opinion is wanted, choose no tool.

Respond with ONLY this JSON:
{{"tool": "<tool name or null>", "args": {{...}}, "reason": "<8 words max>"}}"""

ROLE_SYSTEM = {
    "research": "You are Researcher, a Vortex specialist. Gather facts, cite what you actually know, "
                "flag uncertainty explicitly. Be concrete and concise (under 120 words). Never invent sources.",
    "coding": "You are Architect, a Vortex engineering specialist. Give concrete technical plans, "
              "name real files/functions/trade-offs. Be concise (under 120 words). Prefer specifics over generalities.",
    "security": "You are Cipher, a Vortex security specialist. Assess risk, policy, data exposure and "
                "failure modes. Be concise (under 120 words) and concrete about the actual threat.",
    "general": "You are a Vortex specialist agent. Answer directly, accurately and concisely (under 120 words). "
               "Say plainly when you do not know.",
}

MAX_CODE_CHARS = 4000


def llm_available() -> bool:
    return get_llm().available


def llm_route(message: str, role: str = "general",
              memory_ctx: Optional[List[str]] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Semantic tool routing. Returns (tool_name, args) or None.

    None means "no LLM, or the model chose no tool" — callers keep their existing
    heuristic path, so behaviour is unchanged when unconfigured.

    `memory_ctx` is accepted for interface symmetry but deliberately NOT sent to the
    router. Recalled turns are verbatim past messages, and feeding them in lets an
    earlier request hijack the current routing decision — e.g. after answering a word
    problem, the recalled text made an unrelated "who are you?" re-run the arithmetic.
    Routing is a decision about the message in front of us; memory belongs in the role
    reply, where it informs content instead of tool choice.
    See test_route_ignores_memory_context.
    """
    llm = get_llm()
    if not llm.available or not message.strip():
        return None

    tools_desc = "\n".join(f"- {n}: {d}" for n, d in ROUTER_TOOLS.items())

    data = llm.complete_json(
        ROUTER_SYSTEM.format(tools=tools_desc),
        f"Specialist role: {role}\n\nUser message: {message}",
        temperature=0.0,
    )
    if not isinstance(data, dict):
        return None

    tool = data.get("tool")
    if not tool or str(tool).lower() in ("null", "none", ""):
        return None
    tool = str(tool).strip()
    if tool not in ROUTER_TOOLS:
        return None

    args = data.get("args")
    if not isinstance(args, dict):
        args = {}

    if tool == "codeforge":
        code = args.get("code") or ""
        if not isinstance(code, str) or not code.strip():
            return None
        if len(code) > MAX_CODE_CHARS:
            return None
        if "print" not in code:
            code = code.rstrip() + "\n"
        args = {"code": code}

    return tool, args


def profile_context() -> str:
    """
    Guaranteed context (Hermes Tier 1): MEMORY.md + USER.md, loaded every turn.

    Unlike vector recall this is not probabilistic — if the user told us their name,
    it is in the prompt, every time, with no retrieval step.
    """
    try:
        from profile_memory import ProfileMemory
        return ProfileMemory().context_block()
    except Exception:
        return ""


def llm_role_reply(role: str, name: str, message: str,
                   memory_ctx: Optional[List[str]] = None) -> Optional[str]:
    """A specialist actually reasoning in role. None -> caller uses its template."""
    llm = get_llm()
    if not llm.available or not message.strip():
        return None

    system = ROLE_SYSTEM.get(role, ROLE_SYSTEM["general"])
    prof = profile_context()
    if prof:
        system += f"\n\nAlways-known context:\n{prof}"
    ctx = ""
    if memory_ctx:
        joined = "\n".join(f"- {str(c)[:160]}" for c in memory_ctx[:4])
        ctx = f"\n\nWhat you recall from memory:\n{joined}"

    r = llm.complete(system, f"{message}{ctx}", temperature=0.3)
    if not r:
        return None

    badge = {"research": "🔍", "coding": "🏗️", "security": "🔒"}.get(role, "🤖")
    return f"{badge} {name.capitalize()}: {r.text}"


def llm_council_analysis(role: str, role_prompt: str, goal: str, proposal: str,
                         candidates: Optional[List[Any]] = None) -> Optional[Dict[str, Any]]:
    """
    A council member forming a genuine independent position.

    Returns {"analysis","evidence","confidence"} or None to fall back to heuristics.
    This is what turns "confidence 0.91" from arithmetic-over-templates into a real judgement.
    """
    llm = get_llm()
    if not llm.available or not goal.strip():
        return None

    cand_txt = ""
    if candidates:
        joined = "\n".join(f"- {str(c)[:200]}" for c in list(candidates)[:4])
        cand_txt = f"\n\nCandidate results so far:\n{joined}"

    system = (
        f"You are the {role} on the Vortex council. {role_prompt}\n"
        "Give your own independent position — do not defer to the proposal.\n"
        'Respond with ONLY JSON: {"analysis": "<under 90 words>", '
        '"evidence": ["<short fact>", "..."], "confidence": <0.0-1.0>}'
    )
    data = llm.complete_json(system, f"Goal: {goal}\nProposal: {proposal}{cand_txt}", temperature=0.2)
    if not isinstance(data, dict):
        return None

    analysis = str(data.get("analysis") or "").strip()
    if not analysis:
        return None

    evidence = data.get("evidence")
    if not isinstance(evidence, list):
        evidence = []
    evidence = [str(e)[:200] for e in evidence[:5]]

    try:
        confidence = float(data.get("confidence", 0.6))
    except (TypeError, ValueError):
        confidence = 0.6
    confidence = max(0.0, min(1.0, confidence))

    return {"analysis": analysis, "evidence": evidence or [analysis[:200]], "confidence": confidence}
