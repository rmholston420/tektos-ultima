"""
Tektos-Ultima v1 — 10 Hard Coding Tests

Genuinely challenging problems testing:
- Complex algorithms (graphs, DP, trees)
- System design patterns (queues, pools, limiters)
- Data structures (tries, bloom filters, skip lists)
- Concurrent programming (producer-consumer, locks)
- Parsing/compilation (tokenizers, ASTs)
- Networking (HTTP/WebSocket servers)
- Database (in-memory with transactions)
- Security (encryption, hashing)
- Performance (O(1) caches, skip lists)
- Complex patterns (interpreters, state machines)
"""

import requests
import json
import os
import time
import sys

BACKEND = "http://localhost:8020"
TEST_DIR = "/home/rmholston/dev/tektos-ultima-v1"
TIMEOUT = 600  # 10 minutes per test
PROGRESS_INTERVAL = 60  # Check every 60 seconds


def create_session():
    """Create a new session and return session_id."""
    resp = requests.post(f"{BACKEND}/api/sessions", json={
        "model": "Qwen_Qwen3.6-35B-A3B-Q5_K_M",
        "cwd": TEST_DIR,
        "provider": "local",
        "permission_mode": "auto"
    })
    resp.raise_for_status()
    data = resp.json()
    return data.get("session_id") or data.get("id")


def send_prompt(session_id, prompt, timeout=600):
    """Send a prompt via SSE and collect all events with progress monitoring."""
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
            
            # Progress monitoring
            now = time.time()
            if now - last_progress >= PROGRESS_INTERVAL:
                print(f"  ... {event_count} events after {int(now - last_progress + PROGRESS_INTERVAL)}s")
                last_progress = now
    
    return events


def check_file_exists(filepath, timeout=600):
    """Wait for a file to be created with progress monitoring."""
    start = time.time()
    last_progress = start
    
    while time.time() - start < timeout:
        if os.path.exists(filepath):
            return True
        
        # Progress monitoring
        now = time.time()
        if now - last_progress >= PROGRESS_INTERVAL:
            elapsed = int(now - start)
            remaining = int(timeout - elapsed)
            print(f"  ⏳ Waiting for file... {elapsed}s elapsed, {remaining}s remaining")
            last_progress = now
        
        time.sleep(5)
    
    return False


def read_file_content(filepath):
    """Read file content."""
    with open(filepath, 'r') as f:
        return f.read()


def verify_file(filepath, checks, test_name):
    """Verify file exists, is valid Python, and contains required components."""
    if not check_file_exists(filepath, timeout=TIMEOUT):
        print(f"❌ {test_name}: File not created within {TIMEOUT}s")
        return False
    
    content = read_file_content(filepath)
    print(f"✅ {test_name}: File created ({len(content)} bytes)")
    
    # Verify valid Python
    try:
        compile(content, filepath, 'exec')
        print(f"  ✅ Valid Python syntax")
    except SyntaxError as e:
        print(f"  ❌ Syntax error: {e}")
        return False
    
    # Check required components
    all_passed = True
    for keyword, name in checks:
        if keyword in content:
            print(f"  ✅ {name} found")
        else:
            print(f"  ❌ {name} NOT found")
            all_passed = False
    
    return all_passed


# ─── 10 Hard Tests ─────────────────────────────────────────────────────────────

def test_dijkstra():
    """Hard 1: Dijkstra's shortest path algorithm."""
    print("\n🔴 Hard 1: Dijkstra's Algorithm")
    session_id = create_session()
    
    prompt = """Write Dijkstra's shortest path algorithm in Python at /tmp/dijkstra.py.

Requirements:
1. Graph class with add_edge, get_neighbors
2. dijkstra(graph, start, end) returns shortest path and distance
3. Use priority queue (heapq)
4. main() tests with a sample graph

Include docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/dijkstra.py", [
        ("Graph", "Graph class"),
        ("dijkstra", "dijkstra function"),
        ("heapq", "priority queue"),
        ("add_edge", "add_edge method"),
        ("get_neighbors", "get_neighbors method"),
        ("main", "main function"),
    ], "Hard 1: Dijkstra's Algorithm")


def test_message_queue():
    """Hard 2: Thread-safe message queue."""
    print("\n🔴 Hard 2: Message Queue")
    session_id = create_session()
    
    prompt = """Write a thread-safe message queue in Python at /tmp/message_queue.py.

Requirements:
1. MessageQueue class with put, get, size, is_empty
2. Thread-safe using threading.Lock and threading.Condition
3. Blocking get() when queue is empty
4. main() demonstrates producer-consumer pattern

Include docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/message_queue.py", [
        ("MessageQueue", "MessageQueue class"),
        ("put", "put method"),
        ("get", "get method"),
        ("Lock", "threading.Lock"),
        ("Condition", "threading.Condition"),
        ("main", "main function"),
    ], "Hard 2: Message Queue")


def test_bloom_filter():
    """Hard 3: Bloom filter for set membership."""
    print("\n🔴 Hard 3: Bloom Filter")
    session_id = create_session()
    
    prompt = """Write a Bloom filter in Python at /tmp/bloom_filter.py.

Requirements:
1. BloomFilter class with add, contains, size
2. Multiple hash functions using different seeds
3. Configurable false positive rate
4. main() demonstrates usage and tests false positives

Include docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/bloom_filter.py", [
        ("BloomFilter", "BloomFilter class"),
        ("add", "add method"),
        ("contains", "contains method"),
        ("hash", "hash function"),
        ("main", "main function"),
    ], "Hard 3: Bloom Filter")


def test_skip_list():
    """Hard 4: Skip list for O(log n) operations."""
    print("\n🔴 Hard 4: Skip List")
    session_id = create_session()
    
    prompt = """Write a skip list in Python at /tmp/skip_list.py.

