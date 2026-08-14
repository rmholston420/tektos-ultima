"""Language Game Classifier (Wittgenstein).

Identifies which domain/language game the user is operating in.
Every domain has its own technical terminology; words shift meaning across fields.
The Planner must identify the language game before translating.

"Meaning is use" — a word's meaning is determined by how it's used in context.
"""

from __future__ import annotations

import re
from typing import Any

from .models import LanguageGame


# Domain keyword signatures — each game has a unique vocabulary fingerprint
_DOMAIN_SIGNATURES: dict[LanguageGame, list[str]] = {
    LanguageGame.SOFTWARE_ENGINEERING: [
        "api", "database", "function", "class", "module", "test",
        "deploy", "build", "compile", "runtime", "endpoint", "route",
        "authentication", "authorization", "token", "jwt", "oauth",
        "frontend", "backend", "server", "client", "database", "query",
        "sql", "json", "http", "websocket", "rest", "graphql",
        "docker", "kubernetes", "ci/cd", "pipeline", "artifact",
        "microservice", "monolith", "architecture", "framework",
        "python", "typescript", "javascript", "react", "vue", "angular",
        "fastapi", "flask", "django", "next.js", "node.js",
        "code", "refactor", "debug", "lint", "format",
    ],
    LanguageGame.SYSTEMS_ARCHITECTURE: [
        "vsm", "viable system", "cybernetics", "general systems",
        "feedback", "homeostasis", "variety", "requisite variety",
        "ashby", "beer", "wiener", "bertalanffy",
        "s1", "s2", "s3", "s4", "s5", "system 1", "system 2",
        "governance", "control", "operations", "audit", "intelligence",
        "coherence", "self-organization", "emergence", "complexity",
        "prinst", "process", "information", "structure",
        "architecture", "pattern", "antipattern",
        "planner", "thinker", "coding agent", "manager", "supervisor",
        "agent", "multi-agent", "orchestrator", "coordinator",
        "tektos", "kosmos", "rigpa", "apex", "vlife",
    ],
    LanguageGame.BUDDHIST_PHILOSOPHY: [
        "dharma", "sangha", "bodhisattva", "nirvana", "samsara",
        "meditation", "mindfulness", "contemplation", "insight",
        "nagarjuna", "madhyamaka", "emptiness", "shunyata",
        "dependent origination", "pratityasamutpada",
        "bodhicitta", "samaya", "ngakpa", "lama",
        "tibetan", "vajrayana", "saivite", "yoga",
        "process ontology", "whitehead", "bohm", "implicate order",
        "axiomatization", "gutoe", "crustafarianism", "plasmodialism",
        "wisdom", "compassion", "skillful means", "upaya",
        "dharma vows", "dharma-invariant", "self-actualization",
    ],
}


def classify_language_game(text: str) -> LanguageGame:
    """Classify the language game of the given text.

    Analyzes keywords and context to determine which domain the user is operating in.
    Returns the best matching LanguageGame, or LanguageGame.GENERAL if uncertain.

    Args:
        text: The text to classify (user prompt or conversation context).

    Returns:
        The identified LanguageGame enum value.
    """
    text_lower = text.lower()

    scores: dict[LanguageGame, float] = {}

    for game, keywords in _DOMAIN_SIGNATURES.items():
        score = 0.0
        for keyword in keywords:
            if keyword in text_lower:
                score += 1.0
        scores[game] = score

    best_game = max(scores, key=scores.get)  # type: ignore[arg-type]
    best_score = scores[best_game]

    # If no keywords matched, return GENERAL
    if best_score == 0:
        return LanguageGame.GENERAL

    # If there's a tie, prefer SOFTWARE_ENGINEERING (most common)
    top_scores = [g for g, s in scores.items() if s == best_score]
    if len(top_scores) > 1:
        if LanguageGame.SOFTWARE_ENGINEERING in top_scores:
            return LanguageGame.SOFTWARE_ENGINEERING
        if LanguageGame.SYSTEMS_ARCHITECTURE in top_scores:
            return LanguageGame.SYSTEMS_ARCHITECTURE

    return best_game


def get_language_game_description(game: LanguageGame) -> str:
    """Return a human-readable description of a language game."""
    descriptions = {
        LanguageGame.SOFTWARE_ENGINEERING: "Software Engineering — programming, APIs, databases, testing, deployment",
        LanguageGame.SYSTEMS_ARCHITECTURE: "Systems Architecture — VSM, cybernetics, system design, governance",
        LanguageGame.BUDDHIST_PHILOSOPHY: "Buddhist Philosophy — dharma, meditation, ontology, axiomatic theory",
        LanguageGame.GENERAL: "General — everyday language, no specialized domain",
    }
    return descriptions.get(game, "Unknown")
