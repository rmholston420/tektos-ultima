"""Conversation compressor for context window management.

Automatically summarizes older conversation messages while preserving:
- Critical decisions and conclusions
- Code snippets and technical details
- User preferences and constraints
- Task progress and completion status
- Important tool outputs (especially errors)

Uses a tiered approach:
1. Keep all messages from the last N tokens (recent context)
2. Compress older messages into structured summaries
3. Preserve special markers for decisions, code, errors
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompressedMessage:
    """A compressed representation of one or more original messages."""
    original_start_token: int
    original_end_token: int
    summary: str
    preserved_elements: list[dict[str, Any]] = field(default_factory=list)
    message_count: int = 0
    has_decisions: bool = False
    has_code: bool = False
    has_errors: bool = False
    tags: list[str] = field(default_factory=list)


class ConversationCompressor:
    """Compresses conversation history while preserving critical context.
    
    This is a heuristic compressor that works without calling an external LLM.
    For better quality, integrate with a small local model (Qwen3-Embedding or similar).
    """
    
    def __init__(self, recent_tokens: int = 30000, max_compressed_size: int = 15000):
        self.recent_tokens = recent_tokens  # Keep this many tokens uncompressed
        self.max_compressed_size = max_compressed_size  # Max tokens for compressed history
    
    def compress(
        self,
        events: list[dict[str, Any]],
        max_total_tokens: int,
    ) -> tuple[list[dict[str, Any]], list[CompressedMessage]]:
        """Compress events to fit within max_total_tokens.
        
        Returns:
            Tuple of (compressed_events, compressed_messages) where:
            - compressed_events: New events list with summaries replacing old messages
            - compressed_messages: List of CompressedMessage objects for reference
        """
        if not events:
            return events, []
        
        # Step 1: Estimate tokens per event
        tokenized = []
        cumulative = 0
        for i, event in enumerate(events):
            tokens = self._estimate_event_tokens(event)
            cumulative += tokens
            tokenized.append((i, event, tokens, cumulative))
        
        total_tokens = cumulative
        
        # If we're already under budget, return as-is
        if total_tokens <= max_total_tokens:
            return events, []
        
        # Step 2: Identify recent events to keep uncompressed
        recent_start = 0
        cumulative_recent = 0
        for i, event, tokens, cum in tokenized:
            if cumulative_recent < self.recent_tokens:
                cumulative_recent += tokens
                recent_start = i
            else:
                break
        
        # Step 3: Compress older events
        old_events = tokenized[:recent_start]
        if not old_events:
            # Can't compress enough, just trim from the very beginning
            return self._trim_events(tokenized, max_total_tokens), []
        
        compressed_messages = self._compress_old_events(old_events, events)
        
        # Step 4: Create summary events
        summary_events = self._create_summary_events(compressed_messages, events)
        
        # Step 5: Combine with recent events
        recent_events = [ev for _, ev, _, _ in tokenized[recent_start:]]
        compressed_events = summary_events + recent_events
        
        return compressed_events, compressed_messages
    
    def _estimate_event_tokens(self, event: dict[str, Any]) -> int:
        """Estimate token count for an event."""
        payload = event.get("payload", {})
        content = str(payload.get("content", "") or payload.get("message", ""))
        
        # Simple word count * 4 (rough token approximation)
        words = len(content.split())
        tokens = words * 4
        
        # Add overhead for metadata
        tokens += 10
        
        # Tool calls are verbose
        if "tool_calls" in payload:
            for tc in payload["tool_calls"]:
                tokens += len(str(tc)) * 3
        
        return max(1, tokens)
    
    def _compress_old_events(
        self,
        old_events: list[tuple[int, dict, int, int]],
        all_events: list[dict[str, Any]],
    ) -> list[CompressedMessage]:
        """Compress old events into grouped summaries."""
        messages = []
        
        # Group events by type and semantic proximity
        groups = self._group_events(old_events)
        
        for group_key, group_events in groups.items():
            if not group_events:
                continue
            
            # Extract preserved elements
            preserved = self._extract_preserved(group_events, all_events)
            
            # Create summary
            summary = self._generate_summary(group_key, group_events, preserved)
            
            first_idx = group_events[0][0]
            last_idx = group_events[-1][0]
            
            msg = CompressedMessage(
                original_start_token=first_idx,
                original_end_token=last_idx,
                summary=summary,
                preserved_elements=preserved,
                message_count=len(group_events),
                has_decisions=any("decision" in str(e).lower() for e in preserved),
                has_code=any("code" in str(e).get("type", "").lower() for e in preserved),
                has_errors=any("error" in str(e).get("type", "").lower() for e in preserved),
                tags=group_key.split("_"),
            )
            messages.append(msg)
        
        return messages
    
    def _group_events(
        self,
        events: list[tuple[int, dict, int, int]]
    ) -> dict[str, list[tuple[int, dict, int, int]]]:
        """Group events by type and proximity."""
        groups = {}
        current_group = []
        current_key = None
        
        for idx, event, tokens, cum in events:
            event_type = event.get("event_type", "unknown")
            role = event.get("role", "")
            
            # Create group key based on event type and proximity
            if current_key is None:
                current_key = f"{role}_{event_type}"
                current_group = [(idx, event, tokens, cum)]
            elif f"{role}_{event_type}" == current_key:
                # Same type, continue group
                current_group.append((idx, event, tokens, cum))
            else:
                # Different type, save current group and start new one
                if current_group:
                    groups[current_key] = current_group
                current_key = f"{role}_{event_type}"
                current_group = [(idx, event, tokens, cum)]
        
        # Don't forget the last group
        if current_group:
            groups[current_key] = current_group
        
        return groups
    
    def _extract_preserved(
        self,
        group_events: list[tuple[int, dict, int, int]],
        all_events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract elements that must be preserved (decisions, code, errors)."""
        preserved = []
        
        for idx, event, tokens, cum in group_events:
            payload = event.get("payload", {})
            
            # Preserve decisions
            if payload.get("type") in ("decision", "conclusion", "resolution"):
                preserved.append({
                    "type": "decision",
                    "content": payload.get("content", ""),
                })
            
            # Preserve code blocks
            if "code" in str(payload).lower() or payload.get("type") == "code":
                preserved.append({
                    "type": "code",
                    "content": payload.get("content", ""),
                })
            
            # Preserve errors
            if payload.get("type") in ("error", "exception") or "error" in str(payload).lower():
                preserved.append({
                    "type": "error",
                    "content": payload.get("content", ""),
                    "traceback": payload.get("traceback", ""),
                })
            
            # Preserve user constraints/preferences
            if "constraint" in str(payload).lower() or "preference" in str(payload).lower():
                preserved.append({
                    "type": "constraint",
                    "content": payload.get("content", ""),
                })
        
        return preserved
    
    def _generate_summary(
        self,
        group_key: str,
        group_events: list[tuple[int, dict, int, int]],
        preserved: list[dict[str, Any]],
    ) -> str:
        """Generate a human-readable summary of a group of events."""
        role, event_type = group_key.split("_", 1)
        
        # Count by sub-type
        sub_types = {}
        for _, event, _, _ in group_events:
            payload = event.get("payload", {})
            sub = payload.get("type", "other")
            sub_types[sub] = sub_types.get(sub, 0) + 1
        
        # Build summary
        parts = [f"[{role.upper()} {event_type} x{len(group_events)}]"]
        
        # Add sub-type breakdown
        if sub_types:
            parts.append(f" ({', '.join(f'{k}={v}' for k, v in sub_types.items())})")
        
        # Add preserved elements summary
        if preserved:
            types = set(p["type"] for p in preserved)
            parts.append(f" | preserved: {', '.join(types)}")
        
        # Add token count
        total_tokens = sum(t for _, _, t, _ in group_events)
        parts.append(f" | ~{total_tokens} tokens")
        
        # For code-heavy groups, include a brief content preview
        code_count = sum(1 for p in preserved if p["type"] == "code")
        if code_count > 0:
            parts.append(f" | {code_count} code block(s)")
        
        return "".join(parts)
    
    def _create_summary_events(
        self,
        messages: list[CompressedMessage],
        all_events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Create system events to replace compressed messages."""
        events = []
        
        for i, msg in enumerate(messages):
            # Create a single summary event
            summary_text = msg.summary
            
            # Add preserved details if significant
            if msg.preserved_elements:
                details = []
                for elem in msg.preserved_elements[:5]:  # Limit to 5 preserved elements
                    details.append(f"- [{elem['type']}] {elem['content'][:100]}")
                if details:
                    summary_text += "\nPreserved:\n" + "\n".join(details)
            
            events.append({
                "event_type": "session.summary",
                "timestamp": "",  # Approximate timestamp
                "payload": {
                    "content": summary_text,
                    "compressed_from": f"events {msg.original_start_token}-{msg.original_end_token}",
                    "message_count": msg.message_count,
                    "preserved_count": len(msg.preserved_elements),
                },
            })
        
        return events
    
    def _trim_events(
        self,
        tokenized: list[tuple[int, dict, int, int]],
        max_total_tokens: int,
    ) -> list[dict[str, Any]]:
        """Emergency trim: remove events from the beginning until under budget."""
        events = []
        cumulative = 0
        
        for idx, event, tokens, cum in tokenized:
            if cumulative + tokens > max_total_tokens:
                # Add a summary of trimmed events instead
                events.append({
                    "event_type": "session.trimmed",
                    "timestamp": "",
                    "payload": {
                        "content": f"[Trimmed {idx} earlier events to fit context window]",
                        "trimmed_count": idx,
                    },
                })
                break
            
            events.append(event)
            cumulative += tokens
        
        return events
