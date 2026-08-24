"""
Tektos-Ultima v1 — Moderately Difficult Coding Tests (v2)

Improved test suite with:
1. Longer timeouts (300s)
2. Simplified prompts for complex tasks
3. Progress monitoring via event tracking
4. Broken-down complex tasks into smaller steps
"""

import requests
import json
import os
import time
import sys

BACKEND = "http://localhost:8020"
TEST_DIR = "/home/rmholston/dev/tektos-ultima-v1"
TIMEOUT = 300  # Increased timeout


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


def send_prompt(session_id, prompt, timeout=TIMEOUT):
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
            if event_count % 50 == 0:
                print(f"  ... received {event_count} events so far")
    
    return events


def check_file_exists(filepath, timeout=TIMEOUT):
    """Wait for a file to be created."""
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(filepath):
            return True
        time.sleep(3)  # Less frequent polling
    return False


def read_file_content(filepath):
    """Read file content."""
    with open(filepath, 'r') as f:
        return f.read()


def verify_file(filepath, checks, test_name):
    """Verify file exists, is valid Python, and contains required components."""
    if not check_file_exists(filepath, timeout=TIMEOUT):
        print(f"❌ {test_name}: File not created within timeout")
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


# ─── Test Cases ────────────────────────────────────────────────────────────────

def test_bst_with_rotations():
    """Tektos implements an AVL tree with insert and rotations."""
    print("\n🌳 Test 1: BST with Rotations (AVL Tree)")
    session_id = create_session()
    
    prompt = """Write an AVL tree implementation in Python at /tmp/avl_tree.py.

Requirements:
1. AVLNode class with left, right, height, key, value
2. AVLTree class with insert, delete, search, inorder_traversal
3. left_rotate, right_rotate methods
4. balance_factor() method
5. main() that inserts 10,20,30,40,50,25 and prints traversal

Keep it concise with docstrings."""

    events = send_prompt(session_id, prompt)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/avl_tree.py", [
        ("AVLNode", "AVLNode class"),
        ("AVLTree", "AVLTree class"),
        ("left_rotate", "left_rotate method"),
        ("right_rotate", "right_rotate method"),
        ("balance_factor", "balance_factor method"),
        ("insert", "insert method"),
        ("delete", "delete method"),
        ("search", "search method"),
        ("inorder_traversal", "inorder_traversal method"),
    ], "Test 1")


def test_lru_cache():
    """Tektos implements LRU Cache with O(1) get and put."""
    print("\n📦 Test 2: LRU Cache (O(1) operations)")
    session_id = create_session()
    
    prompt = """Write an LRU Cache in Python at /tmp/lru_cache.py.

Requirements:
1. LRUCache class with capacity
2. get(key) returns value or -1 (O(1))
3. put(key, value) adds/updates (O(1))
4. Use OrderedDict
5. main() tests capacity 3 with put/get/eviction

Keep it concise with docstrings."""

    events = send_prompt(session_id, prompt)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/lru_cache.py", [
        ("LRUCache", "LRUCache class"),
        ("get", "get method"),
        ("put", "put method"),
        ("OrderedDict", "OrderedDict usage"),
        ("capacity", "capacity parameter"),
    ], "Test 2")


def test_json_parser():
    """Tektos implements a recursive descent JSON parser."""
    print("\n📋 Test 3: JSON Parser (Simplified)")
    session_id = create_session()
    
    prompt = """Write a JSON parser in Python at /tmp/json_parser.py.

Requirements:
1. parse(json_string) returns Python object
2. Handles: strings, numbers, booleans, null, arrays, objects
3. validate(json_string) returns True/False
4. main() tests parsing and validation

Keep it simple and concise."""

    events = send_prompt(session_id, prompt)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/json_parser.py", [
        ("parse", "parse function"),
        ("validate", "validate function"),
        ("def ", "function definitions"),
        ("string", "string handling"),
        ("number", "number handling"),
    ], "Test 3")


def test_event_emitter():
    """Tektos implements an event emitter with method chaining."""
    print("\n📡 Test 4: Event Emitter (Simplified)")
    session_id = create_session()
    
    prompt = """Write an EventEmitter in Python at /tmp/event_emitter.py.

Requirements:
1. EventEmitter class
2. on(event, callback) - register listener
3. off(event, callback) - remove listener
4. emit(event, *args) - trigger event
5. main() demonstrates usage

Keep it simple and concise."""

    events = send_prompt(session_id, prompt)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/event_emitter.py", [
        ("EventEmitter", "EventEmitter class"),
        ("on", "on method"),
        ("off", "off method"),
        ("emit", "emit method"),
        ("callback", "callback handling"),
    ], "Test 4")


