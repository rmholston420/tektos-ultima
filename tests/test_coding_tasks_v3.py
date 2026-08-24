"""
Tektos-Ultima v1 — Coding Tests (4 Easy, 3 Medium, 3 Hard)

Difficulty levels:
- Easy: Simple functions, clear requirements, fast execution
- Medium: Classes with multiple methods, some complexity
- Hard: Complex algorithms, multiple components, longer generation
"""

import requests
import json
import os
import time
import sys

BACKEND = "http://localhost:8020"
TEST_DIR = "/home/rmholston/dev/tektos-ultima-v1"

# Timeouts by difficulty
TIMEOUTS = {
    "easy": 120,
    "medium": 180,
    "hard": 300,
}


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


def send_prompt(session_id, prompt, timeout=180):
    """Send a prompt via SSE and collect all events."""
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
            if event_count % 30 == 0:
                print(f"  ... {event_count} events so far")
    
    return events


def check_file_exists(filepath, timeout=180):
    """Wait for a file to be created."""
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(filepath):
            return True
        time.sleep(3)
    return False


def read_file_content(filepath):
    """Read file content."""
    with open(filepath, 'r') as f:
        return f.read()


def verify_file(filepath, checks, test_name, difficulty):
    """Verify file exists, is valid Python, and contains required components."""
    timeout = TIMEOUTS.get(difficulty, 180)
    
    if not check_file_exists(filepath, timeout=timeout):
        print(f"❌ {test_name} ({difficulty}): File not created within {timeout}s")
        return False
    
    content = read_file_content(filepath)
    print(f"✅ {test_name} ({difficulty}): File created ({len(content)} bytes)")
    
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


# ─── Easy Tests (4) ────────────────────────────────────────────────────────────

def test_fibonacci():
    """Easy: Simple recursive function with memoization."""
    print("\n🌟 Easy 1: Fibonacci with Memoization")
    session_id = create_session()
    
    prompt = """Write a fibonacci function in Python at /tmp/fibonacci.py.

Requirements:
1. fibonacci(n) returns nth fibonacci number
2. Use memoization (cache) for efficiency
3. main() prints first 10 fibonacci numbers

Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUTS["easy"])
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/fibonacci.py", [
        ("fibonacci", "fibonacci function"),
        ("cache", "memoization cache"),
        ("def ", "function definition"),
        ("main", "main function"),
    ], "Easy 1: Fibonacci", "easy")


def test_reverse_string():
    """Easy: String manipulation."""
    print("\n🌟 Easy 2: String Reversal")
    session_id = create_session()
    
    prompt = """Write a string reversal function in Python at /tmp/reverse_string.py.

Requirements:
1. reverse_string(s) reverses a string
2. is_palindrome(s) checks if string is palindrome
3. main() tests both functions

Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUTS["easy"])
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/reverse_string.py", [
        ("reverse_string", "reverse_string function"),
        ("is_palindrome", "is_palindrome function"),
        ("def ", "function definition"),
        ("main", "main function"),
    ], "Easy 2: String Reversal", "easy")


def test_bubble_sort():
    """Easy: Simple sorting algorithm."""
    print("\n🌟 Easy 3: Bubble Sort")
    session_id = create_session()
    
    prompt = """Write a bubble sort in Python at /tmp/bubble_sort.py.

Requirements:
1. bubble_sort(arr) sorts array in place
2. is_sorted(arr) checks if array is sorted
3. main() tests sorting and verification

Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUTS["easy"])
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/bubble_sort.py", [
        ("bubble_sort", "bubble_sort function"),
        ("is_sorted", "is_sorted function"),
        ("def ", "function definition"),
        ("main", "main function"),
    ], "Easy 3: Bubble Sort", "easy")


def test_count_vowels():
    """Easy: String counting."""
    print("\n🌟 Easy 4: Vowel Counter")
    session_id = create_session()
    
    prompt = """Write a vowel counter in Python at /tmp/vowel_counter.py.

Requirements:
1. count_vowels(s) returns count of vowels
2. get_vowel_indices(s) returns list of vowel positions
3. main() tests both functions

Keep it simple and concise."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUTS["easy"])
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/vowel_counter.py", [
        ("count_vowels", "count_vowels function"),
        ("get_vowel_indices", "get_vowel_indices function"),
        ("def ", "function definition"),
        ("main", "main function"),
    ], "Easy 4: Vowel Counter", "easy")


# ─── Medium Tests (3) ──────────────────────────────────────────────────────────

def test_lru_cache():
    """Medium: LRU Cache with O(1) operations."""
    print("\n🔷 Medium 1: LRU Cache")
    session_id = create_session()
    
    prompt = """Write an LRU Cache in Python at /tmp/lru_cache.py.

Requirements:
1. LRUCache class with capacity
2. get(key) returns value or -1 (O(1))
3. put(key, value) adds/updates (O(1))
4. Use OrderedDict
5. main() tests capacity 3 with operations

Keep it concise with docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUTS["medium"])
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/lru_cache.py", [
        ("LRUCache", "LRUCache class"),
        ("get", "get method"),
        ("put", "put method"),
        ("OrderedDict", "OrderedDict usage"),
        ("capacity", "capacity parameter"),
    ], "Medium 1: LRU Cache", "medium")


def test_observer_pattern():
    """Medium: Observer design pattern."""
    print("\n🔷 Medium 2: Observer Pattern")
    session_id = create_session()
    
    prompt = """Write an Observer pattern in Python at /tmp/observer.py.

