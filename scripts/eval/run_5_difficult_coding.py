#!/usr/bin/env python3
"""Run 5 difficult coding tests against Tektos-Ultima v1."""

import requests
import time
import os
import sys

BASE_URL = "http://localhost:8020"
TEST_DIR = "/home/rmholston/dev/tektos-ultima-v1"

TESTS = [
    {
        "name": "LZW Compression",
        "prompt": """Write a complete LZW (Lempel-Ziv-Welch) compression and decompression implementation in Python at /tmp/lzw_compression.py.

Requirements:
1. Create a class `LZWCompressor` with methods `compress(text: str) -> bytes` and `decompress(compressed: bytes) -> str`
2. Use a dictionary-based approach starting with 256 entries (ASCII characters)
3. The compressed output should be a bytes object containing: 2-byte code length prefix, then the code stream
4. Handle edge cases: empty string, single character, repeated patterns
5. Include a `__main__` block that demonstrates compression/decompression with at least 3 test strings
6. The decompression must perfectly reconstruct the original input
7. Include docstrings and type hints
8. The implementation should be self-contained (no external dependencies)
9. Include a `get_dict_size()` method to report the final dictionary size
10. Add a `compression_ratio(original: str, compressed: bytes) -> float` function""",
        "keywords": ["LZWCompressor", "compress", "decompress", "dictionary", "__main__", "compression_ratio"],
        "timeout": 900,
    },
    {
        "name": "Red-Black Tree",
        "prompt": """Write a complete Red-Black Tree implementation in Python at /tmp/red_black_tree.py.

Requirements:
1. Create a class `Node` with attributes: key, color (0=black, 1=red), left, right, parent
2. Create a class `RedBlackTree` with methods: `insert(key)`, `search(key) -> bool`, `inorder() -> list`, `min()`, `max()`
3. Implement left_rotate and right_rotate methods
4. Implement insert_fixup to maintain Red-Black properties
5. Include a `is_valid()` method that checks: root is black, no red-red violations, black-height consistency
6. Include a `height() -> int` method
7. Include a `__main__` block that inserts 15+ nodes, prints inorder, verifies validity, and tests search
8. Handle duplicate keys by ignoring them
9. Include docstrings
10. The implementation should be self-contained (no external dependencies)""",
        "keywords": ["RedBlackTree", "Node", "insert", "search", "is_valid", "inorder", "left_rotate", "right_rotate"],
        "timeout": 900,
    },
    {
        "name": "HTTP/1.1 Request Parser",
        "prompt": """Write a complete HTTP/1.1 request parser in Python at /tmp/http_parser.py.

Requirements:
1. Create a class `HTTPParser` with method `parse(request_line: str, headers: list[str], body: str = '') -> dict`
2. Parse the request line into method, path, query parameters, and HTTP version
3. Parse headers into a dictionary (handle duplicate headers by making them lists)
4. Handle query string parsing (e.g., '/search?q=test&page=2' -> {'q': 'test', 'page': '2'})
5. Support all common HTTP methods: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
6. Include a `parse_raw(raw_request: str) -> dict` method that parses a complete raw HTTP request string
7. Include a `build_response(status_code: int, status_text: str, headers: dict, body: str = '') -> str` method
8. Include a `__main__` block that tests parsing at least 5 different request types
9. Handle edge cases: malformed requests, missing fields, unusual whitespace
10. Include docstrings and type hints
11. The implementation should be self-contained (no external dependencies)""",
        "keywords": ["HTTPParser", "parse", "parse_raw", "build_response", "query", "__main__"],
        "timeout": 900,
    },
    {
        "name": "Merkle Tree",
        "prompt": """Write a complete Merkle Tree implementation in Python at /tmp/merkle_tree.py.

Requirements:
1. Create a class `MerkleTree` with methods: `build(leaves: list[str])`, `get_root() -> str`, `get_proof(index: int) -> list[str]`, `verify_proof(leaf: str, proof: list[str], root: str, index: int) -> bool`
2. Use SHA-256 for all hashing operations
3. Handle odd number of leaves by duplicating the last leaf
4. The proof should be a list of sibling hashes needed to reconstruct the root
5. Include a `get_leaves() -> list[str]` method to retrieve all leaf hashes
6. Include a `verify(leaf: str, proof: list[str], root: str) -> bool` convenience method
7. Include a `__main__` block that builds a tree with 8+ leaves, generates proofs for several leaves, and verifies them
8. Include a `get_tree_structure() -> dict` method that returns the tree as a nested dictionary
9. Handle edge cases: empty input, single leaf, large number of leaves
10. Include docstrings and type hints
11. The implementation should be self-contained (no external dependencies)""",
        "keywords": ["MerkleTree", "build", "get_root", "get_proof", "verify_proof", "SHA-256", "__main__"],
        "timeout": 900,
    },
    {
        "name": "Trie with Autocomplete",
        "prompt": """Write a complete Trie (Prefix Tree) with autocomplete functionality in Python at /tmp/trie_autocomplete.py.

Requirements:
1. Create a class `TrieNode` with children dict, is_end_of_word flag, and word_count
2. Create a class `Trie` with methods: `insert(word: str)`, `search(word: str) -> bool`, `starts_with(prefix: str) -> bool`, `autocomplete(prefix: str, limit: int = 10) -> list[str]`
3. The `autocomplete` method should return up to `limit` words that start with the given prefix, sorted alphabetically
4. Include a `delete(word: str) -> bool` method that removes a word from the trie
5. Include a `count_words_with_prefix(prefix: str) -> int` method
6. Include a `get_all_words() -> list[str]` method that returns all words in the trie
7. Include a `__main__` block that demonstrates: inserting 20+ words, searching, deleting, autocomplete with various prefixes
8. Handle edge cases: empty prefix, non-existent words, case-insensitive search option
9. Include a `get_words_by_length(min_len: int, max_len: int) -> dict[int, list[str]]` method
10. Include docstrings and type hints
11. The implementation should be self-contained (no external dependencies)""",
        "keywords": ["TrieNode", "Trie", "insert", "search", "autocomplete", "delete", "__main__"],
        "timeout": 900,
    },
]


