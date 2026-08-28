#!/usr/bin/env python3
"""Test multi-turn chat via gateway proxy WebSocket."""

import asyncio
import json
import sys
import uuid

import websockets

GATEWAY_URL = "ws://127.0.0.1:8765"


async def json_rpc_call(ws, method, params, request_id=None):
    """Send a JSON-RPC request and wait for the response."""
    if request_id is None:
        request_id = str(uuid.uuid4())
    msg = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    await ws.send(json.dumps(msg))
    # Read responses until we get the one matching our request_id
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        data = json.loads(raw)
        if data.get("id") == request_id:
            return data
        # Otherwise it's a notification, ignore


async def collect_notifications(ws, stop_event, results, timeout=5):
    """Collect notifications (non-response messages) until stop_event is set."""
    try:
        while not stop_event.is_set():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
                data = json.loads(raw)
                if "id" not in data:
                    results.append(data)
            except asyncio.TimeoutError:
                continue
    except Exception as e:
        print(f"  [collector] error: {e}")


async def test_multi_turn():
    print("=" * 60)
    print("Multi-turn chat test via gateway proxy")
    print("=" * 60)

    # Connect to gateway proxy
    print("\n[1] Connecting to gateway proxy...")
    async with websockets.connect(GATEWAY_URL) as ws:
        # Collect ready notification
        ready = await asyncio.wait_for(ws.recv(), timeout=5)
        ready_data = json.loads(ready)
        print(f"  Got: {json.dumps(ready_data, indent=2)[:200]}")

        # Create a session
        print("\n[2] Creating session...")
        resp = await json_rpc_call(ws, "session.create", {"cwd": "/home/rmholston/dev/tektos-ultima-v1"})
        if "error" in resp:
            print(f"  ERROR: {resp['error']}")
            return False
        session_id = resp["result"]["session_id"]
        print(f"  Session created: {session_id[:16]}...")

        # Collect notifications after session creation
        await asyncio.sleep(1)

        # Turn 1: Send a prompt
        print("\n[3] Turn 1: Sending prompt 'What is 2+2?'")
        resp = await json_rpc_call(ws, "prompt.submit", {
            "session_id": session_id,
            "text": "What is 2+2? Answer with just the number.",
        })
        if "error" in resp:
            print(f"  ERROR: {resp['error']}")
            return False
        print(f"  Prompt submitted: {resp['result']}")

        # Wait for assistant response
        print("  Waiting for assistant response...")
        assistant_text = ""
        turn1_done = False
        for _ in range(60):  # 60 seconds max
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(raw)
                if "id" in data:
                    continue  # Response to our request
                params = data.get("params", {})
                event_type = params.get("type", "")
                payload = params.get("payload", {})
                if event_type == "assistant.delta":
                    delta = payload.get("text", "")
                    if delta:
                        assistant_text += delta
                        sys.stdout.write(delta)
                        sys.stdout.flush()
                elif event_type == "assistant.completed":
                    print("\n  [assistant.completed received]")
                    turn1_done = True
                    break
                elif event_type == "session.failed":
                    print(f"\n  [session.failed: {payload.get('error', 'unknown')}]")
                    return False
            except asyncio.TimeoutError:
                pass

        if not turn1_done:
            print("\n  ERROR: Turn 1 did not complete in time")
            return False

        print(f"\n  Turn 1 response: '{assistant_text.strip()}'")

        # Small delay before turn 2
        await asyncio.sleep(1)

        # Turn 2: Send another prompt (this is where the bug was)
        print("\n[4] Turn 2: Sending prompt 'What is 3*3?'")
        resp = await json_rpc_call(ws, "prompt.submit", {
            "session_id": session_id,
            "text": "What is 3*3? Answer with just the number.",
        })
        if "error" in resp:
            print(f"  ERROR: {resp['error']}")
            return False
        print(f"  Prompt submitted: {resp['result']}")

        # Wait for assistant response
        print("  Waiting for assistant response...")
        assistant_text2 = ""
        turn2_done = False
        for _ in range(60):
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(raw)
                if "id" in data:
                    continue
                params = data.get("params", {})
                event_type = params.get("type", "")
                payload = params.get("payload", {})
                if event_type == "assistant.delta":
                    delta = payload.get("text", "")
                    if delta:
                        assistant_text2 += delta
                        sys.stdout.write(delta)
                        sys.stdout.flush()
                elif event_type == "assistant.completed":
                    print("\n  [assistant.completed received]")
                    turn2_done = True
                    break
                elif event_type == "session.failed":
                    print(f"\n  [session.failed: {payload.get('error', 'unknown')}]")
                    return False
            except asyncio.TimeoutError:
                pass

        if not turn2_done:
            print("\n  ERROR: Turn 2 did not complete in time — MULTI-TURN BUG CONFIRMED")
            return False

        print(f"\n  Turn 2 response: '{assistant_text2.strip()}'")

        # Turn 3: Third prompt to be thorough
        await asyncio.sleep(1)
        print("\n[5] Turn 3: Sending prompt 'What is 10-7?'")
        resp = await json_rpc_call(ws, "prompt.submit", {
            "session_id": session_id,
            "text": "What is 10-7? Answer with just the number.",
        })
        if "error" in resp:
            print(f"  ERROR: {resp['error']}")
            return False
        print(f"  Prompt submitted: {resp['result']}")

        print("  Waiting for assistant response...")
        assistant_text3 = ""
        turn3_done = False
        for _ in range(60):
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(raw)
                if "id" in data:
                    continue
                params = data.get("params", {})
                event_type = params.get("type", "")
                payload = params.get("payload", {})
                if event_type == "assistant.delta":
                    delta = payload.get("text", "")
                    if delta:
                        assistant_text3 += delta
                        sys.stdout.write(delta)
                        sys.stdout.flush()
                elif event_type == "assistant.completed":
                    print("\n  [assistant.completed received]")
                    turn3_done = True
                    break
                elif event_type == "session.failed":
                    print(f"\n  [session.failed: {payload.get('error', 'unknown')}]")
                    return False
            except asyncio.TimeoutError:
                pass

        if not turn3_done:
            print("\n  ERROR: Turn 3 did not complete in time")
            return False

        print(f"\n  Turn 3 response: '{assistant_text3.strip()}'")

        # Close session
        print("\n[6] Closing session...")
        resp = await json_rpc_call(ws, "session.close", {"session_id": session_id})
        print(f"  Session closed: {resp['result']}")

    print("\n" + "=" * 60)
    print("SUCCESS: All 3 turns completed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_multi_turn())
    sys.exit(0 if success else 1)
