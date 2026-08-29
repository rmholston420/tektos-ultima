#!/usr/bin/env python3
"""
Tektos-Ultima v1 — 5 Extremely Difficult Agent Coding Tests

These tests push the LLM to its limits with systems-level programming tasks
that require deep algorithmic knowledge, multi-component architecture, and
careful integration. Each test is designed to stress the full agent loop:
LLM → tools → LLM → ... until completion.

Difficulty rationale:
  1. Raft Consensus — distributed systems, state machines, leader election
  2. Neural Network from scratch — calculus, backprop, matrix ops without numpy
  3. SQL Query Engine — parser, optimizer, execution plan, joins
  4. Mark-Sweep-Compact GC — graph traversal, pointer analysis, compaction
  5. Merkle Patricia Trie — cryptographic hashing, trie with path compression

Each test uses simplified prompts and 900s timeout.
Files are written to project root (sandbox), not /tmp.
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
    """Create a new Tektos session and return session_id."""
    resp = requests.post(f"{BACKEND}/api/sessions", json={
        "model": "Qwen_Qwen3.6-35B-A3B-Q5_K_M",
        "cwd": TEST_DIR,
        "provider": "local",
        "permission_mode": "auto",
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("session_id") or data.get("id")


def send_prompt(session_id, prompt, timeout=900):
    """Send a coding prompt via SSE and collect events."""
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
        if line.startswith(b"event: "):
            current_event = line[7:].decode()
        elif line.startswith(b"data: "):
            data = json.loads(line[6:].decode())
            events.append({"type": current_event, "data": data})

    return events


def check_file_exists(filepath, timeout=900):
    """Wait for a file to appear, with progress reporting."""
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
    """Read file content."""
    with open(filepath, 'r') as f:
        return f.read()


def verify_file(filepath, checks, test_name):
    """Verify file exists, has valid syntax, and contains required keywords."""
    if not check_file_exists(filepath, timeout=TIMEOUT):
        print(f"❌ {test_name}: File not created within {TIMEOUT}s")
        return False

    content = read_file_content(filepath)
    print(f"✅ {test_name}: File created ({len(content)} bytes)")

    # Syntax check
    try:
        compile(content, filepath, 'exec')
        print(f"  ✅ Valid Python syntax")
    except SyntaxError as e:
        print(f"  ❌ Syntax error: {e}")
        return False

    # Keyword checks
    all_passed = True
    for keyword, name in checks:
        if keyword in content:
            print(f"  ✅ {name} found")
        else:
            print(f"  ❌ {name} NOT found")
            all_passed = False

    return all_passed


# ─── Test 1: Raft Consensus Protocol ──────────────────────────────────────────

def test_raft_consensus():
    """
    Extremely Difficult 1: Raft Consensus Protocol Implementation

    Raft is one of the hardest distributed systems algorithms to implement
    correctly. It requires leader election, log replication, safety guarantees,
    and proper state machine management.
    """
    print("\n" + "=" * 60)
    print("🔴 EXTREMELY DIFFICULT 1: Raft Consensus Protocol")
    print("=" * 60)
    session_id = create_session()

    prompt = """Write a Raft consensus protocol simulator in Python at raft_consensus.py.

Requirements:
1. RaftNode class with states: FOLLOWER, CANDIDATE, LEADER
2. Leader election with randomized timeouts and term management
3. Log replication: append entries, commit indices, persistence
4. Safety: leader completeness property, log matching property
5. Client command submission via leader, response propagation
6. Heartbeat mechanism to maintain leader authority
7. simulate(nodes, commands) function that runs the protocol
8. __main__ block: create 5-node cluster, submit commands, verify consensus

Keep it simple and concise. Use asyncio for concurrency simulation."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")

    return verify_file("raft_consensus.py", [
        ("RaftNode", "RaftNode class"),
        ("FOLLOWER", "FOLLOWER state"),
        ("CANDIDATE", "CANDIDATE state"),
        ("LEADER", "LEADER state"),
        ("append_entries", "log replication"),
        ("heartbeat", "heartbeat mechanism"),
        ("simulate", "simulate function"),
        ("__main__", "main block"),
    ], "Extremely Difficult 1: Raft Consensus")


# ─── Test 2: Neural Network from Scratch ──────────────────────────────────────

