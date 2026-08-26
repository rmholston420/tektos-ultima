"""Simple test: can the agent write a file?"""
import requests
import json
import os
import time

BACKEND = "http://localhost:8020"

# Check backend
resp = requests.get(f"{BACKEND}/health", timeout=5)
resp.raise_for_status()
print(f"✅ Backend: {resp.json()['llm_model']}")

# Create session
resp = requests.post(f"{BACKEND}/api/sessions", json={
    "model": "Qwen_Qwen3.6-35B-A3B-Q5_K_M",
    "cwd": ".",
    "provider": "local",
    "permission_mode": "auto"
})
session_id = resp.json().get("session_id") or resp.json().get("id")
print(f"✅ Session: {session_id}")

# Send prompt
resp = requests.post(
    f"{BACKEND}/api/prompt/sse",
    json={"prompt": "Write a file at /tmp/simple_test.md with content 'Hello from the agent'. Include the word 'hello' in the content.", "session_id": session_id},
    stream=True,
    timeout=120
)
print(f"✅ Response: {resp.status_code}")

# Collect events
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

print(f"📊 Events: {len(events)}")
event_types = {}
for e in events:
    event_types[e["type"]] = event_types.get(e["type"], 0) + 1
print(f"📊 Event types: {json.dumps(event_types, indent=2)}")

# Check file
time.sleep(5)
if os.path.exists("/tmp/simple_test.md"):
    content = open("/tmp/simple_test.md").read()
    print(f"✅ File exists! ({len(content)} bytes)")
    print(f"   Content preview: {content[:200]}")
    if "hello" in content.lower():
        print("✅ Contains 'hello'")
    else:
        print("❌ Missing 'hello'")
else:
    print("❌ File not created")
