import asyncio
import json
import websockets
import httpx

async def main():
    # Get a session ID first
    async with httpx.AsyncClient() as client:
        resp = await client.post('http://localhost:8000/api/sessions', 
                                json={'model': 'qwen3.6-35b-a3b-ud-q4_k_xl'})
        data = resp.json()
        session_id = data['id']
        print(f"Created session: {session_id}")
        
        # Connect via WebSocket
        ws_url = f"ws://localhost:8000/ws/{session_id}"
        print(f"Connecting to WS: {ws_url}")
        
        async with websockets.connect(ws_url) as ws:
            # Read first message
            msg = await ws.recv()
            print(f"First msg: {msg}")
            
            # Send a prompt
            prompt = json.dumps({
                'type': 'prompt',
                'session_id': session_id,
                'prompt': 'Write a Python function that reverses a string. Keep it simple.'
            })
            print(f"Sending prompt: {prompt[:100]}...")
            await ws.send(prompt)
            
            # Wait for events
            print("\nWaiting for events...")
            for i in range(30):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    data = json.loads(msg)
                    etype = data.get('event_type', data.get('type', 'unknown'))
                    payload = str(data.get('payload', {}))[:150]
                    print(f"  Event {i}: {etype} - {payload}")
                except asyncio.TimeoutError:
                    print(f"  Timeout after {i} events")
                    break

asyncio.run(main())