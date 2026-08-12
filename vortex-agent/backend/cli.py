"""Vortex Agent — Phase 4 CLI with full Vortex architecture."""
from memory import Memory
from swarm import VortexAgent

def main():
    memory = Memory()
    agent = VortexAgent(memory)

    print("\n🌪️  VORTEX AGENT — Phase 5 (Evolution Engine v1)")
    print("   Bots:", ", ".join(agent.bots.keys()))
    print("   RSI  : gen", agent.memory.current_generation())
    print("   Council:", list(agent.council.members.keys()) if agent.council else "none")
    print("   Sovereign:", agent.sovereign.identity.whoami() if agent.sovereign else "none")
    print("   Governance policies:", len(agent.governance.policy.policies) if agent.governance else 0)
    print("   Tools:", len(agent.tool_registry.tools) if agent.tool_registry else 0)
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
            print(
                "  @<bot> <msg>           talk to one bot\n"
                "  /bots                  list swarm\n"
                "  /spawn <name> <role>   add a bot\n"
                "  /kill <name>           remove a bot\n"
                "  /skills                shared skill library\n"
                "  /history /stats /clear\n"
                "  /improve /rsi /lessons /evolve /eval\n"
                "  -- new --\n"
                "  /council               council status\n"
                "  /deliberate <goal>     run council deliberation\n"
                "  /governance            governance policies + audit\n"
                "  /sovereign             sovereign identity/objectives/state\n"
                "  /tools                 list tool capabilities\n"
                "  /memory <query>        hybrid memory recall\n"
                "  /graph                 knowledge graph stats\n"
                "  /orchestrate <goal>    run full orchestration graph\n"
                "  /benchmark             Vortex comprehensive benchmark\n"
                "  /observability         traces + metrics\n"
                "  /releases              evolution releases + pointers\n"
                "  /rollback              restore last known-good overlay\n"
                "  anything else          chief orchestrates (add 'orchestrate:' prefix for full graph)"
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
        if msg == "/skills":
            for s in agent.skills.list():
                print(f"  • {s['name']}: {s['description']}")
            continue
        if msg in ("/improve", "/rsi"):
            print(agent.rsi.report())
            continue
        if msg == "/lessons":
            lessons = agent.memory.get_lessons(True)
            if not lessons:
                print("  (no lessons yet — talk to the swarm, it learns mid-turn)")
            for l in lessons[:20]:
                print(f"  • [{l['kind']}] {l['trigger']} → {l['action']}  "
                      f"c={l['confidence']:.2f} {l['wins']}w/{l['losses']}l")
            continue
        if msg == "/evolve":
            cycle = agent.rsi.run_cycle()
            print(f"  {cycle['decision']}: {cycle['notes']}")
            if cycle.get("evolution"):
                print(f"  evolution: {cycle['evolution']}")
            print(agent.rsi.report())
            continue
        if msg == "/eval":
            from evals import format_suite, run_suite
            print(format_suite(run_suite(agent, name="cli")))
            continue
        if msg in ("/benchmark", "/eval/benchmark"):
            from evals import VortexBenchmark, format_suite
            vb = VortexBenchmark(agent)
            res = vb.run_comprehensive(persist=False)
            print(format_suite(res))
            continue
        if msg == "/history":
            for m in memory.get_history(10):
                print(f"  [{m['role']}] {m['content'][:80]}")
            continue
        if msg == "/stats":
            s = memory.stats()
            print(f"  messages={s['messages']} tool_calls={s['tool_calls']} lessons={s['lessons']} generation={s['generation']}")
            if s.get("graph"):
                print(f"  graph nodes={s['graph'].get('nodes')} edges={s['graph'].get('edges')}")
            continue
        if msg == "/clear":
            memory.clear_history()
            print("  cleared")
            continue
        if msg == "/council":
            if agent.council:
                print(f"  members: {list(agent.council.members.keys())}")
                print(f"  weights: {agent.council.weights}")
            else:
                print("  council not loaded")
            continue
        if msg.startswith("/deliberate"):
            goal = msg[len("/deliberate"):].strip() or "research and build a fibonacci benchmark"
            if agent.council:
                delib = agent.council.deliberate(goal=goal)
                print(f"  decision: {delib.get('decision')} conf={delib.get('confidence')}")
                print(f"  final: {delib.get('final', '')[:400]}")
            else:
                print("  council not loaded")
            continue
        if msg == "/governance":
            if agent.governance:
                for p in agent.governance.policy.list_policies()[:10]:
                    print(f"  • {p['name']} → {p['action']} ({p['description']})")
                print(f"  audit recent: {len(agent.governance.audit.recent(5))} entries")
            else:
                print("  governance not loaded")
            continue
        if msg == "/sovereign":
            if agent.sovereign:
                ctx = agent.sovereign.context()
                print(f"  identity: {ctx['identity']}")
                print(f"  mode: {ctx['state'].get('mode')} health: {ctx['state'].get('health')}")
                print(f"  objectives: {ctx['objectives'][:2]}")
            else:
                print("  sovereign not loaded")
            continue
        if msg == "/tools":
            if agent.tool_registry:
                for cat, names in agent.tool_registry.categories().items():
                    print(f"  {cat}: {', '.join(names[:5])}")
            else:
                print("  tool registry not loaded")
            continue
        if msg.startswith("/memory"):
            query = msg[len("/memory"):].strip() or "test"
            rec = memory.recall(query, n=5)
            for r in rec[:10]:
                print(f"  • [{r.get('type')}] {str(r)[:120]}")
            continue
        if msg == "/graph":
            if hasattr(memory, 'graph') and memory.graph:
                print(f"  {memory.graph.stats()}")
                nodes = memory.graph.get_all(10)
                for n in nodes:
                    print(f"    • {n['label']} ({n['type']}) c={n['confidence']:.2f}")
            else:
                print("  graph not available")
            continue
        if msg.startswith("/orchestrate"):
            goal = msg[len("/orchestrate"):].strip() or "research and build fibonacci"
            if agent.graph:
                print(f"  running orchestration graph for: {goal}")
                res = agent.run_orchestrated(goal)
                print(f"  result: {res[:800]}")
            else:
                print("  graph not loaded")
            continue
        if msg == "/observability":
            if agent.observability:
                print(f"  metrics: {agent.observability.metrics.summary()}")
                print(f"  traces: {agent.observability.tracer.list_recent(3)}")
            else:
                print("  observability not loaded")
            continue

        # direct-bot addressing
        if msg.startswith("@"):
            name, _, rest = msg[1:].partition(" ")
            if name in agent.bots:
                print(f"vortex[{name}]> {agent.bots[name].handle(rest)}\n")
            else:
                print("  unknown bot")
            continue

        # orchestrated prefix
        if msg.lower().startswith("orchestrate:"):
            goal = msg[len("orchestrate:"):].strip()
            print(f"vortex[orchestrated]> {agent.run_orchestrated(goal)}\n")
            continue

        # default: chief orchestrates
        print(f"vortex> {agent.chat(msg)}\n")

    print("\n👋 Signed off.")

if __name__ == "__main__":
    main()
