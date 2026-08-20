import asyncio
import json
import websockets
import urllib.request

async def test():
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
        print(f'Session: {session_id}')

    uri = f'ws://localhost:8020/ws/{session_id}'
    try:
        async with websockets.connect(uri) as ws:
            # Wait for session.ready
            resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(resp)
            print(f'Event: {data.get("event_type", "unknown")}')

            # Send prompt
            prompt = json.dumps({
                'type': 'prompt',
                'session_id': session_id,
                'prompt': 'Say hi in 3 words'
            })
            await ws.send(prompt)
            print('Sent prompt')

            # Receive events with higher budget
            delta_count = 0
            for i in range(200):
                try:
                    resp = await asyncio.wait_for(ws.recv(), timeout=60.0)
                    data = json.loads(resp)
                    et = data.get('event_type', 'unknown')
                    if et == 'assistant.delta':
                        delta_count += 1
                        text = data.get('payload', {}).get('text', '')
                        if delta_count <= 3 or delta_count % 50 == 0 or delta_count >= 125:
                            print(f'  delta #{delta_count}: {text!r}')
                    elif et == 'assistant.completed':
                        print(f'✓ assistant.completed RECEIVED (after {delta_count} deltas)')
                        break
                    elif et == 'session.ready':
                        print('  session.ready')
                    else:
                        print(f'  event: {et}')
                except asyncio.TimeoutError:
                    print(f'⚠ Timeout after {delta_count} deltas')
                    break
            print(f'Done. Total deltas: {delta_count}')
    except Exception as e:
        print(f'Error: {e}')

asyncio.run(test())