def create_session():
    """Create a new Tektos session and return session_id."""
    resp = requests.post(f"{BASE_URL}/api/sessions", json={
        "model": "Qwen3.6-35B-A3B-Q4_K_M",
        "cwd": TEST_DIR,
        "provider": "local",
        "permission_mode": "auto",
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("session_id") or data.get("id")


def send_prompt(session_id: str, prompt: str):
    """Send a coding prompt and collect all SSE events."""
    resp = requests.post(
        f"{BASE_URL}/api/prompt/sse",
        json={"prompt": prompt, "session_id": session_id},
        stream=True,
        timeout=900,
    )
    resp.raise_for_status()

    event_count = 0
    for line in resp.iter_lines():
        if line:
            line_str = line.decode("utf-8")
            if line_str.startswith("data:"):
                event_count += 1

    return event_count


def wait_for_file(filepath: str, timeout: int):
    """Wait for a file to appear."""
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(filepath):
            return filepath
        time.sleep(2)
    return None


def verify_file(filepath: str, keywords: list[str]):
    """Verify the generated file contains required keywords."""
    if not filepath or not os.path.exists(filepath):
        return False, ["FILE_NOT_FOUND"]

    with open(filepath, "r") as f:
        content = f.read()

    missing = [kw for kw in keywords if kw not in content]
    return len(missing) == 0, missing


def run_test(test: dict):
    """Run a single coding test."""
    print(f"\n{'='*60}")
    print(f"TEST: {test['name']}")
    print(f"{'='*60}")

    # Create session
    session_id = create_session()
    print(f"Session created: {session_id}")

    # Send prompt
    start_time = time.time()
    event_count = send_prompt(session_id, test["prompt"])
    working_time = time.time() - start_time
    print(f"SSE events: {event_count}")
    print(f"Working time: {working_time:.1f}s")

    # Determine output filename
    filename = test["name"].lower().replace(" ", "_") + ".py"
    filepath = f"/tmp/{filename}"

    # Wait for file
    print(f"Waiting for {filename}...")
    filepath = wait_for_file(filepath, test["timeout"])

    if not filepath:
        print(f"❌ TIMEOUT: File {filename} not created within {test['timeout']}s")
        return {
            "name": test["name"],
            "result": "TIMEOUT",
            "events": event_count,
            "time": working_time,
            "file_size": 0,
            "keywords_pass": False,
            "missing_keywords": test["keywords"],
        }

    # Read and verify
    with open(filepath, "r") as f:
        content = f.read()
    file_size = len(content.encode("utf-8"))
    print(f"File created: {filepath} ({file_size}B)")

    keywords_pass, missing = verify_file(filepath, test["keywords"])
    print(f"Keywords: {'PASS' if keywords_pass else 'FAIL'}")
    if missing:
        print(f"  Missing: {missing}")

    # Compile check
    try:
        compile(content, filename, "exec")
        compile_ok = True
        print("Syntax: VALID")
    except SyntaxError as e:
        compile_ok = False
        print(f"Syntax: INVALID — {e}")

    result = "PASS" if keywords_pass and compile_ok else "FAIL"
    print(f"Result: {result}")

    return {
        "name": test["name"],
        "result": result,
        "events": event_count,
        "time": working_time,
        "file_size": file_size,
        "keywords_pass": keywords_pass,
        "missing_keywords": missing,
        "compile_ok": compile_ok,
    }


def main():
    print("Tektos-Ultima v1 — 5 Difficult Coding Tests")
    print(f"Backend: {BASE_URL}")
    print(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    results = []
    for test in TESTS:
        result = run_test(test)
        results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"{'Test':<30} {'Result':<10} {'Events':<8} {'Time':<8} {'Size':<8} {'Keywords'}")
    print("-" * 80)
    for r in results:
        size_str = f"{r['file_size']}B" if r['file_size'] else "N/A"
        kw_str = "PASS" if r['keywords_pass'] else "FAIL"
        print(f"{r['name']:<30} {r['result']:<10} {r['events']:<8} {r['time']:<8.1f}s {size_str:<8} {kw_str}")

    passed = sum(1 for r in results if r['result'] == 'PASS')
    total = len(results)
    print(f"\nTotal: {passed}/{total} passed ({passed/total*100:.0f}%)")

    return results


if __name__ == "__main__":
    main()
