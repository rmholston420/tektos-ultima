#!/usr/bin/env python3
"""Run all 5 hard Terminal-Bench tasks against Qwen3.8-27B.

Uses the SSE endpoint for streaming, then polls /api/sessions/{id}/events
for actual tool execution events (tool.started, tool.completed).
"""

import requests
import json
import os
import time
import sys

BACKEND = "http://localhost:8020"
TIMEOUT = 600  # 10 minutes per task

TASKS = [
    {
        "name": "regex-chess",
        "output_file": "/app/re.json",
        "prompt": (
            "You are working in a terminal environment. Your task is to solve the "
            "Terminal-Bench 2.1 \"regex-chess\" challenge.\n\n"
            "TASK:\n"
            "Write a JSON file called /app/re.json that is a list of [regex, replacement] pairs. "
            "When executed in order with the Python code:\n\n"
            "    import re\n"
            "    import json\n"
            "    def all_legal_next_positions(fen):\n"
            "        for pattern, repl in json.load(open(\"/app/re.json\")):\n"
            "            fen = re.sub(pattern, repl, fen)\n"
            "        return fen.split(\"\\n\")\n\n"
            "this function should return the FEN position for all possible legal next chess positions.\n\n"
            "CONSTRAINTS:\n"
            "- You will only be shown positions where it is WHITE to move\n"
            "- Any promotions will only be made to Queen (no underpromotion)\n"
            "- You do NOT need to track the full-move or half-move count (they can be wrong)\n"
            "- The length of re.json must be under 100,000 [regex, replacement]-pairs long\n"
            "- The file must be under 10 megabytes in total\n\n"
            "WHAT YOU MUST IMPLEMENT CORRECTLY:\n"
            "- Castling, with proper tracking of castling rights (kingside and queenside)\n"
            "- Promotion, except only allow promotion to queen\n"
            "- En-passant captures\n"
            "- All standard piece movements (pawns, knights, bishops, rooks, queens, kings)\n"
            "- A move is illegal if it leaves the king in check\n\n"
            "IMPORTANT: The file MUST be at /app/re.json. Write it using bash commands or file_write.\n\n"
            "Start by exploring the /app directory, then write your solution."
        )
    },
    {
        "name": "feal-crypto",
        "output_file": "/app/attack.py",
        "prompt": (
            "You are working in a terminal environment. Your task is to solve the "
            "Terminal-Bench 2.1 \"feal-differential-cryptanalysis\" challenge.\n\n"
            "TASK:\n"
            "Create a Python script at /app/attack.py that implements a differential "
            "cryptanalysis attack on the FEAL cipher.\n\n"
            "The script must:\n"
            "1. Implement the FEAL encryption function (4 rounds, 16-bit block)\n"
            "2. Generate random plaintext pairs with a specific XOR difference\n"
            "3. Use differential characteristics to find the last round key\n"
            "4. Output the recovered key\n\n"
            "Write the complete implementation to /app/attack.py using file_write or bash."
        )
    },
    {
        "name": "compile-compcert",
        "output_file": "/app/compcert",
        "prompt": (
            "You are working in a terminal environment. Your task is to compile CompCert from source.\n\n"
            "TASK:\n"
            "1. Use the pre-staged source tarball at /opt/tb-sources/compcert-3.17.tar.gz (already downloaded)\n"
            "2. Extract it to /tmp\n"
            "3. Build it with make (you may need to install dependencies: opam, coq, etc.)\n"
            "4. The final binary should be at /app/compcert\n\n"
            "Use bash commands to extract and compile. Start by checking what's available."
        )
    },
    {
        "name": "make-doom-for-mips",
        "output_file": "/app/doom_mips",
        "prompt": (
            "You are working in a terminal environment. Your task is to cross-compile DOOM for MIPS.\n\n"
            "TASK:\n"
            "1. Use the pre-staged doomgeneric source at /opt/tb-sources/doomgeneric.tar.gz (already downloaded)\n"
            "2. Extract it to /tmp\n"
            "3. The MIPS cross-toolchain is installed at /usr/local/mipsel (mipsel-linux-gnu-gcc). binutils-mipsel-linux-gnu and qemu-mipsel are also available.\n"
            "4. Create a Makefile that cross-compiles doomgeneric for MIPS using mipsel-linux-gnu-gcc\n"
            "5. Run make to produce the binary at /app/doom_mips\n\n"
            "Write the Makefile and build. Use bash commands."
        )
    },
    {
        "name": "build-pov-ray",
        "output_file": "/app/povray",
        "prompt": (
            "You are working in a terminal environment. Your task is to build POV-Ray from source.\n\n"
            "TASK:\n"
            "1. Use the pre-staged source tarball at /opt/tb-sources/povray-v3.8.0-beta.2-src.tar.gz (already downloaded)\n"
            "2. Extract it to /tmp\n"
            "3. Configure with ./configure (or cmake if available)\n"
            "4. Build with make\n"
            "5. The final binary should be at /app/povray\n\n"
            "Use bash commands to extract, configure, and build."
        )
    }
]


