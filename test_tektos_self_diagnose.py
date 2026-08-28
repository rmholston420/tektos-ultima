#!/usr/bin/env python3
"""Have Tektos diagnose and fix its own multi-turn context loss problem."""

import asyncio
import json
import sys
import time

import httpx

BACKEND_URL = "http://127.0.0.1:8020"


async def send_prompt(client, session_id, prompt, label=""):
    """Send a prompt via SSE and collect the full response."""
    print(f"\n[{label}] Sending prompt...")
    print(f"  Prompt: {prompt[:120]}...")

    async with client.stream("POST", "/api/prompt/sse", json={
        "session_id": session_id,
        "prompt": prompt,
    }) as resp:
        print(f"  Status: {resp.status_code}")
        full_response = ""
        event_count = 0
        start = time.time()

        async for line in resp.aiter_lines():
            if not line or line.startswith(":"):
                continue
            if line.startswith("data:"):
                event_count += 1
                try:
                    d = json.loads(line[5:])
                    choices = d.get("choices", [])
                    if choices and choices[0].get("delta"):
                        delta = choices[0]["delta"]
                        content = delta.get("content", "") or delta.get("text", "")
                        if content:
                            full_response += content
                            sys.stdout.write(content)
                            sys.stdout.flush()
                except json.JSONDecodeError:
                    pass

        elapsed = time.time() - start
        print(f"\n  [{label}] Done: {event_count} events, {len(full_response)} chars, {elapsed:.0f}s")
        return full_response


async def main():
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30.0) as client:
        # Create session
        resp = await client.post("/api/sessions", json={"model": "Qwen_Qwen3.6-35B-A3B-Q4_K_M"})
        session_id = resp.json()["id"]
        print(f"Session created: {session_id}")

        # Turn 1: Ask Tektos to diagnose and fix its own context loss
        prompt1 = """I need you to diagnose and fix a critical bug in your own codebase.

PROBLEM: When I send multiple prompts in the same session via WebSocket, you lose all context from previous turns. Each turn starts fresh as if it's the first conversation.

ROOT CAUSE HYPOTHESIS: The Tektos backend's WebSocket handler (_handle_prompt in main.py) builds the LLM conversation from scratch each turn instead of accumulating messages. The session stores events in the event store, but the LLM call doesn't replay them.

YOUR TASK:
1. Read the relevant source files to understand how conversation context is built for LLM calls
2. Find where the conversation history should be accumulated but isn't
3. Implement the fix so that each turn includes all previous messages from the session
4. The fix should:
   - Load previous messages from the event store for the session
   - Build a proper conversation history (system prompt + all prior user/assistant exchanges)
   - Send the full history to the LLM on each turn
   - Append the new exchange to the session state after completion

Start by reading:
- src/tektos/main.py (the _handle_prompt function and WebSocket handler)
- src/tektos/runtime/sdk.py (how LLM calls are made, how messages are built)
- src/tektos/store/event_store.py (how events are stored and retrieved)
- src/tektos/runtime/session_state.py (session state management)

Be thorough. This is the most important feature for an autonomous coding agent.
"""

        resp1 = await send_prompt(client, session_id, prompt1, "Turn 1")

        # Wait for any file writes
        print("\nWaiting for background work...")
        await asyncio.sleep(8)

        # Turn 2: Test if Tektos remembers Turn 1
        prompt2 = """You previously analyzed my codebase and identified a bug. What did you find? Summarize the root cause and the fix you implemented.
"""

        resp2 = await send_prompt(client, session_id, prompt2, "Turn 2")

        # Check for context awareness
        print("\n" + "=" * 60)
        if "fibonacci" in resp2.lower() or "def " in resp2 or "context" in resp2.lower():
            print("✓ Turn 2 shows awareness of prior conversation")
        elif "no visibility" in resp2.lower() or "don't have" in resp2.lower() or "first turn" in resp2.lower():
            print("✗ Turn 2 still lacks context from Turn 1")
        else:
            print(f"? Turn 2 response: {resp2[:200]}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
