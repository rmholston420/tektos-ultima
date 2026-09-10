"""Planner/Thinker (S4) — the orchestrator.

Full pipeline:
1. Language Game Classifier → identify the domain
2. Disambiguator → catch ambiguous terms across domains
3. Translator → convert NL → Proper Technical English
4. Template Selector → choose architecture template
5. Spec Generator → produce structured build spec

The Planner is S4 (Intelligence) in the VSM. It looks outward at the
environment, identifies what needs to be built, and translates human
intent into machine-executable specifications.

The Planner does NOT execute code. It produces the spec. The Coding Agent
(S1) executes the spec. The Manager (S3) regulates the variety between
them. This separation of concerns is critical — the Planner translates,
the Agent computes.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from .disambiguator import (
    find_ambiguities,
    find_vague_terms,
    generate_clarifying_questions,
    resolve_ambiguities,
)
from .language_game import LanguageGame, classify_language_game, get_language_game_description
from .models import (
    Ambiguity,
    AmbiguityResolution,
    BuildSpec,
    ClarifyingQuestion,
    PlannerOutput,
)
from .repo_map import RepoMapGenerator
from .spec_generator import generate_spec
from .template_selector import choose_best_template
from .translator import add_spec_context, translate_to_technical_english
from src.tektos.runtime.embedder import EmbedderClient

log = logging.getLogger(__name__)


class Planner:
    """The Planner/Thinker (S4) orchestrator.

    Processes natural language through the full pipeline:
    Language Game → Disambiguator → Translator → Template Selector → Spec Generator

    Attributes:
        context_budget: Maximum context budget in tokens (default: 128000).
        max_clarifying_questions: Maximum number of questions to ask per prompt.
        repo_root: Path to the repository root for repo map generation.
    """

    def __init__(
        self,
        context_budget: int = 128000,
        max_clarifying_questions: int = 3,
        repo_root: str = ".",
        embedder_client: EmbedderClient | None = None,
    ) -> None:
        self.context_budget = context_budget
        self.max_clarifying_questions = max_clarifying_questions
        self.repo_root = Path(repo_root)
        self._repo_map: RepoMapGenerator | None = None
        self._repo_map_result: Any = None  # RepoMap object from generate_map()
        self._embedder = embedder_client

    def _get_repo_map(self) -> RepoMapGenerator | None:
        """Lazy-load repo map generator. Only creates if repo_root exists."""
        if self._repo_map is None and self.repo_root.exists():
            try:
                self._repo_map = RepoMapGenerator(str(self.repo_root))
            except Exception as e:
                log.debug(f"Failed to init repo map: {e}")
        return self._repo_map

    async def _get_embedding_relevant_files(
        self,
        prompt: str,
        top_k: int = 5,
    ) -> list[str]:
        """Find files most relevant to the prompt using embeddings.

        Uses the repo map's symbol index and file content to build a corpus,
        then embeds the prompt to find the most similar files.

        Args:
            prompt: The user's prompt.
            top_k: Number of relevant files to return.

        Returns:
            List of relevant file paths.
        """
        if self._embedder is None or self._repo_map is None:
            return []

        try:
            # Build corpus from repo map
            corpus: list[tuple[str, str]] = []  # (file_path, text)

            # Add symbol info
            for file_path, file_info in self._repo_map.files.items():
                if file_info.symbols:
                    symbols_text = "\n".join(
                        f"{s.kind}: {s.name} (line {s.line_start})"
                        for s in file_info.symbols[:20]
                    )
                    corpus.append((file_path, f"{file_path} symbols: {symbols_text}"))

            # Add file content summaries (first 500 chars)
            for file_path, file_info in self._repo_map.files.items():
                try:
                    content = Path(file_info.path).read_text(
                        encoding='utf-8', errors='replace'
                    )[:500]
                    if content.strip():
                        corpus.append((file_path, f"{file_path} content: {content}"))
                except OSError:
                    pass

            if not corpus:
                return []

            # Embed prompt and corpus
            prompt_vec = await self._embedder.embed(prompt)
            if not prompt_vec.embeddings:
                return []

            corpus_vecs = await self._embedder.embed_batch(
                [text for _, text in corpus]
            )

            # Compute similarities
            from src.tektos.runtime.embedder import cosine_similarity
            scored: list[tuple[float, str]] = []
            for i, c_vec in enumerate(corpus_vecs.embeddings):
                sim = cosine_similarity(prompt_vec.embeddings[0], c_vec)
                scored.append((sim, corpus[i][0]))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [f for _, f in scored[:top_k]]

        except Exception as e:
            log.debug(f"Embedding-based file relevance failed: {e}")
            return []

    def plan(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        user_preference: str | None = None,
        synthesis_guidance: str = "",
    ) -> PlannerOutput:
        """Run the full planning pipeline on a natural language prompt.

        Args:
            prompt: The user's natural language prompt.
            context: Optional context dict (language_game, tech_stack, constraints).
            user_preference: Optional user preference for architecture template.

        Returns:
            PlannerOutput containing the structured spec and metadata.
        """
        # Step 0: Generate repo map for codebase context (if available)
        repo_map = self._get_repo_map()
        repo_context = ""
        embedding_relevant_files: list[str] = []
        if repo_map:
            try:
                self._repo_map_result = repo_map.generate_map()
                repo_context = repo_map.generate_context_prompt(prompt)

                # Embedding-based file relevance (if embedder available)
                if self._embedder:
                    embedding_relevant_files = asyncio.run(
                        self._get_embedding_relevant_files(prompt, top_k=5)
                    )
                    if embedding_relevant_files:
                        repo_context += (
                            f"\n\n# Embedding-Relevant Files\n"
                            f"Most relevant files for this task: {', '.join(embedding_relevant_files)}\n"
                        )
            except Exception as e:
                log.debug(f"Repo map generation failed: {e}")

        # Step 1: Classify language game
        language_game = classify_language_game(prompt)

        # Step 2: Find ambiguities
        ambiguities = find_ambiguities(prompt, language_game)
        vague_terms = find_vague_terms(prompt)
        all_ambiguities = ambiguities + vague_terms

        # Step 3: Resolve ambiguities
        resolved, resolutions = resolve_ambiguities(
            all_ambiguities,
            user_input=context.get("previous_conversation") if context else None,
        )

        # Step 4: Generate clarifying questions (for unresolved critical ambiguities)
        unresolved_critical = [
            amb
            for amb, res in zip(resolved, resolutions)
            if res == AmbiguityResolution.ASK_USER and amb.criticality == "critical"
        ]
        clarifying_questions = generate_clarifying_questions(unresolved_critical)

        # Limit clarifying questions
        clarifying_questions = clarifying_questions[: self.max_clarifying_questions]

        # Step 5: Translate to Proper Technical English
        context_for_translation = context or {}
        context_for_translation["language_game"] = get_language_game_description(language_game)
        if repo_context:
            context_for_translation["repo_context"] = repo_context
        translated = translate_to_technical_english(prompt)
        translated = add_spec_context(translated, context_for_translation)

        # Step 6: Select architecture template
        requirements = self._extract_requirements(translated)
        architecture = choose_best_template(
            requirements,
            user_preference=user_preference,
        )

        # Step 7: Generate build spec
        spec = generate_spec(
            original_prompt=prompt,
            translated_prompt=translated,
            language_game=language_game,
            architecture=architecture,
            requirements=requirements,
            constraints=context.get("constraints") if context else None,
            tech_stack=context.get("tech_stack") if context else None,
            test_strategy=context.get("test_strategy", "spec-driven") if context else "spec-driven",
            notes=context.get("notes") if context else None,
            context_budget_warning=(
                f"Spec uses {len(translated)} chars. Context budget: {self.context_budget}."
                if len(translated) > self.context_budget * 0.8
                else None
            ),
            synthesis_guidance=synthesis_guidance,
        )

        return PlannerOutput(
            spec=spec,
            synthesis_guidance=synthesis_guidance,
            language_game_detected=language_game,
            ambiguities_found=all_ambiguities,
            ambiguities_resolved=list(zip(resolved, resolutions)),
            clarifying_questions_asked=clarifying_questions,
            templates_presented=[architecture.selected],
            context_budget_used=len(translated),
            context_budget_total=self.context_budget,
        )

    def _extract_requirements(self, text: str) -> list[str]:
        """Extract requirements from translated text.

        Simple heuristic: split on newlines and filter non-empty lines.
        The Spec Generator does more sophisticated extraction if needed.
        """
        lines = text.split("\n")
        return [line.strip() for line in lines if line.strip()]