def test_neural_network():
    """
    Extremely Difficult 2: Neural Network from Scratch (No NumPy)

    Building a neural network without numpy requires implementing matrix
    operations, backpropagation with chain rule, and activation functions
    entirely in pure Python. This tests the LLM's ability to handle
    mathematical computation without libraries.
    """
    print("\n" + "=" * 60)
    print("🔴 EXTREMELY DIFFICULT 2: Neural Network from Scratch")
    print("=" * 60)
    session_id = create_session()

    prompt = """Write a neural network from scratch in pure Python (no numpy, no torch) at neural_network.py.

Requirements:
1. Matrix class with __add__, __sub__, __mul__, __matmul__, transpose, zeros, ones
2. Activation functions: sigmoid, relu, tanh, softmax with derivatives
3. Dense layer class with forward and backward methods
4. Network class with multiple layers, forward pass, backward pass (backprop)
5. SGD optimizer with learning rate and momentum
6. train(X, y, epochs, batch_size) method with mini-batch training
7. predict(X) method for inference
8. __main__ block: train on XOR problem, verify it learns (accuracy > 90%)
9. All matrix operations must be pure Python (list of lists)

Keep it simple and concise. The XOR problem is 4 samples with 2 inputs."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")

    return verify_file("neural_network.py", [
        ("Matrix", "Matrix class"),
        ("sigmoid", "sigmoid activation"),
        ("relu", "relu activation"),
        ("Dense", "Dense layer"),
        ("backward", "backward pass"),
        ("train", "train method"),
        ("predict", "predict method"),
        ("XOR", "XOR problem"),
        ("__main__", "main block"),
    ], "Extremely Difficult 2: Neural Network")


# ─── Test 3: SQL Query Engine with Optimizer ──────────────────────────────────

def test_sql_engine():
    """
    Extremely Difficult 3: SQL Query Engine with Query Optimizer

    A SQL engine requires a lexer, parser, AST, query optimizer (join ordering,
    index selection), and execution engine. This is a full compiler project.
    """
    print("\n" + "=" * 60)
    print("🔴 EXTREMELY DIFFICULT 3: SQL Query Engine")
    print("=" * 60)
    session_id = create_session()

    prompt = """Write a SQL query engine in Python at sql_engine.py.

Requirements:
1. Lexer: tokenize SQL (SELECT, FROM, WHERE, AND, OR, =, >, <, *, identifiers, literals)
2. Parser: produce AST nodes (SelectStmt, TableRef, Condition, BinaryOp, ColumnRef, Literal)
3. In-memory table storage: Table class with columns, rows, insert(), select()
4. Query execution: evaluate WHERE conditions, project columns, handle JOINs
5. Query optimizer: choose best join order for multi-table queries
6. Support: SELECT with WHERE, AND/OR, ORDER BY, JOIN (INNER JOIN), COUNT/SUM aggregates
7. execute(sql) function that chains lexer → parser → optimizer → executor
8. __main__ block: create tables, insert data, run queries, verify results

Keep it simple and concise. Focus on correctness over performance."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")

    return verify_file("sql_engine.py", [
        ("Lexer", "Lexer class"),
        ("Parser", "Parser class"),
        ("SelectStmt", "Select AST node"),
        ("Table", "Table class"),
        ("execute", "execute function"),
        ("JOIN", "JOIN support"),
        ("optimize", "query optimizer"),
        ("__main__", "main block"),
    ], "Extremely Difficult 3: SQL Query Engine")


# ─── Test 4: Mark-Sweep-Compact Garbage Collector ─────────────────────────────

