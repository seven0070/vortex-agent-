"""Vortex CLI — interactive agent shell."""
from __future__ import annotations

import json
import sys
import time

from vortex.agent.os import VortexOS
from vortex.constants import NAME, VERSION


BANNER = f"""
🌪️  {NAME} v{VERSION} — Hermes-inspired autonomous agent
   Bots: {{bots}}
   Brain: {{provider}} · tools: {{tools}}
   Type /help for commands, /quit to exit.
"""


def main():
    os_ = VortexOS()

    def on_event(ev: dict):
        t = ev.get("type")
        if t == "thought":
            print(f"   💭 step {ev.get('step')}: {(ev.get('thought') or '')[:100]}")
            print(f"      → {ev.get('action')} {json.dumps(ev.get('args') or {})[:80]}")
        elif t == "tool_call":
            print(f"   🔧 {ev.get('tool')}")
        elif t == "observation":
            obs = (ev.get("observation") or "")[:120].replace("\n", " ")
            print(f"   👁  [{ev.get('status')}] {obs}")
        elif t == "mission_completed":
            print(f"   ✅ complete ({ev.get('steps')} steps)")
        elif t == "mission_failed":
            print(f"   ❌ failed: {ev.get('error')}")

    os_.subscribe(on_event)

    print(
        BANNER.format(
            bots=", ".join(os_.bots.keys()),
            provider=os_.brain.provider,
            tools=len(os_.list_tools()),
        )
    )

    while True:
        try:
            msg = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not msg:
            continue
        if msg in ("/quit", "exit", "quit"):
            break
        if msg == "/help":
            print(
                "  @<bot> <msg>         talk to one specialist\n"
                "  /auto <goal>         autonomous mission (live trace)\n"
                "  /missions            list sessions/missions\n"
                "  /mission <id>        show mission detail\n"
                "  /bots /spawn /kill\n"
                "  /tools /skills\n"
                "  /history /stats\n"
                "  anything else        chief chat (auto-missions when needed)"
            )
            continue
        if msg == "/bots":
            for b in os_.list_bots():
                print(f"  • {b['name']} ({b['role']}/{b['toolset']}) — {b['messages']} msgs")
            continue
        if msg.startswith("/spawn"):
            parts = msg.split()
            name = parts[1] if len(parts) > 1 else f"bot{len(os_.bots)}"
            role = parts[2] if len(parts) > 2 else "general"
            ts = parts[3] if len(parts) > 3 else "core"
            os_.spawn_bot(name, role, ts)
            continue
        if msg.startswith("/kill"):
            name = msg.split()[1] if len(msg.split()) > 1 else ""
            print("  💀 killed" if os_.kill_bot(name) else "  not found")
            continue
        if msg == "/tools":
            for t in os_.list_tools():
                print(f"  • {t['name']}: {t['description'][:70]}")
            continue
        if msg == "/skills":
            for s in os_.skills.list():
                print(f"  • {s['name']}: {s['description'][:70]}")
            continue
        if msg == "/stats":
            print(" ", os_.db.stats(), "provider=", os_.brain.provider)
            continue
        if msg == "/missions":
            for m in os_.agent.list_missions()[:15]:
                print(
                    f"  • {m['id']} [{m['status']}] steps={m.get('step_count',0)} — {(m.get('goal') or '')[:60]}"
                )
            continue
        if msg.startswith("/mission "):
            mid = msg.split(" ", 1)[1].strip()
            m = os_.agent.get_mission(mid)
            print(json.dumps(m, indent=2)[:3000] if m else "  not found")
            continue
        if msg.startswith("/auto "):
            goal = msg[6:].strip()
            print("  🚀 launching…")
            mission = os_.agent.run(goal, background=True)
            mid = mission["id"]
            while True:
                time.sleep(0.2)
                m = os_.agent.get_mission(mid)
                if m and m["status"] in ("completed", "failed", "cancelled"):
                    print(f"\nvortex> {m.get('result') or m.get('error')}\n")
                    break
            continue

        print(f"vortex> {os_.chat(msg)}\n")

    print("\n👋 Signed off.")


if __name__ == "__main__":
    main()
    sys.exit(0)