def test_http_simulator():
    """Tektos implements HTTP request simulator with retry logic."""
    print("\n🌐 Test 5: HTTP Request Simulator (Simplified)")
    session_id = create_session()
    
    prompt = """Write an HTTP Request Simulator in Python at /tmp/http_simulator.py.

Requirements:
1. HttpRequestSimulator class
2. get(url), post(url), put(url), delete(url) methods
3. retry with max_retries and backoff
4. main() tests GET and POST

Keep it simple and concise."""

    events = send_prompt(session_id, prompt)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/http_simulator.py", [
        ("HttpRequestSimulator", "HttpRequestSimulator class"),
        ("get", "get method"),
        ("post", "post method"),
        ("retry", "retry logic"),
        ("backoff", "backoff logic"),
    ], "Test 5")


def test_task_pipeline():
    """Tektos implements a task pipeline with multiple stages."""
    print("\n🔄 Test 6: Task Pipeline (Simplified)")
    session_id = create_session()
    
    prompt = """Write a Task Pipeline in Python at /tmp/task_pipeline.py.

Requirements:
1. TaskPipeline class
2. add_stage(name, func) - add stage
3. run(data) - execute pipeline
4. main() with 3 sequential stages

Keep it simple and concise."""

    events = send_prompt(session_id, prompt)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/task_pipeline.py", [
        ("TaskPipeline", "TaskPipeline class"),
        ("add_stage", "add_stage method"),
        ("run", "run method"),
        ("stage", "stage handling"),
    ], "Test 6")


def test_memoization():
    """Tektos implements a memoization decorator."""
    print("\n🧠 Test 7: Memoization Decorator")
    session_id = create_session()
    
    prompt = """Write a memoization decorator in Python at /tmp/memoize.py.

Requirements:
1. memoize decorator that caches function results
2. Works with any function signature
3. clear_cache() method to reset cache
4. main() demonstrates with fibonacci calculation

Keep it simple and concise."""

    events = send_prompt(session_id, prompt)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/memoize.py", [
        ("memoize", "memoize decorator"),
        ("cache", "cache implementation"),
        ("clear_cache", "clear_cache method"),
        ("@memoize", "decorator usage"),
    ], "Test 7")


def test_singleton():
    """Tektos implements a Singleton pattern."""
    print("\n🔒 Test 8: Singleton Pattern")
    session_id = create_session()
    
    prompt = """Write a Singleton class in Python at /tmp/singleton.py.

Requirements:
1. Singleton base class
2. __new__ method ensures single instance
3. get_instance() class method
4. main() demonstrates singleton behavior

Keep it simple and concise."""

    events = send_prompt(session_id, prompt)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/singleton.py", [
        ("Singleton", "Singleton class"),
        ("__new__", "__new__ method"),
        ("get_instance", "get_instance method"),
        ("instance", "instance handling"),
    ], "Test 8")


def test_observer():
    """Tektos implements an Observer pattern."""
    print("\n👁️  Test 9: Observer Pattern")
    session_id = create_session()
    
    prompt = """Write an Observer pattern in Python at /tmp/observer.py.

Requirements:
1. Subject class with attach, detach, notify
2. Observer class with update method
3. ConcreteSubject and ConcreteObserver
4. main() demonstrates subscription and notification

Keep it simple and concise."""

    events = send_prompt(session_id, prompt)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/observer.py", [
        ("Subject", "Subject class"),
        ("Observer", "Observer class"),
        ("attach", "attach method"),
        ("notify", "notify method"),
        ("update", "update method"),
    ], "Test 9")


def test_strategy():
    """Tektos implements a Strategy pattern."""
    print("\n🎯 Test 10: Strategy Pattern")
    session_id = create_session()
    
    prompt = """Write a Strategy pattern in Python at /tmp/strategy.py.

Requirements:
1. Strategy interface (abstract base class)
2. ConcreteStrategyA and ConcreteStrategyB
3. Context class that uses a strategy
4. main() demonstrates switching strategies

Keep it simple and concise."""

    events = send_prompt(session_id, prompt)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/strategy.py", [
        ("Strategy", "Strategy interface"),
        ("Context", "Context class"),
        ("execute", "execute method"),
        ("set_strategy", "set_strategy method"),
        ("ConcreteStrategy", "ConcreteStrategy class"),
    ], "Test 10")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Tektos-Ultima v1 — Moderately Difficult Coding Tests (v2)")
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
        ("BST with Rotations", test_bst_with_rotations),
        ("LRU Cache", test_lru_cache),
        ("JSON Parser", test_json_parser),
        ("Event Emitter", test_event_emitter),
        ("HTTP Simulator", test_http_simulator),
        ("Task Pipeline", test_task_pipeline),
        ("Memoization", test_memoization),
        ("Singleton", test_singleton),
        ("Observer Pattern", test_observer),
        ("Strategy Pattern", test_strategy),
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
