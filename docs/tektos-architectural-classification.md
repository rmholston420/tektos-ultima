"""Tektos Architectural Classification: Built-in vs Plugin vs Skill

This document classifies every Tektos component into one of three categories
to guide development, plugin creation, and system design decisions.

CLASSIFICATION CRITERIA:
1. Built-in: Tektos cannot function without it. These are existential to
   the system's identity and purpose.
2. Plugin: Tektos works without it; user can swap backends. These are
   swappable, optional, or extensible components.
3. Skill: Reusable procedures stored in ~/.hermes/skills/. These are
   workflows, not code modules.

"""

# ═══════════════════════════════════════════════════════════
# BUILT-IN (Cannot be removed without breaking Tektos)
# ═══════════════════════════════════════════════════════════

BUILT_IN = {
    "protocol/": {
        "files": ["envelope.py", "schema_5w1h.py"],
        "reason": "The envelope format and 5W1H schema are the existential contract. "
                  "All events, messages, and interactions must carry 5W1H metadata. "
                  "Without this, Tektos loses its identity as a cybernetic agent.",
        "note": "Can be evolved (versioned), but never removed.",
    },

    "store/": {
        "files": ["event_store.py", "trail.py"],
        "reason": "The append-only event store is the core memory mechanism. "
                  "Tektos's entire identity is built on the Hegelian dialectic loop "
                  "encoded in the Trail. Without the event store, there is no memory, "
                  "no self-improvement, no recovery.",
        "note": "The storage backend (SQLite) can be swapped, but the event store "
                "abstraction must remain built-in.",
    },

    "runtime/": {
        "files": ["session.py", "session_state.py", "sdk.py"],
        "reason": "Session lifecycle management and the state machine are the "
                  "core execution engine. Without sessions, there is no agent "
                  "continuity across turns.",
        "note": "Runtime can be enhanced, but the session manager must remain built-in.",
    },

    "self_modification/": {
        "files": ["self_test_expander.py", "self_gui_expander.py"],
        "reason": "Self-modification is a core mandate from the user. Tektos must "
                  "autonomously expand its own frontend and backend test coverage. "
                  "This is not optional — it's part of Tektos's identity.",
        "note": "The self-improvement loop wiring (Planner→ExperienceReplay) is also built-in.",
    },

    "self_improvement/": {
        "files": ["synthesis_engine.py", "experience_replay.py", "planner.py"],
        "reason": "The synthesis engine and experience replay are the learning loop. "
                  "Without them, Tektos cannot improve from past experience.",
        "note": "The learning model (Claude, GPT, etc.) can be swapped, but the "
                "synthesis mechanism must remain built-in.",
    },

    "agents/": {
        "subdirectories": ["coder/", "planner/", "manager/"],
        "reason": "Tektos's identity is defined as an autonomous agent with three "
                  "roles: Planner (think), Manager (coordinate), Coder (execute). "
                  "These are not swappable — they are Tektos's soul.",
        "note": "Individual agent implementations can be replaced, but the three-role "
                "architecture must remain built-in.",
    },

    "ports/": {
        "files": ["provider_port.py"],
        "reason": "The ProviderPort contract is the plugin interface itself. "
                  "Without it, there is no plugin system.",
        "note": "The contract can evolve, but the existence of a plugin interface "
                "is built-in to Tektos's design.",
    },

    "plugin.py": {
        "files": ["Plugin", "PluginRegistry"],
        "reason": "The base plugin class and registry are the infrastructure for the "
                  "plugin system itself. Without them, plugins cannot exist.",
        "note": "This is the scaffolding, not the plugins.",
    },

    "plugin_loader.py": {
        "files": ["PluginLoader"],
        "reason": "The plugin loader discovers and manages plugin lifecycle. "
                  "Without it, plugins cannot be loaded dynamically.",
        "note": "Loading mechanism can be enhanced, but must remain built-in.",
    },
}

# ═══════════════════════════════════════════════════════════
# PLUGIN (Swappable, optional, extensible)
# ═══════════════════════════════════════════════════════════

