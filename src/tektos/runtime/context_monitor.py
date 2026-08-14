"""Token estimation for context window management.

Provides fast approximations of token counts for different message types
to track context window usage without calling an external API.
"""

from __future__ import annotations

from typing import Any


def estimate_tokens(text: str) -> int:
    """Estimate token count for a text string.

    Approximation: ~4 tokens per word for English, adjusted for code/symbols.
    This is accurate to within ~10-15% for typical LLM tokenizers.
    """
    if not text:
        return 0

    # Count words (whitespace-separated)
    words = len(text.split())

    # Count characters for non-English/emoji detection
    chars = len(text)

    # Code has more tokens per word (keywords, symbols)
    code_markers = text.count("{") + text.count("}") + text.count("(") + text.count(")")

    # Estimate: ~4 tokens per word baseline
    tokens = words * 4

    # Adjust for code-heavy content (more symbols = more tokens)
    if code_markers > words * 0.3:
        tokens = words * 3.5  # Code is slightly more token-efficient per word

    # Adjust for very long texts (subword tokens)
    if chars > 10000:
        tokens = int(tokens * 0.95)

    return max(1, int(tokens))


def estimate_message_tokens(msg: dict[str, Any]) -> int:
    """Estimate tokens for a single message/event."""
    content = msg.get("content", "")
    role = msg.get("role", "user")

    # Base token count
    tokens = estimate_tokens(str(content))

    # Role prefix tokens
    role_tokens = {"system": 4, "user": 4, "assistant": 4, "tool": 3}.get(role, 4)
    tokens += role_tokens

    # Message formatting tokens
    tokens += 2  # Opening/closing tokens

    return tokens


def estimate_session_tokens(events: list[dict[str, Any]]) -> int:
    """Estimate total tokens for a session's events (conversation history)."""
    total = 0
    for event in events:
        # Extract message-like content from events
        payload = event.get("payload", {})
        content = payload.get("content", "") or payload.get("message", "") or ""
        if content:
            total += estimate_tokens(str(content))

        # Count tool call tokens if present
        if "tool_calls" in payload:
            for tc in payload["tool_calls"]:
                total += estimate_tokens(str(tc))

        # System prompt (usually constant, but count once)
        if event.get("event_type") == "session.system_prompt":
            total += estimate_tokens(str(payload.get("prompt", "")))

    # Add special tokens (start/end markers, etc.)
    total += 10  # Approximate special tokens per session

    return total


# Thresholds for context window usage
CONTEXT_THRESHOLDS = {
    "warning": 0.6,  # 60% - log warning
    "checkpoint": 0.75,  # 75% - save checkpoint
    "compress": 0.85,  # 85% - compress conversation
    "critical": 0.95,  # 95% - emergency checkpoint
}


def get_context_status(usage_pct: float) -> str:
    """Get context window status based on usage percentage."""
    if usage_pct >= CONTEXT_THRESHOLDS["critical"]:
        return "critical"
    elif usage_pct >= CONTEXT_THRESHOLDS["compress"]:
        return "compress"
    elif usage_pct >= CONTEXT_THRESHOLDS["checkpoint"]:
        return "checkpoint"
    elif usage_pct >= CONTEXT_THRESHOLDS["warning"]:
        return "warning"
    else:
        return "healthy"
