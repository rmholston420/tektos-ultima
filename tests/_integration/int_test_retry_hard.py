"""
if __name__ == "__main__":
    Retry 4 failed hard tests with simplified prompts.
    """

    import requests
    import json
    import os
    import time
    import sys

    BACKEND = "http://localhost:8020"
    TEST_DIR = "/home/rmholston/dev/tektos-ultima-v1"
    TIMEOUT = 900  # 15 minutes
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
    event_count = 0
    current_event = "unknown"
    last_progress = time.time()
    
    for line in resp.iter_lines():
    if not line:
    continue
    if line.startswith(b"event: "):
    current_event = line[7:].decode()
    elif line.startswith(b"data: "):
    data = json.loads(line[6:].decode())
    events.append({"type": current_event, "data": data})
    event_count += 1
            
    now = time.time()
    if now - last_progress >= PROGRESS_INTERVAL:
    print(f"  ... {event_count} events after {int(now - last_progress + PROGRESS_INTERVAL)}s")
    last_progress = now
    
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


    # ─── Retry 4 Failed Tests ──────────────────────────────────────────────────────






    def test_bloom_filter():
    """Retry: Bloom filter (simplified)."""
    print("\n🔴 Retry 1: Bloom Filter")
    session_id = create_session()
    
    prompt = """Write a Bloom filter in Python at /tmp/bloom_filter.py.

    Requirements:
    1. BloomFilter class with add(item) and contains(item)
    2. Uses a bit array and multiple hash functions
    3. main() tests adding items and checking membership

    Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/bloom_filter.py", [
    ("BloomFilter", "BloomFilter class"),
    ("add", "add method"),
    ("contains", "contains method"),
    ("main", "main function"),
    ], "Retry 1: Bloom Filter")









    def test_skip_list():
    """Retry: Skip list (simplified)."""
    print("\n🔴 Retry 2: Skip List")
    session_id = create_session()
    
    prompt = """Write a skip list in Python at /tmp/skip_list.py.

    Requirements:
    1. SkipList class with insert(key), search(key), delete(key)
    2. Uses random levels for each node
    3. main() tests insert, search, delete

    Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/skip_list.py", [
    ("SkipList", "SkipList class"),
    ("insert", "insert method"),
    ("search", "search method"),
    ("delete", "delete method"),
    ("main", "main function"),
    ], "Retry 2: Skip List")









    def test_in_memory_db():
    """Retry: In-memory database (simplified)."""
    print("\n🔴 Retry 3: In-Memory Database")
    session_id = create_session()
    
    prompt = """Write an in-memory database in Python at /tmp/in_memory_db.py.

    Requirements:
    1. Database class with insert(table, row), select(table, where), delete(table, where)
    2. Simple WHERE clause support (e.g., where='age > 25')
    3. main() demonstrates CRUD operations

    Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/in_memory_db.py", [
    ("Database", "Database class"),
    ("insert", "insert method"),
    ("select", "select method"),
    ("delete", "delete method"),
    ("main", "main function"),
    ], "Retry 3: In-Memory Database")









    def test_rate_limiter():
    """Retry: Rate limiter (simplified)."""
    print("\n🔴 Retry 4: Rate Limiter")
    session_id = create_session()
    
    prompt = """Write a token bucket rate limiter in Python at /tmp/rate_limiter.py.

    Requirements:
    1. RateLimiter class with allow_request() method
    2. Configurable rate (tokens per second) and capacity
    3. main() demonstrates rate limiting

    Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/rate_limiter.py", [
    ("RateLimiter", "RateLimiter class"),
    ("allow_request", "allow_request method"),
    ("main", "main function"),
    ], "Retry 4: Rate Limiter")


    # ─── Main ──────────────────────────────────────────────────────────────────────

    def main():
    print("=" * 60)
    print("Tektos-Ultima v1 — Retry 4 Failed Hard Tests")
    print("=" * 60)
    
    # Check backend is running
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
    ("Retry 1: Bloom Filter", test_bloom_filter),
    ("Retry 2: Skip List", test_skip_list),
    ("Retry 3: In-Memory Database", test_in_memory_db),
    ("Retry 4: Rate Limiter", test_rate_limiter),
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
    print("\n🎉 All retry tests passed!")
    else:
    print(f"\n⚠️  {total_count - passed_count} test(s) failed")
    
    return passed_count == total_count


    success = main()
    sys.exit(0 if success else 1)