Requirements:
1. Subject class with attach, detach, notify
2. Observer class with update method
3. ConcreteSubject and ConcreteObserver
4. main() demonstrates subscription and notification

Keep it concise with docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUTS["medium"])
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/observer.py", [
        ("Subject", "Subject class"),
        ("Observer", "Observer class"),
        ("attach", "attach method"),
        ("notify", "notify method"),
        ("update", "update method"),
    ], "Medium 2: Observer Pattern", "medium")


def test_memoization():
    """Medium: Memoization decorator."""
    print("\n🔷 Medium 3: Memoization Decorator")
    session_id = create_session()
    
    prompt = """Write a memoization decorator in Python at /tmp/memoize.py.

Requirements:
1. memoize decorator that caches function results
2. Works with any function signature
3. clear_cache() method to reset cache
4. main() demonstrates with fibonacci calculation

Keep it concise with docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUTS["medium"])
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/memoize.py", [
        ("memoize", "memoize decorator"),
        ("cache", "cache implementation"),
        ("clear_cache", "clear_cache method"),
        ("@memoize", "decorator usage"),
    ], "Medium 3: Memoization", "medium")


# ─── Hard Tests (3) ────────────────────────────────────────────────────────────

def test_avl_tree():
    """Hard: AVL tree with rotations."""
    print("\n🔴 Hard 1: AVL Tree with Rotations")
    session_id = create_session()
    
    prompt = """Write an AVL tree implementation in Python at /tmp/avl_tree.py.

Requirements:
1. AVLNode class with left, right, height, key, value
2. AVLTree class with insert, delete, search, inorder_traversal
3. left_rotate, right_rotate methods
4. balance_factor() method
5. main() inserts 10,20,30,40,50,25 and prints traversal

Include docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUTS["hard"])
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
    ], "Hard 1: AVL Tree", "hard")


def test_json_parser():
    """Hard: Recursive descent JSON parser."""
    print("\n🔴 Hard 2: JSON Parser")
    session_id = create_session()
    
    prompt = """Write a JSON parser in Python at /tmp/json_parser.py.

Requirements:
1. parse(json_string) returns Python object
2. Handles: strings, numbers, booleans, null, arrays, objects
3. validate(json_string) returns True/False
4. main() tests parsing and validation

Include docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUTS["hard"])
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/json_parser.py", [
        ("parse", "parse function"),
        ("validate", "validate function"),
        ("def ", "function definitions"),
        ("string", "string handling"),
        ("number", "number handling"),
    ], "Hard 2: JSON Parser", "hard")


def test_task_pipeline():
    """Hard: Task pipeline with parallel execution."""
    print("\n🔴 Hard 3: Task Pipeline")
    session_id = create_session()
    
    prompt = """Write a Task Pipeline in Python at /tmp/task_pipeline.py.

Requirements:
1. TaskPipeline class
2. add_stage(name, func) - add stage
3. set_parallel(stages) - mark stages for parallel execution
4. run(data) - execute pipeline
5. main() with 5 stages (some parallel)

Include docstrings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUTS["hard"])
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/task_pipeline.py", [
        ("TaskPipeline", "TaskPipeline class"),
        ("add_stage", "add_stage method"),
        ("set_parallel", "set_parallel method"),
        ("run", "run method"),
        ("stage", "stage handling"),
    ], "Hard 3: Task Pipeline", "hard")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Tektos-Ultima v1 — Coding Tests (4 Easy, 3 Medium, 3 Hard)")
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
        # Easy (4)
        ("Easy 1: Fibonacci", test_fibonacci),
        ("Easy 2: String Reversal", test_reverse_string),
        ("Easy 3: Bubble Sort", test_bubble_sort),
        ("Easy 4: Vowel Counter", test_count_vowels),
        # Medium (3)
        ("Medium 1: LRU Cache", test_lru_cache),
        ("Medium 2: Observer Pattern", test_observer_pattern),
        ("Medium 3: Memoization", test_memoization),
        # Hard (3)
        ("Hard 1: AVL Tree", test_avl_tree),
        ("Hard 2: JSON Parser", test_json_parser),
        ("Hard 3: Task Pipeline", test_task_pipeline),
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
    
    # Summary by difficulty
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    easy_results = [r for r in results if r[0].startswith("Easy")]
    medium_results = [r for r in results if r[0].startswith("Medium")]
    hard_results = [r for r in results if r[0].startswith("Hard")]
    
    easy_passed = sum(1 for _, p in easy_results if p)
    medium_passed = sum(1 for _, p in medium_results if p)
    hard_passed = sum(1 for _, p in hard_results if p)
    
    print(f"\nEasy:   {easy_passed}/{len(easy_results)} passed")
    print(f"Medium: {medium_passed}/{len(medium_results)} passed")
    print(f"Hard:   {hard_passed}/{len(hard_results)} passed")
    
    total_passed = sum(1 for _, p in results if p)
    total_count = len(results)
    
    print(f"\nTotal: {total_passed}/{total_count} tests passed")
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} — {name}")
    
    if total_passed == total_count:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total_count - total_passed} test(s) failed")
    
    return total_passed == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
