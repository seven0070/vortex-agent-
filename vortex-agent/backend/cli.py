"""Vortex Agent — CLI with swarm + autonomous missions."""
from __future__ import annotations

import json
import sys
import time

from memory import Memory
from swarm import VortexAgent


BANNER = """
🌪️  VORTEX AGENT — Phase 3 (Autonomous)
   Bots: {bots}
   Brain: {provider}
   Type /help for commands, /quit to exit.
"""


def main():
    memory = Memory()
    agent = VortexAgent(memory)

    def on_event(ev: dict):
        t = ev.get("type")
        if t == "thought":
            print(f"   💭 step {ev.get('step')}: {ev.get('thought', '')[:100]}")
            print(f"      → {ev.get('action')} {json.dumps(ev.get('args') or {})[:80]}")
        elif t == "tool_call":
            print(f"   🔧 {ev.get('tool')}")
        elif t == "observation":
            obs = (ev.get("observation") or "")[:120].replace("\n", " ")
            print(f"   👁  [{ev.get('status')}] {obs}")
        elif t == "mission_completed":
            print(f"   ✅ mission complete ({ev.get('steps')} steps)")
        elif t == "mission_failed":
            print(f"   ❌ mission failed: {ev.get('error')}")

    agent.auto.subscribe(on_event)

    print(
        BANNER.format(
            bots=", ".join(agent.bots.keys()),
            provider=agent.auto.brain.provider,
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
                "  @<bot> <msg>           talk to one bot\n"
                "  /auto <goal>           run autonomous mission (live)\n"
                "  /missions              list missions\n"
                "  /mission <id>          show mission detail\n"
                "  /bots                  list swarm\n"
                "  /spawn <name> <role>   add a bot\n"
                "  /kill <name>           remove a bot\n"
                "  /tools                 list tools\n"
                "  /skills                shared skill library\n"
                "  /history /stats /clear\n"
                "  anything else          chief orchestrates (auto when needed)"
            )
            continue
        if msg == "/bots":
            for b in agent.list_bots():
                print(f"  • {b['name']} ({b['role']}) — {b['messages']} msgs")
            continue
        if msg.startswith("/spawn"):
            parts = msg.split()
            name = parts[1] if len(parts) > 1 else "bot" + str(len(agent.bots))
            role = parts[2] if len(parts) > 2 else "general"
            agent.spawn_bot(name, role)
            continue
        if msg.startswith("/kill"):
            name = msg.split()[1] if len(msg.split()) > 1 else ""
            print("  💀 killed" if agent.kill_bot(name) else "  not found")
            continue
        if msg == "/tools":
            for t in agent.auto.list_tools():
                print(f"  • {t['name']}: {t['description'][:70]}")
            continue
        if msg == "/skills":
            for s in agent.skills.list():
                print(f"  • {s['name']}: {s['description']}")
            continue
        if msg == "/history":
            for m in memory.get_history(10):
                print(f"  [{m['role']}] {m['content'][:80]}")
            continue
        if msg == "/stats":
            s = memory.stats()
            print(
                f"  messages={s['messages']} tool_calls={s['tool_calls']} "
                f"provider={agent.auto.brain.provider}"
            )
            continue
        if msg == "/clear":
            memory.clear_history()
            print("  cleared")
            continue
        if msg == "/missions":
            for m in agent.auto.list_missions()[:15]:
                print(
                    f"  • {m['id']} [{m['status']}] steps={m['step_count']} — {m['goal'][:60]}"
                )
            continue
        if msg.startswith("/mission "):
            mid = msg.split(" ", 1)[1].strip()
            m = agent.auto.get_mission(mid)
            if not m:
                print("  not found")
                continue
            print(json.dumps(m, indent=2)[:3000])
            continue
        if msg.startswith("/auto ") or msg.startswith("/mission "):
            # /auto handled below; /mission <id> already caught
            pass
        if msg.startswith("/auto "):
            goal = msg[6:].strip()
            print(f"  🚀 mission launched…")
            mission = agent.auto.start_mission(goal, max_steps=12, background=True)
            mid = mission["id"]
            # wait until done
            while True:
                time.sleep(0.25)
                m = agent.auto.get_mission(mid)
                if m and m["status"] in ("completed", "failed", "cancelled"):
                    print(f"\nvortex> {m.get('result') or m.get('error')}\n")
                    break
            continue

        # direct-bot addressing
        if msg.startswith("@"):
            name, _, rest = msg[1:].partition(" ")
            if name in agent.bots:
                print(f"vortex[{name}]> {agent.bots[name].handle(rest)}\n")
            else:
                print("  unknown bot")
            continue

        # default: chief orchestrates (may kick autonomy)
        print(f"vortex> {agent.chat(msg)}\n")

    print("\n👋 Signed off.")


if __name__ == "__main__":
    main()
    sys.exit(0)
