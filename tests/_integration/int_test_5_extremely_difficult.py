"""
if __name__ == "__main__":
    Tektos-Ultima v1 — 5 Extremely Difficult Coding Tests

    Extremely difficult = systems-level programming, complex algorithms, or multi-component architectures.
    Each test uses simplified prompts and 900s timeout.
    """

    import requests
    import json
    import os
    import time
    import sys

    BACKEND = "http://localhost:8020"
    TEST_DIR = "/home/rmholston/dev/tektos-ultima-v1"
    TIMEOUT = 900
    PROGRESS_INTERVAL = 60


    def create_session():
    resp = requests.post(f"{BACKEND}/api/sessions", json={
    "model": "Qwen_Qwen3.6-35B-A3B-Q5_K_M",
    "cwd": TEST_DIR,
    "provider": "local",
    "permission_mode": "auto"
    })
    resp.raise_for_status()
    data = resp.json()
    return data.get("session_id") or data.get("id")


    def send_prompt(session_id, prompt, timeout=900):
    resp = requests.post(
    f"{BACKEND}/api/prompt/sse",
    json={"prompt": prompt, "session_id": session_id},
    stream=True,
    timeout=timeout
    )
    resp.raise_for_status()
    
    events = []
    current_event = "unknown"
    
    for line in resp.iter_lines():
    if not line:
    continue
    if line.startswith(b"event: "):
    current_event = line[7:].decode()
    elif line.startswith(b"data: "):
    data = json.loads(line[6:].decode())
    events.append({"type": current_event, "data": data})
    
    return events


    def check_file_exists(filepath, timeout=900):
    start = time.time()
    last_progress = start
    
    while time.time() - start < timeout:
    if os.path.exists(filepath):
    return True
    now = time.time()
    if now - last_progress >= PROGRESS_INTERVAL:
    elapsed = int(now - start)
    remaining = int(timeout - elapsed)
    print(f"  ⏳ Waiting for file... {elapsed}s elapsed, {remaining}s remaining")
    last_progress = now
    time.sleep(5)
    return False


    def read_file_content(filepath):
    with open(filepath, 'r') as f:
    return f.read()


    def verify_file(filepath, checks, test_name):
    if not check_file_exists(filepath, timeout=TIMEOUT):
    print(f"❌ {test_name}: File not created within {TIMEOUT}s")
    return False
    
    content = read_file_content(filepath)
    print(f"✅ {test_name}: File created ({len(content)} bytes)")
    
    try:
    compile(content, filepath, 'exec')
    print(f"  ✅ Valid Python syntax")
    except SyntaxError as e:
    print(f"  ❌ Syntax error: {e}")
    return False
    
    all_passed = True
    for keyword, name in checks:
    if keyword in content:
    print(f"  ✅ {name} found")
    else:
    print(f"  ❌ {name} NOT found")
    all_passed = False
    
    return all_passed


    # ─── 5 Extremely Difficult Tests ───────────────────────────────────────────────






    def test_minimal_compiler():
    """Extremely Difficult 1: Minimal compiler with lexer, parser, and evaluator."""
    print("\n🔴 Extremely Difficult 1: Minimal Compiler")
    session_id = create_session()
    
    prompt = """Write a minimal programming language compiler in Python at /tmp/compiler.py.

    Requirements:
    1. Lexer: tokenize expressions (numbers, +, -, *, /, parens, identifiers, =)
    2. Parser: recursive descent parser producing an AST (Expr, BinOp, Number, Assign, Var)
    3. Evaluator: execute the AST and return results
    4. run(source) function that chains lexer → parser → evaluator
    5. main() demonstrates: variable assignment, arithmetic expressions, order of operations

    Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/compiler.py", [
    ("Lexer", "Lexer class"),
    ("Parser", "Parser class"),
    ("AST", "AST node classes"),
    ("Evaluator", "Evaluator class"),
    ("run", "run function"),
    ("main", "main function"),
    ], "Extremely Difficult 1: Minimal Compiler")









    def test_btree_db():
    """Extremely Difficult 2: B-Tree based key-value store with transactions."""
    print("\n🔴 Extremely Difficult 2: B-Tree Database")
    session_id = create_session()
    
    prompt = """Write a B-Tree based key-value store in Python at /tmp/btree_db.py.

    Requirements:
    1. BTree class with insert(key, value), search(key), delete(key), range_query(start, end)
    2. B-Tree with configurable order (default 3)
    3. Transaction support: begin(), commit(), rollback()
    4. main() demonstrates CRUD operations and transactions

    Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/btree_db.py", [
    ("BTree", "BTree class"),
    ("insert", "insert method"),
    ("search", "search method"),
    ("delete", "delete method"),
    ("range_query", "range_query method"),
    ("Transaction", "Transaction support"),
    ("main", "main function"),
    ], "Extremely Difficult 2: B-Tree Database")









    def test_cpu_emulator():
    """Extremely Difficult 3: Simple CPU emulator with assembly."""
    print("\n🔴 Extremely Difficult 3: CPU Emulator")
    session_id = create_session()
    
    prompt = """Write a simple CPU emulator in Python at /tmp/cpu_emulator.py.

    Requirements:
    1. CPU class with registers: A, B, C, PC, SP
    2. Instructions: LOAD, STORE, ADD, SUB, MUL, JMP, JZ, JNZ, HALT, PUSH, POP
    3. Memory: 256-byte addressable memory
    4. run(program) function that loads and executes assembly program
    5. main() demonstrates a program that computes factorial

    Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/cpu_emulator.py", [
    ("CPU", "CPU class"),
    ("LOAD", "LOAD instruction"),
    ("STORE", "STORE instruction"),
    ("ADD", "ADD instruction"),
    ("JMP", "JMP instruction"),
    ("HALT", "HALT instruction"),
    ("run", "run function"),
    ("main", "main function"),
    ], "Extremely Difficult 3: CPU Emulator")









    def test_suffix_tree():
    """Extremely Difficult 4: Suffix tree/array for string matching."""
    print("\n🔴 Extremely Difficult 4: Suffix Tree")
    session_id = create_session()
    
    prompt = """Write a suffix tree for string matching in Python at /tmp/suffix_tree.py.

    Requirements:
    1. SuffixTree class with build(text) and search(pattern)
    2. search returns all starting positions of pattern in text
    3. Also implement longest_repeated_substring(text)
    4. Use edge labels (start, end indices) for compact representation
    5. main() demonstrates search and longest repeated substring

    Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/suffix_tree.py", [
    ("SuffixTree", "SuffixTree class"),
    ("build", "build method"),
    ("search", "search method"),
    ("longest_repeated_substring", "longest_repeated_substring method"),
    ("main", "main function"),
    ], "Extremely Difficult 4: Suffix Tree")









    def test_network_protocol():
    """Extremely Difficult 5: TCP-like reliable data transfer protocol."""
    print("\n🔴 Extremely Difficult 5: Reliable Data Transfer Protocol")
    session_id = create_session()
    
    prompt = """Write a TCP-like reliable data transfer protocol simulator in Python at /tmp/protocol.py.

    Requirements:
    1. ReliableTransport class with send(data), receive(), acknowledge()
    2. Implements sliding window protocol with sequence numbers
    3. Handles packet loss simulation (random drop) and retransmission
    4. Flow control: window size management
    5. main() demonstrates sending a large message with simulated packet loss

    Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/protocol.py", [
    ("ReliableTransport", "ReliableTransport class"),
    ("send", "send method"),
    ("receive", "receive method"),
    ("acknowledge", "acknowledge method"),
    ("window", "sliding window"),
    ("retransmit", "retransmission"),
    ("main", "main function"),
    ], "Extremely Difficult 5: Reliable Data Transfer Protocol")


    # ─── Main ──────────────────────────────────────────────────────────────────────

    def main():
    print("=" * 60)
    print("Tektos-Ultima v1 — 5 Extremely Difficult Tests")
    print("=" * 60)
    
    # Check backend
    try:
    resp = requests.get(f"{BACKEND}/health", timeout=5)
    resp.raise_for_status()
    health = resp.json()
    print(f"✅ Backend running: LLM={health['llm_url']}, Model={health['llm_model']}")
    print(f"   Active sessions: {health['active_sessions']}")
    except Exception as e:
    print(f"❌ Backend not running: {e}")
    sys.exit(1)
    
    tests = [
    ("Extremely Difficult 1: Minimal Compiler", test_minimal_compiler),
    ("Extremely Difficult 2: B-Tree Database", test_btree_db),
    ("Extremely Difficult 3: CPU Emulator", test_cpu_emulator),
    ("Extremely Difficult 4: Suffix Tree", test_suffix_tree),
    ("Extremely Difficult 5: Reliable Data Transfer Protocol", test_network_protocol),
    ]
    
    results = []
    for name, test_func in tests:
    try:
    passed = test_func()
    results.append((name, passed))
    except Exception as e:
    print(f"❌ Test '{name}' raised exception: {e}")
    import traceback
    traceback.print_exc()
    results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} — {name}")
    
    print(f"\n{passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
    print("\n🎉 All extremely difficult tests passed!")
    else:
    print(f"\n⚠️  {total_count - passed_count} test(s) failed")
    
    return passed_count == total_count


    success = main()
    sys.exit(0 if success else 1)
