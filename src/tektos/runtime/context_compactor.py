"""Context compaction pipeline - 4-tier compression for managing context window.

This module implements a sophisticated context compaction system inspired by
Claude Code's 4-tier approach:
1. Raw messages (full conversation)
2. Summarized messages (compressed but detailed)
3. Abstracted context (high-level summary)
4. Persistent memory (CLAUDE.md style)

This allows the agent to maintain deep context while staying within token limits.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.tektos.runtime.embedder import EmbedderClient

logger = logging.getLogger(__name__)


@dataclass
class ContextTier:
    """A single tier of context compression."""

    tier: int  # 1-4
    name: str
    content: str
    token_estimate: int
    created_at: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class CompactionResult:
    """Result of a context compaction operation."""

    original_token_count: int
    compressed_token_count: int
    compression_ratio: float
    tiers: list[ContextTier]
    summary: str
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if self.original_token_count > 0:
            self.compression_ratio = self.compressed_token_count / self.original_token_count
        else:
            self.compression_ratio = 0.0


class ContextCompactor:
    """4-tier context compaction pipeline.

    This is the second-highest-ROI improvement because it allows the agent
    to maintain deep context while staying within token limits. The 4-tier
    approach provides:
    - Tier 1: Raw messages (full detail, high token count)
    - Tier 2: Summarized messages (compressed but detailed)
    - Tier 3: Abstracted context (high-level summary)
    - Tier 4: Persistent memory (CLAUDE.md style, permanent)
    """

    def __init__(
        self,
        max_tokens: int = 128000,
        embedder_client: EmbedderClient | None = None,
    ) -> None:
        """Initialize the context compactor.

        Args:
            max_tokens: Maximum token budget for context.
            embedder_client: Optional EmbedderClient for semantic compression.
        """
        self.max_tokens = max_tokens
        self._embedder = embedder_client
        self.tiers: dict[int, ContextTier] = {}
        self.compaction_history: list[CompactionResult] = []
        self._embedding_cache: dict[str, list[float]] = {}

    def compact_context(
        self,
        messages: list[dict[str, Any]],
        current_tokens: int,
    ) -> CompactionResult:
        """Compact context using the 4-tier pipeline.

        Args:
            messages: List of conversation messages.
            current_tokens: Current token count.

        Returns:
            CompactionResult with compressed context.
        """
        if current_tokens <= self.max_tokens:
            # No compaction needed
            return CompactionResult(
                original_token_count=current_tokens,
                compressed_token_count=current_tokens,
                compression_ratio=1.0,
                tiers=[],
                summary="No compaction needed",
            )

        # Tier 1: Keep recent raw messages (last 10)
        recent_messages = messages[-10:] if len(messages) > 10 else messages
        tier1_content = self._format_messages(recent_messages)
        tier1 = ContextTier(
            tier=1,
            name="Recent Raw Messages",
            content=tier1_content,
            token_estimate=len(tier1_content) // 4,  # Rough estimate
            description="Last 10 messages in full detail",
        )

        # Tier 2: Summarize older messages
        older_messages = messages[:-10] if len(messages) > 10 else []
        tier2_content = self._summarize_messages(older_messages)
        tier2 = ContextTier(
            tier=2,
            name="Summarized History",
            content=tier2_content,
            token_estimate=len(tier2_content) // 4,
            description="Summarized older messages",
        )

        # Tier 3: Abstract context
        tier3_content = self._abstract_context(messages)
        tier3 = ContextTier(
            tier=3,
            name="Abstract Context",
            content=tier3_content,
            token_estimate=len(tier3_content) // 4,
            description="High-level summary of conversation",
        )

        # Tier 4: Persistent memory (CLAUDE.md style)
        tier4_content = self._extract_persistent_memory(messages)
        tier4 = ContextTier(
            tier=4,
            name="Persistent Memory",
            content=tier4_content,
            token_estimate=len(tier4_content) // 4,
            description="CLAUDE.md style persistent context",
        )

        self.tiers = {1: tier1, 2: tier2, 3: tier3, 4: tier4}

        # Calculate total compressed token count
        total_compressed = sum(t.token_estimate for t in self.tiers.values())

        result = CompactionResult(
            original_token_count=current_tokens,
            compressed_token_count=total_compressed,
            compression_ratio=total_compressed / current_tokens if current_tokens > 0 else 0,
            tiers=list(self.tiers.values()),
            summary=f"Compressed from {current_tokens} to {total_compressed} tokens ({total_compressed/current_tokens*100:.1f}% of original)",
        )

        self.compaction_history.append(result)
        return result

    def _format_messages(self, messages: list[dict[str, Any]]) -> str:
        """Format messages for Tier 1 (raw).

        Args:
            messages: List of messages to format.

        Returns:
            Formatted message string.
        """
        lines = []
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            lines.append(f"[{role.upper()}]: {content[:500]}")  # Limit length
        return "\n".join(lines)

    def _summarize_messages(self, messages: list[dict[str, Any]]) -> str:
        """Summarize messages for Tier 2 (compressed).

        Args:
            messages: List of messages to summarize.

        Returns:
            Summarized message string.
        """
        if not messages:
            return "No older messages to summarize"

        # Group by role and summarize
        user_messages = [m for m in messages if m.get('role') == 'user']
        assistant_messages = [m for m in messages if m.get('role') == 'assistant']

        summary_parts = []

        if user_messages:
            summary_parts.append(f"User asked {len(user_messages)} questions:")
            for msg in user_messages[:5]:  # Limit to 5
                content = msg.get('content', '')[:200]
                summary_parts.append(f"- {content}")

        if assistant_messages:
            summary_parts.append(f"\nAssistant provided {len(assistant_messages)} responses:")
            for msg in assistant_messages[:5]:  # Limit to 5
                content = msg.get('content', '')[:200]
                summary_parts.append(f"- {content}")

        return "\n".join(summary_parts)

    def _abstract_context(self, messages: list[dict[str, Any]]) -> str:
        """Create abstract context for Tier 3 (high-level).

        Args:
            messages: List of messages to abstract.

        Returns:
            Abstracted context string.
        """
        if not messages:
            return "No context to abstract"

        # Extract key topics and decisions
        topics = set()
        decisions = []

        for msg in messages:
            content = msg.get('content', '').lower()
            # Simple topic extraction
            if 'error' in content or 'fix' in content:
                topics.add('error_handling')
            if 'test' in content or 'verify' in content:
                topics.add('testing')
            if 'implement' in content or 'build' in content:
                topics.add('implementation')
            if 'plan' in content or 'design' in content:
                topics.add('planning')

        return (
            f"Conversation topics: {', '.join(topics) if topics else 'general'}\n"
            f"Total messages: {len(messages)}\n"
            f"Key decisions: {len(decisions)}"
        )

    def _extract_persistent_memory(self, messages: list[dict[str, Any]]) -> str:
        """Extract persistent memory for Tier 4 (CLAUDE.md style).

        Args:
            messages: List of messages to extract from.

        Returns:
            Persistent memory string.
        """
        if not messages:
            return "# Persistent Memory\n\nNo persistent memory extracted."

        # Extract user preferences and corrections
        preferences = []
        corrections = []

        for msg in messages:
            content = msg.get('content', '')
            if 'remember' in content.lower() or 'prefer' in content.lower():
                preferences.append(content[:200])
            if 'fix' in content.lower() or 'correct' in content.lower():
                corrections.append(content[:200])

        memory_parts = ["# Persistent Memory\n"]

        if preferences:
            memory_parts.append("\n## User Preferences\n")
            for pref in preferences[:5]:
                memory_parts.append(f"- {pref}")

        if corrections:
            memory_parts.append("\n## Corrections\n")
            for corr in corrections[:5]:
                memory_parts.append(f"- {corr}")

        return "\n".join(memory_parts)

    def get_compacted_context(self) -> str:
        """Get the full compacted context from all tiers.

        Returns:
            Combined context string from all tiers.
        """
        if not self.tiers:
            return "No compacted context available"

        parts = []
        for tier_num in sorted(self.tiers.keys()):
            tier = self.tiers[tier_num]
            parts.append(f"## {tier.name} (Tier {tier.tier})\n{tier.content}")

        return "\n\n".join(parts)

    def get_compaction_stats(self) -> dict[str, Any]:
        """Get statistics about compaction operations.

        Returns:
            Dictionary with compaction statistics.
        """
        if not self.compaction_history:
            return {"total_compactions": 0}

        ratios = [r.compression_ratio for r in self.compaction_history]
        return {
            "total_compactions": len(self.compaction_history),
            "average_ratio": sum(ratios) / len(ratios),
            "best_ratio": min(ratios),
            "worst_ratio": max(ratios),
            "last_summary": self.compaction_history[-1].summary,
        }

    async def _get_embedding(self, text: str) -> list[float] | None:
        """Get embedding for text, using cache if available.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector, or None if embedder unavailable.
        """
        if self._embedder is None:
            return None
        if text in self._embedding_cache:
            return self._embedding_cache[text]
        try:
            result = await self._embedder.embed(text)
            if result.embeddings:
                vec = result.embeddings[0]
                self._embedding_cache[text] = vec
                return vec
        except Exception as e:
            logger.debug(f"Embedding failed for '{text[:50]}...': {e}")
        return None

    async def semantic_compress(
        self,
        messages: list[dict[str, Any]],
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Compress messages using embedding-based relevance to a query.

        Embeds the query and all messages, then returns only the most
        relevant ones. This is more efficient than keyword matching for
        complex queries.

        Args:
            messages: List of conversation messages.
            query: The query to find relevant messages for.
            top_k: Number of relevant messages to return.

        Returns:
            List of the most relevant messages.
        """
        if self._embedder is None:
            # Fallback: return all messages
            return messages

        # Build text representations
        texts: list[str] = []
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            texts.append(f"[{role}] {content[:500]}")

        if not texts:
            return messages

        # Embed query and all messages
        query_vec = await self._get_embedding(query)
        if query_vec is None:
            return messages

        msg_vecs: list[list[float]] = []
        for text in texts:
            vec = await self._get_embedding(text)
            if vec is not None:
                msg_vecs.append(vec)

        if not msg_vecs:
            return messages

        # Compute similarities
        from src.tektos.runtime.embedder import cosine_similarity
        scored: list[tuple[float, int]] = []
        for i, vec in enumerate(msg_vecs):
            sim = cosine_similarity(query_vec, vec)
            scored.append((sim, i))

        scored.sort(key=lambda x: x[0], reverse=True)
        relevant_indices = {idx for _, idx in scored[:top_k]}

        return [msg for i, msg in enumerate(messages) if i in relevant_indices]