PLUGINS = {
    "searxng_plugin/": {
        "location": "plugins/searxng_plugin/",
        "status": "CONVERTED",
        "reason": "Search is useful but not existential. Tektos can reason, plan, "
                  "and self-modify without web search. Users may use SearXNG, "
                  "Google, DuckDuckGo, or no search at all.",
        "benefits": [
            "Swappable backends (SearXNG → Google → DDG)",
            "Optional dependency (not everyone runs SearXNG locally)",
            "Self-modification friendly (Tektos can discover/add search plugins)",
            "Consistent with ProviderPort contract",
        ],
    },

    "providers/": {
        "location": "src/tektos/providers/",
        "status": "CONVERT_TO_PLUGIN",
        "reason": "Provider implementations (SearXNG client, future providers) "
                  "are swappable backends. The ProviderPort contract is built-in, "
                  "but the implementations should be plugins.",
        "action": "Move all provider implementations from src/tektos/providers/ to plugins/",
    },

    "memory/": {
        "location": "src/tektos/memory/",
        "status": "CONVERT_TO_PLUGIN",
        "reason": "Memory backends (Redis, Postgres, Neo4j, SQLite) are swappable. "
                  "Tektos works with any combination of these. The memory system "
                  "abstraction is built-in, but the implementations should be plugins.",
        "action": "Convert Redis, Postgres, Neo4j, and SQLite backends to plugins",
    },

    "telegram_gateway/": {
        "location": "src/tektos/telegram_gateway.py",
        "status": "CONVERT_TO_PLUGIN",
        "reason": "Telegram is just one of many possible gateways. Tektos also "
                  "supports Discord and WhatsApp. The gateway abstraction is built-in, "
                  "but each gateway implementation should be a plugin.",
        "action": "Convert telegram_gateway.py to plugins/telegram_gateway/",
        "future": "Discord gateway → plugins/discord_gateway/ WhatsApp gateway → plugins/whatsapp_gateway/",
    },
}

# ═══════════════════════════════════════════════════════════
# SKILL (Reusable procedures in ~/.hermes/skills/)
# ═══════════════════════════════════════════════════════════

SKILLS = {
    "agent-loop-troubleshooting": {
        "type": "procedure",
        "reason": "Debugging agent loop issues is a reusable procedure, not a code module. "
                  "Skills are for workflows that agents follow, not persistent system components.",
        "location": "~/.hermes/skills/agent-loop-troubleshooting/",
    },

    "self-improvement-loop": {
        "type": "procedure",
        "reason": "The self-improvement workflow (Synthesis→ExperienceReplay→Planner) "
                  "is a procedure. The mechanism is built-in, but the workflow for "
                  "triggering it is a skill.",
        "location": "~/.hermes/skills/self-improvement-loop/",
    },

    "benchmarking": {
        "type": "procedure",
        "reason": "Benchmarking against frontier systems is a recurring procedure. "
                  "Per user instruction, it's deferred but when implemented, it should "
                  "be a skill, not a code module.",
        "location": "~/.hermes/skills/benchmarking/",
    },
}

# ═══════════════════════════════════════════════════════════
# DECISION RULES
# ═══════════════════════════════════════════════════════════

RULES = """
When deciding if something should be built-in, plugin, or skill:

1. Ask: "Can Tektos function without this?"
   - No → Built-in
   - Yes → Continue to #2

2. Ask: "Is this a swappable backend or implementation?"
   - Yes → Plugin
   - No → Continue to #3

3. Ask: "Is this a reusable procedure or workflow?"
   - Yes → Skill
   - No → Built-in (default)

4. Ask: "Does this change Tektos's identity?"
   - Yes → Built-in
   - No → Plugin or Skill

Examples:
- Event store → Built-in (changes identity)
- SearXNG provider → Plugin (swappable)
- Redis memory → Plugin (swappable)
- Telegram gateway → Plugin (swappable)
- Agent loop debugging → Skill (procedure)
- Self-improvement synthesis → Built-in (changes identity)

When in doubt, make it a plugin. Plugins are easier to remove than built-ins.
"""
