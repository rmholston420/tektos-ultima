import asyncio
import json
import websockets
import urllib.request

async def live_demo():
    # Create session
    req = urllib.request.Request(
        'http://localhost:8020/api/sessions',
        data=b'{}',
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        session = json.loads(resp.read())
        session_id = session['id']
    
    print(f"=== Session: {session_id} ===")
    print(f"=== Sending: 'Write a haiku about code and coffee' ===")
    print()
    
    uri = f'ws://localhost:8020/ws/{session_id}'
    async with websockets.connect(uri) as ws:
        # session.ready
        resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(resp)
        
        # Send prompt
        prompt = json.dumps({
            'type': 'prompt',
            'session_id': session_id,
            'prompt': 'Write a haiku about code and coffee'
        })
        await ws.send(prompt)
        
        # Stream events in real-time
        delta_count = 0
        full_text = ""
        for i in range(200):
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=60.0)
                data = json.loads(resp)
                et = data.get('event_type', 'unknown')
                
                if et == 'assistant.delta':
                    delta_count += 1
                    text = data.get('payload', {}).get('text', '')
                    full_text += text
                    
                    # Print streaming effect
                    if delta_count <= 5:
                        print(f"  [delta #{delta_count}] {text!r}")
                    elif delta_count == 6:
                        print(f"  [delta #{delta_count}] ... (streaming {delta_count} tokens so far) ...")
                    elif delta_count >= 125:
                        print(f"  [delta #{delta_count}] {text!r}")
                    
                elif et == 'assistant.completed':
                    print()
                    print(f"✓ assistant.completed ({delta_count} deltas)")
                    print()
                    print(f"=== Final Response ===")
                    print(f"---")
                    print(full_text)
                    print(f"---")
                    break
                elif et == 'session.ready':
                    print("[session.ready]")
                else:
                    print(f"[{et}]")
            except asyncio.TimeoutError:
                print(f"\n⚠ Timeout after {delta_count} deltas")
                break

asyncio.run(live_demo())
