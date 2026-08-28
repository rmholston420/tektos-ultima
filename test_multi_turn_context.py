#!/usr/bin/env python3
"""Test multi-turn chat to verify context persistence."""

import asyncio
import json
import sys
import time

import websockets

GATEWAY_URL = "ws://127.0.0.1:8765"


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


async def collect_response(ws, timeout=90):
    """Collect assistant response until assistant.completed or timeout."""
    full_response = ""
    got_completed = False
    start = time.time()

    while not got_completed and (time.time() - start) < timeout:
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
                    print("\n[assistant.completed]")

                elif event_type == "session.failed":
                    print(f"\n[session.failed: {payload.get('error', 'Unknown')}]")
                    got_completed = True

                elif event_type == "session.interrupted":
                    print("\n[session.interrupted]")
                    got_completed = True

        except asyncio.TimeoutError:
            pass

    return full_response, got_completed


async def main():
    print("=" * 60)
    print("Multi-Turn Context Persistence Test")
    print("=" * 60)

    # Connect
    print("\n[1] Connecting to gateway proxy...")
    ws = await websockets.connect(GATEWAY_URL)
    raw = await asyncio.wait_for(ws.recv(), timeout=10)
    ready = json.loads(raw)
    print(f"  Ready: {ready.get('method')}")

    # Create session
    print("\n[2] Creating session...")
    result, err = await json_rpc_call(ws, "session.create", {"session_id": None})
    if err:
        print(f"  ERROR: {err}")
        return False
    session_id = result.get("session_id", result.get("id", ""))
    print(f"  Session: {session_id[:20]}...")

    # Turn 1: Write a fibonacci function
    print("\n[Turn 1] Write a fibonacci function")
    result, err = await json_rpc_call(
        ws, "prompt.submit", {"session_id": session_id, "text": "Write a Python function called 'fibonacci' that takes a non-negative integer n and returns the nth Fibonacci number using an iterative approach. Include type hints and a docstring."}
    )
    if err:
        print(f"  ERROR: {err}")
        return False
    print(f"  Submitted: {result}")

    resp1, ok1 = await collect_response(ws)
    if not ok1:
        print("  Turn 1 FAILED - no response")
        return False
    print(f"\n  Turn 1 response: {len(resp1)} chars")

    # Turn 2: Ask about the fibonacci function — this tests context
    print("\n[Turn 2] Ask about the fibonacci function (tests context)")
    result, err = await json_rpc_call(
        ws, "prompt.submit", {"session_id": session_id, "text": "You just wrote a fibonacci function. What does it do? Show me the function signature and explain the approach."}
    )
    if err:
        print(f"  ERROR: {err}")
        return False
    print(f"  Submitted: {result}")

    resp2, ok2 = await collect_response(ws)
    if not ok2:
        print("  Turn 2 FAILED - no response")
        return False
    print(f"\n  Turn 2 response: {len(resp2)} chars")

    # Turn 3: Ask about error handling — tests if it remembers Turn 1
    print("\n[Turn 3] Ask about error handling (tests context)")
    result, err = await json_rpc_call(
        ws, "prompt.submit", {"session_id": session_id, "text": "Now add error handling to that fibonacci function: raise ValueError for negative numbers and TypeError for non-integers."}
    )
    if err:
        print(f"  ERROR: {err}")
        return False
    print(f"  Submitted: {result}")

    resp3, ok3 = await collect_response(ws)
    if not ok3:
        print("  Turn 3 FAILED - no response")
        return False
    print(f"\n  Turn 3 response: {len(resp3)} chars")

    # Verify context awareness
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    results = {
        "Turn 1": resp1,
        "Turn 2": resp2,
        "Turn 3": resp3,
    }

    # Check Turn 2 for context awareness
    t2_lower = resp2.lower()
    context_indicators = ["fibonacci", "def ", "iterative", "function", "approach"]
    missing_context = [ind for ind in context_indicators if ind not in t2_lower]

    if missing_context:
        print(f"✗ Turn 2 lacks context: missing indicators: {missing_context}")
        print(f"  Response preview: {resp2[:300]}")
    else:
        print(f"✓ Turn 2 shows context awareness (mentions fibonacci, function, approach)")

    # Check Turn 3 for context awareness
    t3_lower = resp3.lower()
    context_indicators_3 = ["fibonacci", "error", "valueerror", "typeerror", "negative", "integer"]
    missing_context_3 = [ind for ind in context_indicators_3 if ind not in t3_lower]

    if missing_context_3:
        print(f"✗ Turn 3 lacks context: missing indicators: {missing_context_3}")
        print(f"  Response preview: {resp3[:300]}")
    else:
        print(f"✓ Turn 3 shows context awareness (mentions fibonacci, error handling)")

    # Overall verdict
    if not missing_context and not missing_context_3:
        print("\n✓✓✓ MULTI-TURN CONTEXT PERSISTENCE WORKS ✓✓✓")
        return True
    else:
        print("\n✗✗✗ MULTI-TURN CONTEXT STILL BROKEN ✗✗✗")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
