"""Vortex Agent — Phase 2 CLI with swarm commands."""
from memory import Memory
from swarm import VortexAgent


def main():
    memory = Memory()
    agent = VortexAgent(memory)

    print("\n🌪️  VORTEX AGENT — Phase 2 (The Swarm)")
    print("   Bots:", ", ".join(agent.bots.keys()))
    print("   Type /help for commands, /quit to exit.\n")

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
            print("  @<bot> <msg>        talk to one bot\n"
                  "  /bots               list swarm\n"
                  "  /spawn <name> <role>  add a bot\n"
                  "  /kill <name>        remove a bot\n"
                  "  /skills             shared skill library\n"
                  "  /history /stats /clear\n"
                  "  anything else       chief orchestrates the swarm")
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
            print(f"  messages={s['messages']} tool_calls={s['tool_calls']}")
            continue
        if msg == "/clear":
            memory.clear_history()
            print("  cleared")
            continue

        # direct-bot addressing
        if msg.startswith("@"):
            name, _, rest = msg[1:].partition(" ")
            if name in agent.bots:
                print(f"vortex[{name}]> {agent.bots[name].handle(rest)}\n")
            else:
                print("  unknown bot")
            continue

        # default: chief orchestrates
        print(f"vortex> {agent.chat(msg)}\n")

    print("\n👋 Signed off.")


if __name__ == "__main__":
    main()
