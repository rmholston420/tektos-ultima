"""
Tektos Live Witness - Playwright with Chromium
Actually drives the Tektos GUI and shows you the LLM working live.
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright


FRONTEND = "http://localhost:3006"
VIDEO_PATH = "/home/rmholston/dev/tektos-ultima-v1/test-results/tektos-live-demo-2.mp4"


async def main():
    print("=" * 60)
    print("TEKTOS LIVE WITNESS - CHROMIUM GUI")
    print("=" * 60)
    
    # Check frontend
    print("\n📋 Checking Tektos...")
    try:
        import httpx
        resp = httpx.get(f"{FRONTEND}/", timeout=5)
        print(f"✅ Tektos frontend running: {resp.status_code}")
    except Exception as e:
        print(f"❌ Tektos frontend not running: {e}")
        print(f"   Start: cd frontend && PORT=3005 npm start")
        sys.exit(1)
    
    # Launch headed Chromium
    print(f"\n🎬 Launching Chromium (headed)...")
    print(f"   You'll see Tektos running on your screen")
    print(f"   Video saved to: {VIDEO_PATH}")
    
    async with async_playwright() as p:
        # Use CHROMIUM (not Firefox)
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=200,  # Slow down for visibility
        )
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            record_video_dir=Path(VIDEO_PATH).parent,
        )
        
        page = await context.new_page()
        
        # Step 1: Navigate to Tektos
        print(f"\n📍 Step 1: Opening {FRONTEND}")
        await page.goto(FRONTEND)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        await page.screenshot(path="/home/rmholston/dev/tektos-ultima-v1/test-results/s1-dashboard.png")
        print("✅ Dashboard loaded")
        
        # Step 2: Create session
        print("\n📋 Step 2: Creating session via GUI")
        btn = page.locator("button").filter(has_text="New Session").first
        await btn.click()
        await asyncio.sleep(2)
        
        await page.screenshot(path="/home/rmholston/dev/tektos-ultima-v1/test-results/s2-composer.png")
        print("✅ Composer open")
        
        # Step 3: Type task
        print("\n📋 Step 3: Typing task")
        task = """Write a Python class LRUCache:
- __init__(capacity) - init with OrderedDict
- get(key) -> int - return value or -1
- put(key, value) -> None - insert, evict LRU if full
- main() demo function

Write to /home/rmholston/dev/tektos-ultima-v1/demo_lru_cache2.py"""
        
        textarea = page.locator("textarea").first
        await textarea.click()
        await textarea.fill(task)
        await asyncio.sleep(1)
        
        await page.screenshot(path="/home/rmholston/dev/tektos-ultima-v1/test-results/s3-typed.png")
        print("✅ Task typed")
        
        # Step 4: Send
        print("\n📋 Step 4: Sending task")
        await textarea.press("Enter")
        await asyncio.sleep(3)
        
        await page.screenshot(path="/home/rmholston/dev/tektos-ultima-v1/test-results/s4-sent.png")
        print("✅ Task sent")
        
        # Step 5: Watch for LLM response
        print("\n📋 Step 5: Watching for LLM response...")
        start = asyncio.get_event_loop().time()
        max_wait = 180  # 3 minutes
        
        while asyncio.get_event_loop().time() - start < max_wait:
            body_text = await page.locator("body").text_content()
            
            # Check for code/content in response
            if len(body_text) > 300 and any(w in body_text for w in ["def ", "class ", "return", "import", "print"]):
                elapsed = asyncio.get_event_loop().time() - start
                print(f"✅ LLM response detected after {elapsed:.1f}s!")
                print(f"   Response length: {len(body_text)} chars")
                
                await page.screenshot(path="/home/rmholston/dev/tektos-ultima-v1/test-results/s5-response.png")
                print("✅ Response captured")
                break
            
            await asyncio.sleep(3)
        else:
            print("⏳ Max wait reached")
            # Check what we actually have
            body_text = await page.locator("body").text_content()
            print(f"   Current page content: {len(body_text)} chars")
        
        # Step 6: Final
        print("\n📋 Step 6: Final state")
        await asyncio.sleep(2)
        await page.screenshot(path="/home/rmholston/dev/tektos-ultima-v1/test-results/s6-final.png")
        print("✅ Final screenshot saved")
        
        await context.close()
        await browser.close()
    
    # Verify result
    print("\n📋 Verifying result...")
    test_file = Path("/home/rmholston/dev/tektos-ultima-v1/demo_lru_cache2.py")
    if test_file.exists():
        content = test_file.read_text()
        lines = len(content.split('\n'))
        print(f"✅ File created: demo_lru_cache2.py ({lines} lines)")
        
        checks = {
            "LRUCache class": "class LRUCache" in content,
            "OrderedDict": "OrderedDict" in content,
            "get method": "def get" in content,
            "put method": "def put" in content,
            "main demo": "def main" in content,
        }
        
        for name, ok in checks.items():
            print(f"   {'✅' if ok else '❌'} {name}")
        
        if all(checks.values()):
            print("\n🎉 Tektos successfully solved the task!")
    else:
        print("⏳ File not yet created")
    
    print("\n" + "=" * 60)
    print("WITNESS DEMO COMPLETE")
    print("Screenshots: test-results/s{1-6}*.png")
    print("Video:", VIDEO_PATH)
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
