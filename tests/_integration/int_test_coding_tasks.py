"""
if __name__ == "__main__":
    Tektos-Ultima v1 — Moderately Difficult Coding Tests via REST API

    Tests Tektos's ability to solve real programming tasks:
    1. Binary Search Tree with rotations (AVL tree)
    2. LRU Cache with O(1) operations
    3. JSON parser (recursive descent)
    4. Event emitter with method chaining
    5. HTTP request simulator with retry logic
    6. Task pipeline with multiple stages
    """

    import requests
    import json
    import os
    import time
    import sys

    BACKEND = "http://localhost:8020"
    TEST_DIR = "/home/rmholston/dev/tektos-ultima-v1"

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
    for line in resp.iter_lines():
    if not line:
    continue
    if line.startswith(b"event: "):
    event_type = line[7:].decode()
    elif line.startswith(b"data: "):
    data = json.loads(line[6:].decode())
    events.append({"type": event_type, "data": data})
    
    return events

    def check_file_exists(filepath, timeout=180):
    """Wait for a file to be created."""
    start = time.time()
    while time.time() - start < timeout:
    if os.path.exists(filepath):
    return True
    time.sleep(2)
    return False

    def read_file_content(filepath):
    """Read file content."""
    with open(filepath, 'r') as f:
    return f.read()

    # ─── Test Cases ────────────────────────────────────────────────────────────────






    def test_bst_with_rotations():
    """Tektos implements an AVL tree with insert and rotations."""
    print("\n🌳 Test 1: BST with Rotations (AVL Tree)")
    session_id = create_session()
    
    prompt = """Write a complete AVL tree implementation in Python at /tmp/avl_tree.py.

    Requirements:
    1. Implement AVLNode class with left, right, parent, height, key, value
    2. Implement AVLTree class with: insert(key, value), delete(key), search(key), inorder_traversal()
    3. Implement all 4 rotations: left_rotate, right_rotate, left_right_rotate, right_left_rotate
    4. Implement balance_factor() method
    5. Implement is_balanced() method
    6. Include a main() function that:
    - Creates a tree and inserts keys: 10, 20, 30, 40, 50, 25
    - Prints inorder traversal before and after each insertion
    - Verifies the tree is balanced after all insertions
    - Tests deletion of node 20 and verifies balance
    - Tests search for existing and non-existing keys

    The code must be complete, runnable, and include docstrings."""

    events = send_prompt(session_id, prompt)
    
    # Wait for file to be created
    filepath = "/tmp/avl_tree.py"
    if check_file_exists(filepath, timeout=180):
    content = read_file_content(filepath)
    print(f"✅ File created: {filepath} ({len(content)} bytes)")
        
    # Verify the file is valid Python
    try:
    compile(content, filepath, 'exec')
    print("✅ Valid Python syntax")
    except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    return False
        
    # Check for required components
    checks = [
    ("AVLNode", "AVLNode class"),
    ("AVLTree", "AVLTree class"),
    ("left_rotate", "left_rotate method"),
    ("right_rotate", "right_rotate method"),
    ("balance_factor", "balance_factor method"),
    ("insert", "insert method"),
    ("delete", "delete method"),
    ("search", "search method"),
    ("inorder_traversal", "inorder_traversal method"),
    ]
        
    all_passed = True
    for keyword, name in checks:
    if keyword in content:
    print(f"  ✅ {name} found")
    else:
    print(f"  ❌ {name} NOT found")
    all_passed = False
        
    return all_passed
    else:
    print("❌ File not created within timeout")
    return False






    def test_lru_cache():
    """Tektos implements LRU Cache with O(1) get and put."""
    print("\n📦 Test 2: LRU Cache (O(1) operations)")
    session_id = create_session()
    
    prompt = """Write a complete LRU Cache implementation in Python at /tmp/lru_cache.py.

    Requirements:
    1. Implement LRUCache class with capacity parameter
    2. Implement get(key) method that returns value or -1 if not found (O(1))
    3. Implement put(key, value) method that adds/updates entry (O(1))
    4. Use OrderedDict or a custom doubly-linked list + hash map for O(1) operations
    5. Include a main() function that:
    - Creates a cache with capacity 3
    - Performs a series of put/get operations
    - Verifies correct behavior for eviction
    - Tests edge cases (capacity 1, duplicate keys, negative values)
    - Prints the cache state after each operation

    The code must be complete, runnable, and include docstrings."""

    events = send_prompt(session_id, prompt)
    
    filepath = "/tmp/lru_cache.py"
    if check_file_exists(filepath, timeout=180):
    content = read_file_content(filepath)
    print(f"✅ File created: {filepath} ({len(content)} bytes)")
        
    try:
    compile(content, filepath, 'exec')
    print("✅ Valid Python syntax")
    except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    return False
        
    checks = [
    ("LRUCache", "LRUCache class"),
    ("get", "get method"),
    ("put", "put method"),
    ("OrderedDict", "OrderedDict usage"),
    ("capacity", "capacity parameter"),
    ]
        
    all_passed = True
    for keyword, name in checks:
    if keyword in content:
    print(f"  ✅ {name} found")
    else:
    print(f"  ❌ {name} NOT found")
    all_passed = False
        
    return all_passed
    else:
    print("❌ File not created within timeout")
    return False






    def test_json_parser():
    """Tektos implements a recursive descent JSON parser."""
    print("\n📋 Test 3: JSON Parser (Recursive Descent)")
    session_id = create_session()
    
    prompt = """Write a complete JSON parser in Python at /tmp/json_parser.py.

    Requirements:
    1. Implement a recursive descent parser that handles:
    - Objects (key-value pairs)
    - Arrays (lists)
    - Strings (with escape sequences: \", \\, \/, backspace, formfeed, newline, carriage return, tab, unicode)
    - Numbers (integers, floats, negative, scientific notation)
    - Booleans (true, false)
    - null
    2. Include a parse(json_string) function that returns the Python object
    3. Include a validate(json_string) function that returns True/False
    4. Include a main() function that:
    - Parses various JSON strings
    - Tests edge cases (empty objects, nested structures, escape sequences)
    - Tests validation of invalid JSON
    - Compares parsed output with json.loads()

    The code must be complete, runnable, and include docstrings."""

    events = send_prompt(session_id, prompt)
    
    filepath = "/tmp/json_parser.py"
    if check_file_exists(filepath, timeout=180):
    content = read_file_content(filepath)
    print(f"✅ File created: {filepath} ({len(content)} bytes)")
        
    try:
    compile(content, filepath, 'exec')
    print("✅ Valid Python syntax")
    except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    return False
        
    checks = [
    ("parse", "parse function"),
    ("validate", "validate function"),
    ("recursive", "recursive approach"),
    ("escape", "escape sequence handling"),
    ("object", "object parsing"),
    ("array", "array parsing"),
    ]
        
    all_passed = True
    for keyword, name in checks:
    if keyword in content:
    print(f"  ✅ {name} found")
    else:
    print(f"  ❌ {name} NOT found")
    all_passed = False
        
    return all_passed
    else:
    print("❌ File not created within timeout")
    return False






    def test_event_emitter():
    """Tektos implements an event emitter with method chaining."""
    print("\n📡 Test 4: Event Emitter (Method Chaining)")
    session_id = create_session()
    
    prompt = """Write a complete Event Emitter implementation in Python at /tmp/event_emitter.py.

    Requirements:
    1. Implement EventEmitter class with:
    - on(event, callback) - register listener (returns self for chaining)
    - off(event, callback) - remove listener (returns self for chaining)
    - once(event, callback) - register one-time listener (returns self for chaining)
    - emit(event, *args, **kwargs) - trigger event (returns self for chaining)
    - remove_all(event) - remove all listeners for event (returns self for chaining)
    2. Support multiple listeners per event
    3. Support wildcard events (e.g., 'user.*' matches 'user.login', 'user.logout')
    4. Include error handling for listener exceptions
    5. Include a main() function that:
    - Demonstrates method chaining
    - Tests wildcard events
    - Tests once() listeners
    - Tests error handling
    - Tests remove_all()

    The code must be complete, runnable, and include docstrings."""

    events = send_prompt(session_id, prompt)
    
    filepath = "/tmp/event_emitter.py"
    if check_file_exists(filepath, timeout=180):
    content = read_file_content(filepath)
    print(f"✅ File created: {filepath} ({len(content)} bytes)")
        
    try:
    compile(content, filepath, 'exec')
    print("✅ Valid Python syntax")
    except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    return False
        
    checks = [
    ("EventEmitter", "EventEmitter class"),
    ("on", "on method"),
    ("off", "off method"),
    ("once", "once method"),
    ("emit", "emit method"),
    ("remove_all", "remove_all method"),
    ("wildcard", "wildcard support"),
    ]
        
    all_passed = True
    for keyword, name in checks:
    if keyword in content:
    print(f"  ✅ {name} found")
    else:
    print(f"  ❌ {name} NOT found")
    all_passed = False
        
    return all_passed
    else:
    print("❌ File not created within timeout")
    return False






    def test_http_simulator():
    """Tektos implements HTTP request simulator with retry logic."""
    print("\n🌐 Test 5: HTTP Request Simulator (Retry Logic)")
    session_id = create_session()
    
    prompt = """Write a complete HTTP Request Simulator in Python at /tmp/http_simulator.py.

    Requirements:
    1. Implement HttpRequestSimulator class with:
    - get(url, headers=None, params=None) - simulate GET request
    - post(url, data=None, headers=None) - simulate POST request
    - put(url, data=None, headers=None) - simulate PUT request
    - delete(url, headers=None) - simulate DELETE request
    2. Implement retry logic with:
    - configurable max_retries (default 3)
    - configurable backoff_factor (default 1.0)
    - exponential backoff between retries
    - configurable retryable status codes (default 500, 502, 503, 504)
    3. Include a mock_response() method that simulates server responses
    4. Include a main() function that:
    - Tests successful requests
    - Tests retry logic with failing requests
    - Tests different HTTP methods
    - Tests backoff timing
    - Tests max retries exceeded

    The code must be complete, runnable, and include docstrings."""

    events = send_prompt(session_id, prompt)
    
    filepath = "/tmp/http_simulator.py"
    if check_file_exists(filepath, timeout=180):
    content = read_file_content(filepath)
    print(f"✅ File created: {filepath} ({len(content)} bytes)")
        
    try:
    compile(content, filepath, 'exec')
    print("✅ Valid Python syntax")
    except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    return False
        
    checks = [
    ("HttpRequestSimulator", "HttpRequestSimulator class"),
    ("get", "get method"),
    ("post", "post method"),
    ("put", "put method"),
    ("delete", "delete method"),
    ("retry", "retry logic"),
    ("backoff", "backoff logic"),
    ]
        
    all_passed = True
    for keyword, name in checks:
    if keyword in content:
    print(f"  ✅ {name} found")
    else:
    print(f"  ❌ {name} NOT found")
    all_passed = False
        
    return all_passed
    else:
    print("❌ File not created within timeout")
    return False






    def test_task_pipeline():
    """Tektos implements a task pipeline with multiple stages."""
    print("\n🔄 Test 6: Task Pipeline (Multi-Stage)")
    session_id = create_session()
    
    prompt = """Write a complete Task Pipeline implementation in Python at /tmp/task_pipeline.py.

    Requirements:
    1. Implement TaskPipeline class with:
    - add_stage(name, func) - add a processing stage
    - set_parallel(stages) - mark stages for parallel execution
    - set_dependency(stage, depends_on) - set stage dependencies
    - run(data) - execute the pipeline
    - get_status() - return pipeline status
    2. Support:
    - Sequential stages (A → B → C)
    - Parallel stages (A and B run concurrently, then C)
    - Stage dependencies (C depends on A and B)
    - Error handling (skip failed stages, continue with others)
    - Stage result caching
    3. Include a main() function that:
    - Creates a pipeline with 5 stages
    - Demonstrates sequential execution
    - Demonstrates parallel execution
    - Demonstrates dependency handling
    - Tests error handling
    - Prints pipeline execution log

    The code must be complete, runnable, and include docstrings."""

    events = send_prompt(session_id, prompt)
    
    filepath = "/tmp/task_pipeline.py"
    if check_file_exists(filepath, timeout=180):
    content = read_file_content(filepath)
    print(f"✅ File created: {filepath} ({len(content)} bytes)")
        
    try:
    compile(content, filepath, 'exec')
    print("✅ Valid Python syntax")
    except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
    return False
        
    checks = [
    ("TaskPipeline", "TaskPipeline class"),
    ("add_stage", "add_stage method"),
    ("set_parallel", "set_parallel method"),
    ("set_dependency", "set_dependency method"),
    ("run", "run method"),
    ("parallel", "parallel execution"),
    ("dependency", "dependency handling"),
    ]
        
    all_passed = True
    for keyword, name in checks:
    if keyword in content:
    print(f"  ✅ {name} found")
    else:
    print(f"  ❌ {name} NOT found")
    all_passed = False
        
    return all_passed
    else:
    print("❌ File not created within timeout")
    return False

    # ─── Main ──────────────────────────────────────────────────────────────────────

    def main():
    print("=" * 60)
    print("Tektos-Ultima v1 — Moderately Difficult Coding Tests")
    print("=" * 60)
    
    # Check backend is running
    try:
    resp = requests.get(f"{BACKEND}/health", timeout=5)
    resp.raise_for_status()
    print(f"✅ Backend is running: {resp.json()}")
    except Exception as e:
    print(f"❌ Backend is not running: {e}")
    sys.exit(1)
    
    tests = [
    ("BST with Rotations", test_bst_with_rotations),
    ("LRU Cache", test_lru_cache),
    ("JSON Parser", test_json_parser),
    ("Event Emitter", test_event_emitter),
    ("HTTP Simulator", test_http_simulator),
    ("Task Pipeline", test_task_pipeline),
    ]
    
    results = []
    for name, test_func in tests:
    try:
    passed = test_func()
    results.append((name, passed))
    except Exception as e:
    print(f"❌ Test '{name}' raised exception: {e}")
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

    success = main()
    sys.exit(0 if success else 1)
