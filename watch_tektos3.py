#!/usr/bin/env python3
"""Live demo: Open Tektos in headed browser and watch LLM solve a task"""
import asyncio
import os
from pathlib import Path

TEKTOS_URL = "http://localhost:3006"
OUTPUT_FILE = "/home/rmholston/dev/tektos-ultima-v1/demo_bst.py"

from playwright.async_api import async_playwright


async def main():
    print("=" * 70)
    print("👁️  WATCHING TEKTOS WORK - LIVE BROWSER DEMO")
    print("=" * 70)
    print()
    print("A browser will open showing Tektos solving a programming task.")
    print("Watch as the LLM writes code in real-time!")
    print()

    async with async_playwright() as p:
        print("🚀 Launching Chromium (you'll see it on screen)...")
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=100,
            args=["--window-size=1280,900", "--start-maximized"]
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = await context.new_page()

        # Navigate to Tektos
        print(f"\n📍 Opening {TEKTOS_URL}...")
        await page.goto(TEKTOS_URL)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        await page.screenshot(path="/tmp/tektos-demo-step1.png")
        print("✅ Tektos loaded - you're seeing it now!")
        print()

        # Step 1: Create a new session
        print("📋 Creating new session...")
        btn = page.locator("button").filter(has_text="New Session").first
        await btn.click()
        await asyncio.sleep(2)

        await page.screenshot(path="/tmp/tektos-demo-step2.png")
        print("✅ Session created")
        print()

        # Step 2: Type task using JavaScript - also trigger React state
        task = (
            "Write a Binary Search Tree implementation to "
            "/home/rmholston/dev/tektos-ultima-v1/demo_bst.py\n\n"
            "Requirements:\n"
            "- TreeNode and BST classes\n"
            "- Methods: insert, search, delete, inorder traversal, height\n"
            "- is_valid_bst method\n"
            "- main() demonstration function"
        )

        print("📝 Typing task...")
        # Use Playwright's fill() which works with React controlled components
        textarea = page.locator("textarea").first
        await textarea.fill(task)
        await asyncio.sleep(2)
        
        # Verify the textarea actually has the value
        textarea_val = await page.evaluate("""
            () => {
                const ta = document.querySelector('textarea');
                return ta ? ta.value.length : 0;
            }
        """)
        print(f"   Textarea value length: {textarea_val} chars")
        if textarea_val == 0:
            print("   WARNING: Value not set in textarea!")

        await page.screenshot(path="/tmp/tektos-demo-step3.png")
        print("✅ Task typed")
        print()

        # Step 3: Submit by clicking the send button
        print("🚀 Sending task to Tektos...")
        send_btn = page.locator("button[title='Send message']").first
        if await send_btn.count() > 0:
            await send_btn.click()
        else:
            await page.keyboard.press("Enter")
        await asyncio.sleep(3)

        await page.screenshot(path="/tmp/tektos-demo-step4.png")
        print("✅ Task submitted - watching for LLM response...")
        print()

        # Step 4: Watch for LLM response in real-time
        print("⏳ Monitoring LLM output...")
        print("-" * 70)
        start_time = asyncio.get_event_loop().time()
        max_wait = 180  # 3 minutes

        last_text_length = 0
        while asyncio.get_event_loop().time() - start_time < max_wait:
            body_text = await page.locator("body").text_content()

            if len(body_text) > 300:
                elapsed = asyncio.get_event_loop().time() - start_time
                growth = len(body_text) - last_text_length

                if growth > 0 or len(body_text) > 500:
                    print(
                        f"⏱️  {elapsed:.1f}s | 📝 {len(body_text)} chars"
                        + (f" (+{growth})" if growth > 0 else "")
                    )

                    if elapsed % 15 < 3:
                        await page.screenshot(
                            path=f"/tmp/tektos-demo-work-{int(elapsed)}.png"
                        )

                    last_text_length = len(body_text)

                if any(
                    kw in body_text for kw in ["def insert", "class BST", "class TreeNode"]
                ):
                    print(f"✅ CODE DETECTED at {elapsed:.1f}s!")
                    await page.screenshot(path="/tmp/tektos-demo-step5.png")

            await asyncio.sleep(2)
        else:
            print("⏰ Max wait reached")

        print("-" * 70)
        print()

        # Final state
        print("📊 Final state:")
        await page.screenshot(path="/tmp/tektos-demo-final.png")
        print("   Screenshots saved to /tmp/tektos-demo-step*.png")
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
    print(f"  Browser screenshots: /tmp/tektos-demo-step*.png")
    print(f"  Work progress: /tmp/tektos-demo-work-*.png")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
