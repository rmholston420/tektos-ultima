#!/usr/bin/env python3
"""
Terminal-Bench 2.1 - regex-chess task for Tektos

Task: Write a JSON file /app/re.json containing [regex, replacement] pairs
that, when applied sequentially to a FEN position string, generates all
legal next chess positions for white.

Constraints:
- Under 100,000 pairs, under 10MB
- Must handle: castling (with rights tracking), en passant, queen-only promotion
- Move/half-move counters can be wrong
- Tested on multiple FEN positions

This script sets up the task environment and sends the prompt to Tektos.
"""

import requests
import json
import os
import time
import sys

BACKEND = "http://localhost:8020"
TEST_DIR = "/home/rmholston/dev/tektos-ultima-v1"
TIMEOUT = 3600  # 1 hour


def create_session():
    """Create a new Tektos session."""
    resp = requests.post(f"{BACKEND}/api/sessions", json={
        "model": "Qwen3.8-27B-Q4_K_M",
        "cwd": TEST_DIR,
        "provider": "local",
        "permission_mode": "auto",
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("session_id") or data.get("id")


def send_prompt(session_id, prompt, timeout=3600):
    """Send a prompt via SSE and collect events."""
    resp = requests.post(
        f"{BACKEND}/api/prompt/sse",
        json={"prompt": prompt, "session_id": session_id},
        stream=True,
        timeout=timeout,
    )
    resp.raise_for_status()

    events = []
    current_event = "unknown"
    for line in resp.iter_lines():
        if not line:
            continue
        line_str = line.decode("utf-8")
        if line_str.startswith("event: "):
            current_event = line_str[7:]
        elif line_str.startswith("data: "):
            data_str = line_str[6:]
            try:
                data = json.loads(data_str)
                events.append({"type": current_event, "data": data})
            except json.JSONDecodeError:
                pass
    return events


def check_file_exists(filepath, timeout=3600):
    """Wait for a file to appear."""
    start = time.time()
    last_progress = start
    while time.time() - start < timeout:
        if os.path.exists(filepath):
            return True
        now = time.time()
        if now - last_progress >= 60:
            elapsed = int(now - start)
            remaining = int(timeout - elapsed)
            print(f"  Waiting for file... {elapsed}s elapsed, {remaining}s remaining")
            last_progress = now
        time.sleep(5)
    return False


def verify_solution():
    """Run the regex-chess verification against the generated re.json."""
    re_json_path = "/app/re.json"
    if not os.path.exists(re_json_path):
        print(f"FAIL: {re_json_path} not found")
        return False

    with open(re_json_path, 'r') as f:
        re_pairs = json.load(f)

    print(f"OK: re.json found with {len(re_pairs)} pairs")

    # Check size constraints
    file_size = os.path.getsize(re_json_path)
    print(f"  File size: {file_size / 1024 / 1024:.2f} MB (limit: 10 MB)")
    if len(re_pairs) > 100000:
        print(f"  FAIL: Too many pairs: {len(re_pairs)} (limit: 100,000)")
        return False
    if file_size > 10 * 1024 * 1024:
        print(f"  FAIL: Too large: {file_size} bytes (limit: 10 MB)")
        return False

    # Test against the example position from the task
    import re as re_module

    def all_legal_next_positions(fen):
        for pattern, repl in re_pairs:
            fen = re_module.sub(pattern, repl, fen)
        return fen.split("\n")

    # Example position from the task
    test_fen = "rnb1k1nr/p2p1ppp/3B4/1p1NPN1P/6P1/3P1Q2/P1P5/q4Kb1 w kq - 0 1"

    expected_output = [
        "rnb1k1nr/p2p1ppp/3B4/1p1NPN1P/6P1/3P1Q2/P1P1K3/q5b1 b kq - 0 0",
        "rnb1k1nr/p2p1ppp/3B4/1p1NPN1P/6P1/3P1Q2/P1P3K1/q5b1 b kq - 0 0",
        "rnb1k1nr/p2p1ppp/3B4/1p1NPN1P/6P1/3P14/P1P5/q2Q1Kb1 b kq - 0 0",
    ]

    our_output = all_legal_next_positions(test_fen)
    our_output = [o.strip() for o in our_output if o.strip()]

    print(f"\n  Test position: {test_fen}")
    print(f"  Expected {len(expected_output)} moves, got {len(our_output)} moves")

    # Check each expected output is present (order may differ)
    expected_set = set(expected_output)
    our_set = set(our_output)

    missing = expected_set - our_set
    extra = our_set - expected_set

    if missing:
        print(f"  FAIL: Missing moves ({len(missing)}):")
        for m in missing:
            print(f"     {m}")
    if extra:
        print(f"  WARN: Extra moves ({len(extra)}):")
        for e in extra:
            print(f"     {e}")

    if not missing:
        print(f"  OK: All expected moves found!")
        return True
    else:
        print(f"  FAIL: {len(missing)} expected moves missing")
        return False


# The regex-chess task prompt
PROMPT = (
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
    "EXAMPLE:\n"
    'Input FEN: "rnb1k1nr/p2p1ppp/3B4/1p1NPN1P/6P1/3P1Q2/P1P5/q4Kb1 w kq - 0 1"\n\n'
    "Expected output (at least these 3 moves):\n"
    '"rnb1k1nr/p2p1ppp/3B4/1p1NPN1P/6P1/3P1Q2/P1P1K3/q5b1 b kq - 0 0"\n'
    '"rnb1k1nr/p2p1ppp/3B4/1p1NPN1P/6P1/3P1Q2/P1P3K1/q5b1 b kq - 0 0"\n'
    '"rnb1k1nr/p2p1ppp/3B4/1p1NPN1P/6P1/3P14/P1P5/q2Q1Kb1 b kq - 0 0"\n\n'
    "Note: The move number and half-move counter in the output can be wrong. "
    "Only the board position and castling rights matter.\n\n"
    "APPROACH:\n"
    "1. First, explore the /app directory to see if there are any helper files (check.py, test files, etc.)\n"
    "2. Study the FEN format carefully - each rank is separated by /, pieces are uppercase (white) or lowercase (black)\n"
    "3. Design regex patterns that transform the FEN string to represent each legal move\n"
    "4. You need to handle: pawn moves (single, double, capture, en passant), knight moves, "
    "bishop moves, rook moves, queen moves, king moves (including castling), pawn promotion\n"
    "5. Write the re.json file to /app/re.json\n"
    "6. Test your solution using the example position above\n"
    "7. Verify with any check.py or test files that may exist in /app\n\n"
    "IMPORTANT: The file MUST be at /app/re.json. Write it using bash commands (echo, cat with heredoc, or python).\n\n"
    "Start by exploring the /app directory, then write your solution."
)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Terminal-Bench 2.1: regex-chess")
    print("=" * 60)

    # Check backend
    try:
        resp = requests.get(f"{BACKEND}/health", timeout=5)
        resp.raise_for_status()
        health = resp.json()
        print(f"Backend running: LLM={health.get('llm_url', 'unknown')}")
    except Exception as e:
        print(f"Backend not running: {e}")
        sys.exit(1)

    # Create session
    session_id = create_session()
    print(f"Session created: {session_id}")

    # Send prompt
    print(f"\nSending prompt (timeout: {TIMEOUT}s = 1 hour)...")
    start_time = time.time()
    events = send_prompt(session_id, PROMPT, timeout=TIMEOUT)
    working_time = time.time() - start_time
    print(f"  Received {len(events)} events in {working_time:.1f}s")

    # Wait for /app/re.json
    print(f"\nWaiting for /app/re.json...")
    found = check_file_exists("/app/re.json", timeout=TIMEOUT)

    if not found:
        print(f"\n{'='*60}")
        print(f"FAIL: /app/re.json not created within {TIMEOUT}s")
        print(f"{'='*60}")
        sys.exit(1)

    # Verify
    print(f"\n{'='*60}")
    print("Verifying solution...")
    print(f"{'='*60}")
    passed = verify_solution()

    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    print(f"{'='*60}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
