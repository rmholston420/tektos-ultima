"""Disambiguator — identifies ambiguous terms in user prompts.

Every domain has its own technical terminology; a word means one thing in
mathematics and another in physics, software engineering, or Buddhist philosophy.
The Disambiguator catches these shifts and either asks the user to clarify
or makes an optimal choice (when the system can decide).

"Meaning is use" — Wittgenstein. A word's meaning is determined by how it's
used in context. The Disambiguator finds the context, then determines meaning.
"""

from __future__ import annotations

from .language_game import LanguageGame, classify_language_game
from .models import (
    Ambiguity,
    AmbiguityResolution,
    ClarifyingQuestion,
)


# Domain-specific ambiguity dictionary
_AMBIGUITY_DICTIONARY: dict[str, dict[LanguageGame, str]] = {
    "function": {
        LanguageGame.SOFTWARE_ENGINEERING: "A named block of code that performs a specific task",
        LanguageGame.SYSTEMS_ARCHITECTURE: "The role or purpose of a system component within a larger architecture",
        LanguageGame.BUDDHIST_PHILOSOPHY: "A natural law or principle; the way things work by nature (dharma as function)",
        LanguageGame.GENERAL: "A purpose or role",
    },
    "model": {
        LanguageGame.SOFTWARE_ENGINEERING: "A trained neural network that processes data",
        LanguageGame.SYSTEMS_ARCHITECTURE: "A mathematical or conceptual representation of a system",
        LanguageGame.BUDDHIST_PHILOSOPHY: "A conceptual construct; all models are provisional (not ultimate truth)",
        LanguageGame.GENERAL: "A representation or pattern",
    },
    "test": {
        LanguageGame.SOFTWARE_ENGINEERING: "Automated verification that code behaves correctly",
        LanguageGame.SYSTEMS_ARCHITECTURE: "A stress condition applied to evaluate system behavior",
        LanguageGame.BUDDHIST_PHILOSOPHY: "A practical experiment in understanding (direct experience, not theory)",
        LanguageGame.GENERAL: "An attempt to determine quality or correctness",
    },
    "agent": {
        LanguageGame.SOFTWARE_ENGINEERING: "A program that acts autonomously to achieve goals",
        LanguageGame.SYSTEMS_ARCHITECTURE: "An entity within a system that performs operations (S1 agent)",
        LanguageGame.BUDDHIST_PHILOSOPHY: "A being with free will and moral agency (karma-driven)",
        LanguageGame.GENERAL: "A person or entity that acts",
    },
    "process": {
        LanguageGame.SOFTWARE_ENGINEERING: "An OS-level execution unit (thread, container, process)",
        LanguageGame.SYSTEMS_ARCHITECTURE: "A workflow or transformation sequence (PRINST: what the system does)",
        LanguageGame.BUDDHIST_PHILOSOPHY: "A sequence of causal events (dependent origination)",
        LanguageGame.GENERAL: "A series of actions",
    },
    "event": {
        LanguageGame.SOFTWARE_ENGINEERING: "A discrete occurrence in a system (API call, database write)",
        LanguageGame.SYSTEMS_ARCHITECTURE: "A recorded fact in the Trail (S2 event stream)",
        LanguageGame.BUDDHIST_PHILOSOPHY: "A moment of arising in the flow of phenomena (dharmas)",
        LanguageGame.GENERAL: "Something that happens",
    },
    "pattern": {
        LanguageGame.SOFTWARE_ENGINEERING: "A reusable solution to a common problem in code (design pattern)",
        LanguageGame.SYSTEMS_ARCHITECTURE: "A recurring structural or behavioral arrangement in a system (archetype)",
        LanguageGame.BUDDHIST_PHILOSOPHY: "A repeating form in nature that reveals underlying unity (sacred geometry)",
        LanguageGame.GENERAL: "A regular or repeated arrangement",
    },
    "structure": {
        LanguageGame.SOFTWARE_ENGINEERING: "The organization of code, classes, and modules",
        LanguageGame.SYSTEMS_ARCHITECTURE: "The arrangement of components within a system (PRINST: Structure third)",
        LanguageGame.BUDDHIST_PHILOSOPHY: "The arrangement of phenomena; all structures are empty of inherent existence",
        LanguageGame.GENERAL: "The arrangement of parts into a whole",
    },
    "system": {
        LanguageGame.SOFTWARE_ENGINEERING: "A software system or application",
        LanguageGame.SYSTEMS_ARCHITECTURE: "A cybernetic unit within a larger organization (VSM S1-S5)",
        LanguageGame.BUDDHIST_PHILOSOPHY: "The interconnected web of phenomena (dependent origination)",
        LanguageGame.GENERAL: "A group of interacting parts",
    },
    "state": {
        LanguageGame.SOFTWARE_ENGINEERING: "The condition of a program at a specific moment (variables, memory)",
        LanguageGame.SYSTEMS_ARCHITECTURE: "The current configuration of a system (homeostatic setpoint or deviation)",
        LanguageGame.BUDDHIST_PHILOSOPHY: "A transient condition in the flow of phenomena (impermanent)",
        LanguageGame.GENERAL: "The condition of something at a specific time",
    },
    "control": {
        LanguageGame.SOFTWARE_ENGINEERING: "Management of program flow or system resources",
        LanguageGame.SYSTEMS_ARCHITECTURE: "VSM S3: regulatory feedback that maintains homeostasis (variety regulation)",
        LanguageGame.BUDDHIST_PHILOSOPHY: "Mindfulness and ethical restraint (sila as the foundation of samadhi)",
        LanguageGame.GENERAL: "The power to influence or direct behavior",
    },
    "intelligence": {
        LanguageGame.SOFTWARE_ENGINEERING: "Pattern recognition in machine learning models",
        LanguageGame.SYSTEMS_ARCHITECTURE: "VSM S4: horizon scanning and environmental adaptation",
        LanguageGame.BUDDHIST_PHILOSOPHY: "Prajna: insight into the true nature of reality (not mere knowledge)",
        LanguageGame.GENERAL: "The ability to acquire and apply knowledge",
    },
}