def test_garbage_collector():
    """
    Extremely Difficult 4: Mark-Sweep-Compact Garbage Collector

    A GC requires graph traversal (mark phase), free list management (sweep),
    and object compaction with pointer rewriting. This tests the LLM's ability
    to implement low-level memory management.
    """
    print("\n" + "=" * 60)
    print("🔴 EXTREMELY DIFFICULT 4: Mark-Sweep-Compact Garbage Collector")
    print("=" * 60)
    session_id = create_session()

    prompt = """Write a Mark-Sweep-Compact garbage collector in Python at garbage_collector.py.

Requirements:
1. Object class with id, size, references (list of Object ids), marked flag
2. Heap class managing a pool of objects with allocation and deallocation
3. Mark phase: DFS traversal from roots, marking reachable objects
4. Sweep phase: collect unmarked objects, return to free list
5. Compact phase: move live objects to eliminate fragmentation, rewrite references
6. GC collector class with collect() method that runs mark-sweep-compact
7. Root tracking: set_roots() to define GC roots
8. Fragmentation metric: calculate and report before/after compaction
9. __main__ block: create object graph with cycles, allocate, free some, run GC, verify

Keep it simple and concise. Use integer IDs for object references."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")

    return verify_file("garbage_collector.py", [
        ("Object", "Object class"),
        ("Heap", "Heap class"),
        ("mark", "mark phase"),
        ("sweep", "sweep phase"),
        ("compact", "compact phase"),
        ("collect", "collect method"),
        ("roots", "root tracking"),
        ("__main__", "main block"),
    ], "Extremely Difficult 4: Garbage Collector")


# ─── Test 5: Merkle Patricia Trie ─────────────────────────────────────────────

def test_merkle_patricia():
    """
    Extremely Difficult 5: Merkle Patricia Trie (MPT)

    MPTs combine Merkle trees (cryptographic integrity) with Patricia tries
    (path compression). They're used in Ethereum state storage. Requires
    cryptographic hashing, trie with path compression, and proof generation.
    """
    print("\n" + "=" * 60)
    print("🔴 EXTREMELY DIFFICULT 5: Merkle Patricia Trie")
    print("=" * 60)
    session_id = create_session()

    prompt = """Write a Merkle Patricia Trie in Python at merkle_patricia.py.

Requirements:
1. Node types: BranchNode (16 children + value), ExtensionNode (prefix + child), LeafNode (key suffix + value), NullNode
2. insert(key, value) method with proper trie construction and path compression
3. delete(key) method that removes a key and cleans up empty nodes
4. get(key) method returning value or None
5. get_root_hash() using SHA-256 of serialized node for Merkle integrity
6. get_proof(key) returning a list of nodes needed to verify inclusion
7. verify_proof(key, value, proof, root_hash) returning bool
8. MerklePatriciaTrie class with all operations
9. __main__ block: insert 20+ key-value pairs, verify get/delete, generate and verify proofs

Keep it simple and concise. Use hex-encoded keys (like Ethereum)."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")

    return verify_file("merkle_patricia.py", [
        ("MerklePatriciaTrie", "MPT class"),
        ("BranchNode", "BranchNode type"),
        ("LeafNode", "LeafNode type"),
        ("insert", "insert method"),
        ("delete", "delete method"),
        ("get", "get method"),
        ("get_root_hash", "root hash"),
        ("get_proof", "proof generation"),
        ("verify_proof", "proof verification"),
        ("__main__", "main block"),
    ], "Extremely Difficult 5: Merkle Patricia Trie")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Tektos-Ultima v1 — 5 EXTREMELY DIFFICULT Agent Tests")
    print("=" * 60)

    # Check backend
    try:
        resp = requests.get(f"{BACKEND}/health", timeout=5)
        resp.raise_for_status()
        health = resp.json()
        print(f"✅ Backend running: LLM={health.get('llm_url', 'unknown')}, Model={health.get('llm_model', 'unknown')}")
        print(f"   Active sessions: {health.get('active_sessions', 'unknown')}")
    except Exception as e:
        print(f"❌ Backend not running: {e}")
        sys.exit(1)

    tests = [
        ("Extremely Difficult 1: Raft Consensus", test_raft_consensus),
        ("Extremely Difficult 2: Neural Network from Scratch", test_neural_network),
        ("Extremely Difficult 3: SQL Query Engine", test_sql_engine),
        ("Extremely Difficult 4: Mark-Sweep-Compact GC", test_garbage_collector),
        ("Extremely Difficult 5: Merkle Patricia Trie", test_merkle_patricia),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n{'#' * 60}")
        print(f"Running: {name}")
        print(f"{'#' * 60}")
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
    print("FINAL SUMMARY")
    print("=" * 60)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} — {name}")

    print(f"\n{passed_count}/{total_count} tests passed ({passed_count/total_count*100:.0f}%)")

    if passed_count == total_count:
        print("\n🎉 All extremely difficult tests passed!")
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")

    return passed_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
