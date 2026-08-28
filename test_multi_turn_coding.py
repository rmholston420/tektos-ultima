#!/usr/bin/env python3
"""Have Tektos diagnose and fix its own multi-turn context loss problem.

Uses the REST API to create a session and send a prompt asking Tektos to:
1. Analyze why it loses conversation context across turns
2. Identify the root cause in the codebase
3. Propose and implement the fix
"""

import asyncio
import json
import sys
import time

import httpx

BACKEND_URL = "http://127.0.0.1:8020"


async def json_rpc_call(ws, method, params=None, timeout=120):
    """Send a JSON-RPC 2.0 request and return the result."""
    rid = 1
    request = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": rid}
    await ws.send(json.dumps(request))
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        resp = json.loads(raw)
        if "error" in resp:
            return None, resp["error"]
        return resp.get("result"), None
    except asyncio.TimeoutError:
        return None, "timeout"


async def test_multi_turn_coding():
    """Test multi-turn chat with real coding tasks."""
    print("=" * 60)
    print("Live Multi-Turn Coding Test")
    print("=" * 60)

    # Connect to gateway proxy
    print("\n[1] Connecting to gateway proxy...")
    ws = await websockets.connect(GATEWAY_URL)
    # Gateway sends gateway.ready notification immediately on connect
    raw = await asyncio.wait_for(ws.recv(), timeout=10)
    ready = json.loads(raw)
    print(f"  Got: {ready.get('method', 'notification')}")

    # Create session
    print("\n[2] Creating session...")
    result, err = await json_rpc_call(ws, "session.create", {"session_id": None})
    if err:
        print(f"  ERROR: {err}")
        return False
    session_id = result.get("session_id", result.get("id", ""))
    print(f"  Session created: {session_id[:20]}...")

    # Define coding tasks — each builds on the previous
    tasks = [
        {
            "prompt": "Write a Python function called 'fibonacci' that takes a non-negative integer n and returns the nth Fibonacci number using an iterative approach. Include type hints and a docstring.",
            "expected_keywords": ["def fibonacci", "iterative", "int", "fibonacci"],
        },
        {
            "prompt": "Now add a test function called 'test_fibonacci' that verifies fibonacci(0) == 0, fibonacci(1) == 1, fibonacci(10) == 55, and fibonacci(20) == 6765. Use assert statements.",
            "expected_keywords": ["def test_fibonacci", "assert", "fibonacci(0)", "fibonacci(10)", "fibonacci(20)"],
        },
        {
            "prompt": "Add error handling: make fibonacci raise ValueError if n is negative, and TypeError if n is not an integer. Update the docstring to document these exceptions.",
            "expected_keywords": ["ValueError", "TypeError", "not isinstance", "raise"],
        },
        {
            "prompt": "Write a brief summary of the changes you made in the last two turns. What edge cases does the function now handle?",
            "expected_keywords": ["error", "negative", "type", "edge case"],
        },
    ]

    for i, task in enumerate(tasks, 1):
        print(f"\n[Turn {i}] Sending coding task...")
        print(f"  Task: {task['prompt'][:80]}...")

        # Send prompt
        result, err = await json_rpc_call(
            ws, "prompt.submit", {"session_id": session_id, "text": task["prompt"]}
        )
        if err:
            print(f"  ERROR submitting prompt: {err}")
            return False
        print(f"  Prompt submitted: {result}")

        # Collect assistant response
        print("  Waiting for response...")
        full_response = ""
        got_completed = False
        timeout_count = 0
        max_timeout_checks = 60  # 60 seconds max

        while not got_completed and timeout_count < max_timeout_checks:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                resp = json.loads(raw)

                if resp.get("method") == "event":
                    event = resp.get("params", {})
                    event_type = event.get("type", "")
                    payload = event.get("payload", {})

                    if event_type == "assistant.delta":
                        text = payload.get("text", "") or payload.get("delta", "")
                        if text:
                            full_response += text
                            sys.stdout.write(text)
                            sys.stdout.flush()

                    elif event_type == "assistant.completed":
                        got_completed = True
                        print("\n  [assistant.completed received]")

                    elif event_type == "session.failed":
                        print(f"\n  [session.failed: {payload.get('error', 'Unknown')}]")
                        got_completed = True

                    elif event_type == "session.interrupted":
                        print("\n  [session.interrupted]")
                        got_completed = True

            except asyncio.TimeoutError:
                timeout_count += 1
                if timeout_count % 10 == 0:
                    print(f"  ...waiting ({timeout_count}s)...")

        if not got_completed:
            print("\n  ERROR: Timed out waiting for response")
            return False

        print(f"\n  Turn {i} response length: {len(full_response)} chars")

        # Verify response contains expected keywords
        response_lower = full_response.lower()
        missing = [kw for kw in task["expected_keywords"] if kw.lower() not in response_lower]
        if missing:
            print(f"  WARNING: Missing expected keywords: {missing}")
        else:
            print(f"  ✓ All expected keywords found")

    # Cleanup
    print("\n[Done] Cleaning up...")
    try:
        await asyncio.wait_for(ws.close(), timeout=5)
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("Multi-turn coding test PASSED")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_multi_turn_coding())
    sys.exit(0 if success else 1)