def create_session():
    resp = requests.post(f"{BACKEND}/api/sessions", json={
        "model": "Qwen3.8-27B-Q4_K_M",
        "cwd": "/home/rmholston/dev/tektos-ultima-v1",
        "provider": "local",
        "permission_mode": "auto",
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("id") or data.get("session_id")


def send_prompt_and_wait(session_id, prompt, timeout=600):
    """Send prompt via SSE and wait for completion. Returns the session events."""
    resp = requests.post(
        f"{BACKEND}/api/prompt/sse",
        json={"prompt": prompt, "session_id": session_id},
        stream=True,
        timeout=timeout,
    )
    resp.raise_for_status()

    # Consume the SSE stream (we don't parse it for tool events — those come from /events)
    for line in resp.iter_lines():
        if not line:
            continue
        line_str = line.decode("utf-8")
        if line_str == "data: [DONE]":
            break

    # Wait a moment for events to be persisted
    time.sleep(2)

    # Fetch the actual agent events from the events endpoint
    events_resp = requests.get(f"{BACKEND}/api/sessions/{session_id}/events", timeout=10)
    if events_resp.status_code == 200:
        return events_resp.json()
    return []


def analyze_events(events):
    """Analyze session events for tool calls and file writes."""
    tool_counts = {}
    file_writes = 0
    bash_commands = []
    errors = []

    for ev in events:
        etype = ev.get("type", "")
        payload = ev.get("payload", {})

        if etype == "tool.started":
            tool_name = payload.get("tool_name", "unknown")
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        elif etype == "tool.completed":
            tool_name = payload.get("tool_name", "unknown")
            output = payload.get("output", "")
            if tool_name == "file_write":
                file_writes += 1
            elif tool_name == "bash":
                bash_commands.append(output[:100])

        elif etype == "tool.failed":
            errors.append(payload.get("output", "")[:200])

    return {
        "tools": tool_counts,
        "file_writes": file_writes,
        "bash_count": len(bash_commands),
        "errors": errors,
    }


def run_task(task):
    print(f"\n{'='*60}")
    print(f"Running: {task['name']}")
    print(f"{'='*60}")

    start = time.time()

    # Per-task isolation: remove the previous task's output file so it can't
    # leak into this task (FS_ROOT is shared across all tasks).
    if os.path.exists(task["output_file"]):
        try:
            os.remove(task["output_file"])
            print(f"  Cleaned stale {task['output_file']}")
        except Exception as e:
            print(f"  WARN: could not remove {task['output_file']}: {e}")

    # Create session
    try:
        session_id = create_session()
        print(f"Session: {session_id}")
    except Exception as e:
        print(f"  ERROR creating session: {e}")
        return {"name": task["name"], "tools": {}, "file_writes": 0, "elapsed": "0s", "error": str(e)}

    # Send prompt and collect events
    try:
        events = send_prompt_and_wait(session_id, task["prompt"], timeout=TIMEOUT)
        analysis = analyze_events(events)
    except Exception as e:
        print(f"  Stream error: {e}")
        analysis = {"tools": {}, "file_writes": 0, "bash_count": 0, "errors": [str(e)]}

    elapsed = time.time() - start

    # Print tool activity
    if analysis["tools"]:
        print(f"  Tools used: {analysis['tools']}")
    else:
        print(f"  ⚠️  No tools were called!")

    if analysis["file_writes"] > 0:
        print(f"  File writes: {analysis['file_writes']}")

    if analysis["errors"]:
        for err in analysis["errors"][:3]:
            print(f"  ERROR: {err}")

    # Check if output file exists
    output_exists = os.path.exists(task["output_file"])
    if output_exists:
        size = os.path.getsize(task["output_file"])
        print(f"  ✅ Output file exists: {task['output_file']} ({size} bytes)")
    else:
        print(f"  ❌ Output file not found: {task['output_file']}")

    return {
        "name": task["name"],
        "tools": analysis["tools"],
        "file_writes": analysis["file_writes"],
        "bash_count": analysis["bash_count"],
        "elapsed": f"{elapsed:.0f}s",
        "output_exists": output_exists,
    }


def main():
    print("=" * 60)
    print("Terminal-Bench 2.1: 5 Hard Tasks — Qwen3.8-27B")
    print("=" * 60)

    # Check backend
    try:
        resp = requests.get(f"{BACKEND}/health", timeout=5)
        health = resp.json()
        print(f"Backend: LLM={health.get('llm_url')} model={health.get('llm_model')}")
    except Exception as e:
        print(f"Backend not running: {e}")
        sys.exit(1)

    results = []
    for task in TASKS:
        result = run_task(task)
        results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    passed = 0
    for r in results:
        status = "✅ PASS" if r.get("output_exists") else "❌ FAIL"
        if r.get("output_exists"):
            passed += 1
        tools_str = str(r['tools']) if r['tools'] else "NONE"
        print(f"{status} {r['name']:25s} tools={tools_str:40s} fw={r['file_writes']} bash={r.get('bash_count',0)} time={r['elapsed']}")

    print(f"\nScore: {passed}/{len(results)}")


if __name__ == "__main__":
    main()
