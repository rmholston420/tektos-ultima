"""
if __name__ == "__main__":
    Tektos-Ultima v1 — 5 Very Difficult Coding Tests

    Very difficult = complex algorithms, multi-component systems, or deep data structures.
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


    # ─── 5 Very Difficult Tests ────────────────────────────────────────────────────






    def test_a_star():
    """Very Difficult 1: A* pathfinding with heuristic."""
    print("\n🔴 Very Difficult 1: A* Pathfinding")
    session_id = create_session()
    
    prompt = """Write an A* pathfinding algorithm in Python at /tmp/a_star.py.

    Requirements:
    1. AStar class with find_path(start, goal, grid) where grid is 2D list (0=walkable, 1=wall)
    2. Uses Manhattan distance heuristic
    3. Returns list of (row, col) tuples for the path
    4. main() tests on a sample grid

    Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/a_star.py", [
    ("AStar", "AStar class"),
    ("find_path", "find_path method"),
    ("heapq", "priority queue"),
    ("main", "main function"),
    ], "Very Difficult 1: A* Pathfinding")









    def test_kv_store():
    """Very Difficult 2: Key-value store with TTL and persistence."""
    print("\n🔴 Very Difficult 2: KV Store with TTL")
    session_id = create_session()
    
    prompt = """Write a key-value store with TTL in Python at /tmp/kv_store.py.

    Requirements:
    1. KVStore class with set(key, value, ttl_seconds), get(key), delete(key)
    2. Expired entries are automatically cleaned on get
    3. Supports optional persistence to a JSON file
    4. main() demonstrates usage

    Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/kv_store.py", [
    ("KVStore", "KVStore class"),
    ("set", "set method"),
    ("get", "get method"),
    ("delete", "delete method"),
    ("ttl", "TTL support"),
    ("main", "main function"),
    ], "Very Difficult 2: KV Store with TTL")









    def test_dfs_bfs():
    """Very Difficult 3: Graph traversal with cycle detection."""
    print("\n🔴 Very Difficult 3: Graph Traversal + Cycle Detection")
    session_id = create_session()
    
    prompt = """Write graph algorithms in Python at /tmp/graph_algo.py.

    Requirements:
    1. Graph class with add_edge, dfs(start), bfs(start)
    2. detect_cycle() method that returns True/False
    3. topological_sort() method for DAGs
    4. main() tests all methods

    Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/graph_algo.py", [
    ("Graph", "Graph class"),
    ("add_edge", "add_edge method"),
    ("dfs", "dfs method"),
    ("bfs", "bfs method"),
    ("detect_cycle", "detect_cycle method"),
    ("topological_sort", "topological_sort method"),
    ("main", "main function"),
    ], "Very Difficult 3: Graph Traversal + Cycle Detection")









    def test_memoized_dp():
    """Very Difficult 4: Dynamic programming with memoization."""
    print("\n🔴 Very Difficult 4: Dynamic Programming")
    session_id = create_session()
    
    prompt = """Write dynamic programming solutions in Python at /tmp/dp_solutions.py.

    Requirements:
    1. CoinChange class with min_coins(coins, amount) using bottom-up DP
    2. LongestCommonSubsequence class with lcs(s1, s2)
    3. Knapsack class with max_value(weights, values, capacity)
    4. main() tests all three

    Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/dp_solutions.py", [
    ("CoinChange", "CoinChange class"),
    ("min_coins", "min_coins method"),
    ("LongestCommonSubsequence", "LCS class"),
    ("lcs", "lcs method"),
    ("Knapsack", "Knapsack class"),
    ("max_value", "max_value method"),
    ("main", "main function"),
    ], "Very Difficult 4: Dynamic Programming")









    def test_event_system():
    """Very Difficult 5: Event-driven architecture with middleware."""
    print("\n🔴 Very Difficult 5: Event System with Middleware")
    session_id = create_session()
    
    prompt = """Write an event-driven system in Python at /tmp/event_system.py.

    Requirements:
    1. EventBus class with subscribe(event_type, handler), publish(event_type, data)
    2. Middleware support: add_middleware(middleware_func) that wraps handlers
    3. Priority-based subscription ordering
    4. main() demonstrates events, middleware, and priorities

    Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/event_system.py", [
    ("EventBus", "EventBus class"),
    ("subscribe", "subscribe method"),
    ("publish", "publish method"),
    ("add_middleware", "add_middleware method"),
    ("priority", "priority support"),
    ("main", "main function"),
    ], "Very Difficult 5: Event System with Middleware")


    # ─── Main ──────────────────────────────────────────────────────────────────────

    def main():
    print("=" * 60)
    print("Tektos-Ultima v1 — 5 Very Difficult Tests")
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
    ("Very Difficult 1: A* Pathfinding", test_a_star),
    ("Very Difficult 2: KV Store with TTL", test_kv_store),
    ("Very Difficult 3: Graph Traversal + Cycle Detection", test_dfs_bfs),
    ("Very Difficult 4: Dynamic Programming", test_memoized_dp),
    ("Very Difficult 5: Event System with Middleware", test_event_system),
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
    print("\n🎉 All very difficult tests passed!")
    else:
    print(f"\n⚠️  {total_count - passed_count} test(s) failed")
    
    return passed_count == total_count


    success = main()
    sys.exit(0 if success else 1)
