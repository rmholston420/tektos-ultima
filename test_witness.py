"""
Tektos Live Witness - Playwright Programmatic Demo
Launches headed Playwright, navigates to Tektos, sends a programming task,
and records video of the entire flow.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from playwright.async_api import async_playwright


FRONTEND = "http://localhost:3005"
BACKEND = "http://localhost:8020"
VIDEO_PATH = "/home/rmholston/dev/tektos-ultima-v1/test-results/tektos-live-demo.mp4"


async def main():
    print("=" * 60)
    print("TEKTOS LIVE WITNESS DEMO")
    print("=" * 60)
    
    # Verify Tektos frontend is running
    print("\n📋 Checking Tektos frontend...")
    try:
        import httpx
        resp = httpx.get(f"{FRONTEND}/", timeout=5)
        print(f"✅ Tektos frontend running: {resp.status_code}")
    except Exception as e:
        print(f"❌ Tektos frontend not available: {e}")
        print(f"   Tektos is running on {FRONTEND}")
        print(f"   Start it with: cd frontend && PORT=3005 npm start")
        sys.exit(1)
    
    # Launch Playwright headed
    print(f"\n🎬 Launching headed browser (you will see this)...")
    print(f"   Video will be saved to: {VIDEO_PATH}")
    
    async with async_playwright() as p:
        # Launch headed Chromium
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=300,  # Slow down for visibility
        )
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            record_video_dir=Path(VIDEO_PATH).parent,
        )
        
        page = await context.new_page()
        
        # Navigate to Tektos
        print(f"\n📍 Navigating to {FRONTEND}...")
        await page.goto(FRONTEND)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        # Take screenshot of dashboard
        await page.screenshot(path="/home/rmholston/dev/tektos-ultima-v1/test-results/step1-dashboard.png")
        print("✅ Dashboard visible - Screenshot 1/5")
        
        # Find and click "New Session" button
        print("\n✨ Creating new session...")
        new_session_btn = page.locator("button").filter(has_text="New Session").first
        try:
            await new_session_btn.click()
            print("✅ New Session button clicked")
        except Exception as e:
            print(f"⚠️  Could not find 'New Session' button: {e}")
            print("   Screenshot for debugging:")
            await page.screenshot(path="/home/rmholston/dev/tektos-ultima-v1/test-results/debug-buttons.png")
            await context.close()
            await browser.close()
            sys.exit(1)
        
        await asyncio.sleep(2)
        await page.screenshot(path="/home/rmholston/dev/tektos-ultima-v1/test-results/step2-composer.png")
        print("✅ Composer visible - Screenshot 2/5")
        
        # Find textarea and type task
        print("\n⌨️  Typing programming task...")
        task_text = """Write a Python class called "LRUCache" that implements:
- __init__(capacity: int) - initialize cache with max size
- get(key: int) -> int - return value if exists, -1 if not
- put(key: int, value: int) -> None - insert/update, evict LRU if full

Use OrderedDict internally for O(1) operations.
Include type hints, docstrings, and a main() demo function.
Write to /home/rmholston/dev/tektos-ultima-v1/demo_lru_cache.py
Then run it to verify it works."""
        
        textarea = page.locator("textarea").first
        await textarea.click()
        await textarea.fill(task_text)
        await asyncio.sleep(1)
        await page.screenshot(path="/home/rmholston/dev/tektos-ultima-v1/test-results/step3-task-typed.png")
        print("✅ Task typed - Screenshot 3/5")
        
        # Send the task
        print("\n🚀 Sending task...")
        await textarea.press("Enter")
        await asyncio.sleep(3)
        await page.screenshot(path="/home/rmholston/dev/tektos-ultima-v1/test-results/step4-sending.png")
        print("✅ Task sent - Screenshot 4/5")
        
        # Wait for response streaming
        print("\n⏳ Waiting for Tektos to respond...")
        start_time = asyncio.get_event_loop().time()
        max_wait = 120  # seconds
        
        while asyncio.get_event_loop().time() - start_time < max_wait:
            body_text = await page.locator("body").text_content()
            
            # Check for signs of LLM response (code, tool calls, etc.)
            if any(marker in body_text for marker in ["def ", "class ", "return ", "import ", "print("]):
                print(f"✅ LLM response detected after {asyncio.get_event_loop().time() - start_time:.1f}s!")
                await page.screenshot(path="/home/rmholston/dev/tektos-ultima-v1/test-results/step5-response.png")
                break
            
            await asyncio.sleep(2)
        else:
            print("⏳ Max wait reached - Tektos may still be processing")
        
        # Final screenshot
        await asyncio.sleep(2)
        await page.screenshot(path="/home/rmholston/dev/tektos-ultima-v1/test-results/step6-complete.png")
        print("✅ Final screenshot - Screenshot 5/5")
        
        # Close browser
        await context.close()
        await browser.close()
    
    print(f"\n🎬 Demo complete!")
    print(f"📸 Screenshots saved to test-results/")
    print(f"🎥 Video saved to: {VIDEO_PATH}")
    
    # Verify file was created by Tektos
    print("\n📋 Verifying Tektos execution...")
    test_file = Path("/home/rmholston/dev/tektos-ultima-v1/demo_lru_cache.py")
    if test_file.exists():
        content = test_file.read_text()
        lines = len(content.split('\n'))
        print(f"✅ File created: {lines} lines")
        
        checks = {
            "LRUCache class": "class LRUCache" in content,
            "__init__": "def __init__" in content,
            "get method": "def get" in content,
            "put method": "def put" in content,
            "OrderedDict": "OrderedDict" in content,
            "main demo": "def main" in content,
        }
        
        for name, ok in checks.items():
            print(f"   {'✅' if ok else '❌'} {name}")
        
        if all(checks.values()):
            print("\n🎉 SUCCESS! Tektos completed the task!")
    else:
        print("⏳ File not yet created - Tektos may still be processing")
    
    print("\n" + "=" * 60)
    print("WITNESS DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
