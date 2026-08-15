#!/usr/bin/env python3
"""Watch Tektos solve a programming task LIVE in a visible browser"""
import asyncio
import os
import sys
from pathlib import Path

# Add project venv to path
sys.path.insert(0, str(Path(__file__).parent / '.venv' / 'lib' / 'python3.14' / 'site-packages'))

from playwright.async_api import async_playwright

TEKTOS_URL = "http://localhost:3006"
OUTPUT_FILE = str(Path(__file__).parent / "demo_bst.py")


async def main():
    print("=" * 70)
    print("👁️  WATCHING TEKTOS WORK - LIVE BROWSER DEMO")
    print("=" * 70)
    print()
    print("A browser will open showing Tektos solving a programming task.")
    print("Watch as the LLM writes code in real-time!")
    print()

    # Launch headed Chromium - USER CAN SEE THIS
    async with async_playwright() as p:
        print("🚀 Launching Chromium (you'll see it on screen)...")
        browser = await p.chromium.launch(
            headless=False,  # VISIBLE WINDOW
            slow_mo=150,     # Slightly slower for visibility
            args=['--window-size=1280,900', '--start-maximized']
        )
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale='en-US',
        )
        page = await context.new_page()
        
        # Navigate to Tektos
        print(f"\n📍 Opening {TEKTOS_URL}...")
        await page.goto(TEKTOS_URL)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        # Screenshot of initial state
        await page.screenshot(path="/tmp/tektos-step1.png")
        print("✅ Tektos loaded - you're seeing it now!")
        print()
        
        # Find and click "New Session" button
        print("📋 Creating new session...")
        try:
            # Try multiple selectors for "New Session"
            for selector in [
                'button:has-text("New Session")',
                'button:has-text("New")',
                '[data-testid="new-session"]',
                '.new-session',
            ]:
                btn = page.locator(selector).first
                if await btn.count() > 0:
                    await btn.click()
                    print(f"   Clicked: {selector}")
                    break
            else:
                print("   ⚠️  Could not find session button - showing page")
        except Exception as e:
            print(f"   Note: {e}")
        
        await asyncio.sleep(2)
        await page.screenshot(path="/tmp/tektos-step2.png")
        print("✅ Session created")
        print()
        
        # Type a real programming task
        task = """Write a Binary Search Tree implementation to /home/rmholston/dev/tektos-ultima-v1/demo_bst.py

Requirements:
- TreeNode and BST classes
- Methods: insert, search, delete, inorder traversal, height
- is_valid_bst method
- main() demonstration function"""

        print("📝 Typing task...")
        # Use role="textbox" to find the input (Composer uses ARIA role)
        await page.click('[role="textbox"]')
        await page.fill('[role="textbox"]', task)
        await asyncio.sleep(1)
        
        await page.screenshot(path="/tmp/tektos-step3.png")
        print("✅ Task typed - ready to send")
        print()
        
        # Submit the task
        print("🚀 Sending task to Tektos...")
        try:
            await page.press("textarea", "Enter")
        except:
            # If Enter doesn't work, try clicking a send button
            send_btn = page.locator('button:has-text("Send"), button[type="submit"]').first
            if await send_btn.count() > 0:
                await send_btn.click()
        await asyncio.sleep(3)
        
        await page.screenshot(path="/tmp/tektos-step4.png")
        print("✅ Task submitted - watching for LLM response...")
        print()
        
        # Watch for LLM response in real-time
        print("⏳ Monitoring LLM output...")
        print("-" * 70)
        start_time = asyncio.get_event_loop().time()
        max_wait = 180  # 3 minutes
        
        last_text_length = 0
        while asyncio.get_event_loop().time() - start_time < max_wait:
            body_text = await page.locator("body").text_content()
            
            # Check if text grew (LLM is working)
            if len(body_text) > 300:  # Substantial content detected
                elapsed = asyncio.get_event_loop().time() - start_time
                growth = len(body_text) - last_text_length
                
                if growth > 0 or len(body_text) > 500:
                    print(f"⏱️  {elapsed:.1f}s | 📝 {len(body_text)} chars" + 
                          (f" (+{growth})" if growth > 0 else ""))
                    
                    # Take periodic screenshots
                    if elapsed % 15 < 3:
                        await page.screenshot(path=f"/tmp/tektos-work-{int(elapsed)}.png")
                    
                    last_text_length = len(body_text)
                
                # Check for code patterns
                if any(kw in body_text for kw in ["def insert", "class BST", "class TreeNode"]):
                    print(f"✅ CODE DETECTED at {elapsed:.1f}s!")
                    await page.screenshot(path="/tmp/tektos-step5.png")
            
            await asyncio.sleep(2)
        else:
            print("⏰ Max wait reached")
        
        print("-" * 70)
        print()
        
        # Final state
        print("📊 Final state:")
        await page.screenshot(path="/tmp/tektos-final.png")
        print("   Screenshots saved to /tmp/tektos-step{1-6}.png")
        print()
        
        await browser.close()
    
    # Verify the result
    print("🔍 Verifying result...")
    print("-" * 70)
    output_path = Path(OUTPUT_FILE)
    
    if output_path.exists():
        code = output_path.read_text()
        lines = len(code.splitlines())
        print(f"✅ FILE CREATED: {OUTPUT_FILE}")
        print(f"   {lines} lines of code")
        print()
        
        # Check key components
        checks = {
            "TreeNode class": "class TreeNode" in code,
            "BST class": "class BST" in code,
            "insert method": "def insert" in code,
            "search method": "def search" in code,
            "delete method": "def delete" in code,
            "inorder traversal": "def inorder" in code,
            "height method": "def height" in code,
            "is_valid_bst": "is_valid_bst" in code,
            "main demo": "def main" in code,
        }
        
        for name, passed in checks.items():
            icon = "✅" if passed else "❌"
            print(f"   {icon} {name}")
        
        print()
        if all(checks.values()):
            print("🎉 SUCCESS! Tektos wrote a complete BST implementation!")
        else:
            print("⚠️  Partial success - some components missing")
    else:
        print(f"❌ Output file not found at {OUTPUT_FILE}")
    
    print()
    print("=" * 70)
    print("DEMO COMPLETE")
    print(f"  Browser screenshots: /tmp/tektos-step*.png")
    print(f"  Work progress: /tmp/tektos-work-*.png")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
