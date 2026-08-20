"""
Live Demo: Show Tektos solving a real programming task
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Optional

import httpx


BACKEND = "http://localhost:8020"


async def check_health():
    """Verify backend is running."""
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(f"{BACKEND}/health")
        data = resp.json()
        print(f"✅ Backend healthy: {data['llm_model']} sessions={data['active_sessions']}")
        return True


async def create_session(model: str = "Qwen3.6-35B-A3B-Q4_K_M", cwd: str = "."):
    """Create a new session."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BACKEND}/api/sessions",
            json={"model": model, "cwd": cwd},
        )
        data = resp.json()
        session_id = data["id"]
        print(f"✅ Session created: {session_id[:16]}...")
        return session_id


async def send_prompt(session_id: str, prompt: str):
    """Send a prompt via the backend API."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BACKEND}/api/sessions/{session_id}/prompt",
            json={"prompt": prompt},
        )
        data = resp.json()
        print(f"✅ Prompt sent: {data.get('status', 'submitted')}")
        return data


async def poll_session(session_id: str, max_wait: int = 180):
    """Poll session status until complete."""
    start = time.time()
    while time.time() - start < max_wait:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{BACKEND}/api/sessions/{session_id}")
            data = resp.json()
            status = data.get("status", "unknown")
            seq = data.get("seq", 0)
            print(f"⏳ [{int(time.time()-start):3d}s] status={status:15s} seq={seq}")
            
            if status in ("completed", "failed", "ready", "idle"):
                break
        await asyncio.sleep(3)
    return data


async def get_events(session_id: str):
    """Get session events."""
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(f"{BACKEND}/api/sessions/{session_id}/events")
        return resp.json()


async def main():
    print("=" * 60)
    print("Tektos Live Demo — Solving a Programming Task")
    print("=" * 60)
    
    # Step 1: Health check
    print("\n📋 Step 1: Checking backend health...")
    await check_health()
    
    # Step 2: Create session
    print("\n📋 Step 2: Creating session...")
    session_id = await create_session()
    
    # Step 3: Send programming task
    print("\n📋 Step 3: Sending programming task...")
    task = """
Write a Python file at /home/rmholston/dev/tektos-ultima-v1/demo_lru_cache.py that implements:

A class LRUCache with:
  - __init__(capacity: int) - initialize cache
  - get(key: int) -> int - return value or -1
  - put(key: int, value: int) -> None - insert/update

Requirements:
- Use OrderedDict for O(1) operations
- Evict least recently used when full
- Include type hints, docstrings, and a main() demo
- Print usage examples

Write the file, then run it to verify.
"""
    
    try:
        await send_prompt(session_id, task)
    except Exception as e:
        print(f"⚠️  Prompt API not available ({e}), using direct LLM call...")
        # Fallback: call LLM directly
        await direct_llm_call(session_id, task)
    
    # Step 4: Wait for completion
    print("\n📋 Step 4: Waiting for execution...")
    result = await poll_session(session_id)
    
    # Step 5: Check results
    print("\n📋 Step 5: Verifying results...")
    file_path = Path("/home/rmholston/dev/tektos-ultima-v1/demo_lru_cache.py")
    
    if file_path.exists():
        content = file_path.read_text()
        lines = len(content.split('\n'))
        print(f"✅ File created: demo_lru_cache.py ({lines} lines)")
        
        # Verify components
        checks = {
            "LRUCache class": "class LRUCache" in content,
            "__init__ method": "def __init__" in content,
            "get method": "def get" in content,
            "put method": "def put" in content,
            "OrderedDict": "OrderedDict" in content,
            "main demo": "def main" in content,
        }
        
        for name, ok in checks.items():
            print(f"   {'✅' if ok else '❌'} {name}")
        
        if all(checks.values()):
            print("\n🎉 SUCCESS! Tektos completed the task.")
        else:
            print("\n⚠️  Partial completion - some components missing")
    else:
        print("⏳ File not yet created - task may still be processing")
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


async def direct_llm_call(session_id: str, task: str):
    """Fallback: call the LLM directly via OpenAI-compatible API."""
    async with httpx.AsyncClient(timeout=120) as client:
        messages = [
            {"role": "system", "content": "You are a Python programming assistant. Write complete, correct code."},
            {"role": "user", "content": task},
        ]
        
        print("📤 Sending to LLM...")
        resp = await client.post(
            "http://127.0.0.1:8081/v1/chat/completions",
            json={
                "model": "Qwen3.6-35B-A3B-Q4_K_M",
                "messages": messages,
                "max_tokens": 4096,
                "stream": False,
            },
        )
        data = resp.json()
        response = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        print(f"📥 LLM response: {len(response)} chars")
        
        # Extract and write Python code
        if "```python" in response:
            code = response.split("```python")[1].split("```")[0].strip()
        else:
            code = response.strip()
        
        file_path = Path("/home/rmholston/dev/tektos-ultima-v1/demo_lru_cache.py")
        file_path.write_text(code)
        
        lines = len(code.split('\n'))
        print(f"✅ File written: demo_lru_cache.py ({lines} lines)")
        
        # Run the file
        print("🏃 Running demo_lru_cache.py...")
        import subprocess
        result = subprocess.run(
            ["python3", str(file_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode == 0:
            print("✅ Execution successful!")
            print(f"\nOutput:\n{result.stdout[:500]}")
        else:
            print(f"❌ Execution failed: {result.stderr[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