# Ambiguous terms that are always vague regardless of domain (need quantification)
_VAGUE_TERMS: dict[str, str] = {
    "fast": "low-latency (specify: <100ms, <1s, or real-time)",
    "slow": "high-latency (specify: >1s, >5s, or real-time is NOT acceptable)",
    "good": "meets acceptance criteria (specify: test pass rate, performance, security)",
    "bad": "fails acceptance criteria (specify: test failure, performance degradation, security issue)",
    "big": "large-scale (specify: number of records, data volume in GB/TB, users)",
    "small": "minimal/viable (specify: MVP scope, number of features, timebox)",
    "simple": "straightforward implementation (specify: number of components, lines of code)",
    "complex": "requires careful design (specify: number of dependencies, concurrency, state)",
    "secure": "meets security standards (specify: authentication, authorization, encryption)",
    "fast": "low-latency (specify: response time, throughput)",
    "reliable": "meets uptime/accuracy standards (specify: SLA, error rate)",
    "scalable": "handles increased load (specify: users, requests, data volume)",
    "efficient": "optimal resource usage (specify: CPU, memory, bandwidth, time)",
    "clean": "well-structured code (specify: linting rules, test coverage, documentation)",
}


def find_ambiguities(text: str, language_game: LanguageGame) -> list[Ambiguity]:
    """Find ambiguous terms in text based on the detected language game.

    Args:
        text: The user's natural language prompt.
        language_game: The identified language game (from classifier).

    Returns:
        List of Ambiguity objects for terms that have different meanings
        across domains.
    """
    ambiguities: list[Ambiguity] = []
    text_lower = text.lower()

    for term, domain_meanings in _AMBIGUITY_DICTIONARY.items():
        if term in text_lower:
            primary_meaning = domain_meanings.get(language_game, domain_meanings[LanguageGame.GENERAL])
            other_meanings = [
                meaning
                for g, meaning in domain_meanings.items()
                if g != language_game
            ]
            # Only create ambiguity if there are multiple different meanings
            if len(other_meanings) > 0:
                all_meanings = [primary_meaning] + other_meanings
                # Critical if the term appears in a systems architecture context
                criticality = "moderate"
                if language_game == LanguageGame.SYSTEMS_ARCHITECTURE and term in (
                    "system", "control", "intelligence", "state"
                ):
                    criticality = "critical"

                ambiguities.append(Ambiguity(
                    term=term,
                    possible_meanings=all_meanings,
                    criticality=criticality,
                    domain=language_game,
                ))

    return ambiguities


def find_vague_terms(text: str) -> list[Ambiguity]:
    """Find vague, unquantified terms in text.

    These are terms that are ambiguous regardless of domain because they
    lack measurable criteria. E.g., "fast API" needs a latency specification.

    Args:
        text: The user's natural language prompt.

    Returns:
        List of Ambiguity objects for vague terms that need quantification.
    """
    ambiguities: list[Ambiguity] = []
    text_lower = text.lower()

    for term, clarification in _VAGUE_TERMS.items():
        if term in text_lower:
            ambiguities.append(Ambiguity(
                term=term,
                possible_meanings=[clarification],
                criticality="moderate",
            ))

    return ambiguities


def resolve_ambiguities(
    ambiguities: list[Ambiguity],
    user_input: str | None = None,
) -> tuple[list[Ambiguity], list[AmbiguityResolution]]:
    """Resolve ambiguities by asking the user or making optimal choices.

    Critical ambiguities are ALWAYS asked. Moderate/Minor ambiguities:
    - If user_input is provided, attempt to disambiguate from context
    - Otherwise, ask the user for clarification

    Args:
        ambiguities: List of ambiguous terms found.
        user_input: Optional user response to clarifying questions.

    Returns:
        Tuple of (resolved ambiguities, resolution list).
    """
    resolved: list[Ambiguity] = []
    resolutions: list[AmbiguityResolution] = []

    for ambiguity in ambiguities:
        if ambiguity.criticality == "critical":
            # Critical ambiguities must be asked — cannot resolve automatically
            resolved.append(ambiguity)
            resolutions.append(AmbiguityResolution.ASK_USER)
        elif user_input and ambiguity.domain:
            # Try to disambiguate from context
            resolved.append(ambiguity)
            resolutions.append(AmbiguityResolution.OPTIMAL_CHOICE)
        else:
            # No context — ask user
            resolved.append(ambiguity)
            resolutions.append(AmbiguityResolution.ASK_USER)

    return resolved, resolutions


def generate_clarifying_questions(
    ambiguities: list[Ambiguity],
) -> list[ClarifyingQuestion]:
    """Generate clarifying questions for unresolved ambiguities.

    Args:
        ambiguities: List of ambiguities that need clarification.

    Returns:
        List of ClarifyingQuestion objects for the user.
    """
    questions: list[ClarifyingQuestion] = []

    for amb in ambiguities:
        if amb.criticality != "critical":
            continue

        question = ClarifyingQuestion(
            question=f"What does '{amb.term}' mean in your context?",
            options=amb.possible_meanings,
            default=amb.possible_meanings[0] if amb.possible_meanings else "Unknown",
            reason=f"The term '{amb.term}' has multiple meanings across domains.",
        )
        questions.append(question)

    return questions