Requirements:
1. SkipListNode with forward pointers
2. SkipList class with insert, search, delete
3. Randomized level generation
4. O(log n) average case for operations
5. main() tests operations and verifies correctness

Include docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/skip_list.py", [
        ("SkipListNode", "SkipListNode class"),
        ("SkipList", "SkipList class"),
        ("insert", "insert method"),
        ("search", "search method"),
        ("delete", "delete method"),
        ("main", "main function"),
    ], "Hard 4: Skip List")


def test_tokenizer():
    """Hard 5: Programming language tokenizer."""
    print("\n🔴 Hard 5: Tokenizer")
    session_id = create_session()
    
    prompt = """Write a tokenizer in Python at /tmp/tokenizer.py.

Requirements:
1. tokenize(source) returns list of tokens
2. Token types: IDENTIFIER, NUMBER, STRING, OPERATOR, KEYWORD, PUNCTUATION
3. Handles keywords: if, else, for, while, return, def, class
4. main() tokenizes a sample Python-like code snippet

Include docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/tokenizer.py", [
        ("tokenize", "tokenize function"),
        ("Token", "Token class"),
        ("IDENTIFIER", "IDENTIFIER token type"),
        ("NUMBER", "NUMBER token type"),
        ("KEYWORD", "KEYWORD token type"),
        ("main", "main function"),
    ], "Hard 5: Tokenizer")


def test_http_server():
    """Hard 6: Simple HTTP server."""
    print("\n🔴 Hard 6: HTTP Server")
    session_id = create_session()
    
    prompt = """Write a simple HTTP server in Python at /tmp/http_server.py.

Requirements:
1. HTTPServer class using http.server
2. Handle GET and POST requests
3. Route handling with path matching
4. main() starts server on port 8080

Include docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/http_server.py", [
        ("HTTPServer", "HTTPServer class"),
        ("GET", "GET handler"),
        ("POST", "POST handler"),
        ("route", "route handling"),
        ("main", "main function"),
    ], "Hard 6: HTTP Server")


def test_in_memory_db():
    """Hard 7: In-memory database with transactions."""
    print("\n🔴 Hard 7: In-Memory Database")
    session_id = create_session()
    
    prompt = """Write an in-memory database in Python at /tmp/in_memory_db.py.

Requirements:
1. Database class with insert, select, update, delete
2. Transaction support with commit and rollback
3. Query parsing for WHERE clauses
4. main() demonstrates CRUD operations and transactions

Include docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/in_memory_db.py", [
        ("Database", "Database class"),
        ("insert", "insert method"),
        ("select", "select method"),
        ("commit", "commit method"),
        ("rollback", "rollback method"),
        ("main", "main function"),
    ], "Hard 7: In-Memory Database")


def test_aes_encryptor():
    """Hard 8: AES encryption utility."""
    print("\n🔴 Hard 8: AES Encryptor")
    session_id = create_session()
    
    prompt = """Write an AES encryptor in Python at /tmp/aes_encryptor.py.

Requirements:
1. AESCipher class with encrypt and decrypt methods
2. Uses cryptography library or implements basic AES
3. Handles padding (PKCS7)
4. main() demonstrates encryption/decryption roundtrip

Include docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/aes_encryptor.py", [
        ("AESCipher", "AESCipher class"),
        ("encrypt", "encrypt method"),
        ("decrypt", "decrypt method"),
        ("padding", "padding handling"),
        ("main", "main function"),
    ], "Hard 8: AES Encryptor")


def test_interpreter():
    """Hard 9: Simple arithmetic expression interpreter."""
    print("\n🔴 Hard 9: Expression Interpreter")
    session_id = create_session()
    
    prompt = """Write an arithmetic expression interpreter in Python at /tmp/interpreter.py.

Requirements:
1. parse(expression) evaluates arithmetic expressions
2. Supports: +, -, *, /, parentheses, variables
3. Handles operator precedence
4. main() tests various expressions

Include docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/interpreter.py", [
        ("parse", "parse function"),
        ("evaluate", "evaluate function"),
        ("parentheses", "parentheses handling"),
        ("variables", "variable support"),
        ("main", "main function"),
    ], "Hard 9: Expression Interpreter")


def test_rate_limiter():
    """Hard 10: Token bucket rate limiter."""
    print("\n🔴 Hard 10: Rate Limiter")
    session_id = create_session()
    
    prompt = """Write a token bucket rate limiter in Python at /tmp/rate_limiter.py.

Requirements:
1. RateLimiter class with allow_request method
2. Token bucket algorithm with configurable rate and capacity
3. Thread-safe using threading.Lock
4. main() demonstrates rate limiting behavior

Include docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/rate_limiter.py", [
        ("RateLimiter", "RateLimiter class"),
        ("allow_request", "allow_request method"),
        ("token", "token bucket"),
        ("Lock", "threading.Lock"),
        ("main", "main function"),
    ], "Hard 10: Rate Limiter")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Tektos-Ultima v1 — 10 Hard Coding Tests")
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
        ("Hard 1: Dijkstra's Algorithm", test_dijkstra),
        ("Hard 2: Message Queue", test_message_queue),
        ("Hard 3: Bloom Filter", test_bloom_filter),
        ("Hard 4: Skip List", test_skip_list),
        ("Hard 5: Tokenizer", test_tokenizer),
        ("Hard 6: HTTP Server", test_http_server),
        ("Hard 7: In-Memory Database", test_in_memory_db),
        ("Hard 8: AES Encryptor", test_aes_encryptor),
        ("Hard 9: Expression Interpreter", test_interpreter),
        ("Hard 10: Rate Limiter", test_rate_limiter),
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
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")
    
    return passed_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
