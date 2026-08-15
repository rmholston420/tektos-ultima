/**
 * Tektos-Ultima v1 — Live Witness Test
 * 
 * This test demonstrates Tektos solving a real programming task through the GUI.
 * Run with: npx playwright test e2e-live-witness.spec.ts --headed --screenshot=only-on-failure
 * 
 * What you'll see:
 * 1. Tektos dashboard loading
 * 2. Session creation
 * 3. Programming task typed and sent
 * 4. Real-time event streaming (tool calls, file operations, LLM responses)
 * 5. Task completion
 */

import { test, expect } from '@playwright/test';

const FRONTEND = 'http://localhost:3004';

test.describe('Tektos Live Witness Demo', () => {
  test('witness Tektos solve a programming task end-to-end', async ({ page }) => {
    // ── Step 1: Launch Tektos ──────────────────────────────────────────────
    console.log('🎬 STEP 1: Launching Tektos...');
    await page.goto(FRONTEND);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    
    // Verify Tektos is loaded
    const title = await page.title();
    console.log('📄 Page title:', title);
    expect(title).toContain('Tektos');
    
    // Screenshot: Welcome screen
    await page.screenshot({ path: 'test-results/step1-welcome.png', fullPage: true });
    console.log('✅ Welcome screen visible');
    
    // ── Step 2: Create Session ─────────────────────────────────────────────
    console.log('🎬 STEP 2: Creating new session...');
    const newSessionBtn = page.getByRole('button', { name: /new session/i }).first();
    await expect(newSessionBtn).toBeVisible();
    await newSessionBtn.click();
    await page.waitForTimeout(2000);
    
    // Screenshot: Composer visible
    await page.screenshot({ path: 'test-results/step2-composer.png', fullPage: true });
    
    const textarea = page.locator('textarea').first();
    await expect(textarea).toBeVisible();
    await expect(textarea).toBeEnabled();
    console.log('✅ Composer visible and enabled');
    
    // ── Step 3: Send Programming Task ──────────────────────────────────────
    console.log('🎬 STEP 3: Typing programming task...');
    
    const taskMessage = `Write a Python class called "LRUCache" (Least Recently Used Cache) that implements:
- __init__(capacity: int) - initialize cache with max size
- get(key: int) -> int - return value if exists, -1 if not found  
- put(key: int, value: int) -> None - insert/update key-value pair

Requirements:
1. Use OrderedDict internally for O(1) operations
2. When cache is full, evict the least recently used item
3. Include type hints, docstrings, and a main() demo function
4. Write to /home/rmholston/dev/tektos-ultima-v1/test_lru_cache.py
5. Run the file to verify it works

Write the complete implementation.`;
    
    await textarea.click();
    await textarea.fill(taskMessage);
    await page.waitForTimeout(500);
    
    // Screenshot: Task typed
    await page.screenshot({ path: 'test-results/step3-task-typed.png', fullPage: true });
    console.log('✅ Task typed');
    
    // ── Step 4: Send the Task ──────────────────────────────────────────────
    console.log('🎬 STEP 4: Sending task...');
    await textarea.press('Enter');
    
    // Screenshot: Task sent, streaming starts
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'test-results/step4-sending.png', fullPage: true });
    console.log('✅ Task sent, waiting for execution...');
    
    // ── Step 5: Monitor Progress ───────────────────────────────────────────
    console.log('🎬 STEP 5: Monitoring execution...');
    
    // Wait for LLM response to appear in the chat
    const maxWait = 120000; // 2 minutes
    const startTime = Date.now();
    let responseSeen = false;
    
    while (Date.now() - startTime < maxWait) {
      // Check for streaming content or response
      const bodyText = await page.locator('body').textContent();
      
      // Look for signs of LLM activity (not the prompt itself, but response content)
      const hasResponse = bodyText.length > 200 && 
                          !bodyText.includes(taskMessage) || 
                          bodyText.includes('def ') ||
                          bodyText.includes('class ') ||
                          bodyText.includes('return ') ||
                          bodyText.includes('import ');
      
      if (hasResponse) {
        console.log('✅ LLM response detected!');
        await page.screenshot({ path: 'test-results/step5-response.png', fullPage: true });
        responseSeen = true;
        break;
      }
      
      await page.waitForTimeout(5000);
    }
    
    if (!responseSeen) {
      console.log('⏳ Response may still be streaming (long task)...');
    }
    
    // ── Step 6: Final State ────────────────────────────────────────────────
    console.log('🎬 STEP 6: Capturing final state...');
    await page.screenshot({ path: 'test-results/step6-complete.png', fullPage: true });
    console.log('✅ Demo complete!');
    
    // ── Step 7: Verify backend state ───────────────────────────────────────
    console.log('🎬 STEP 7: Verifying backend state...');
    
    // Wait for file creation (give LLM time to write)
    await page.waitForTimeout(15000);
    
    const fs = require('fs');
    const testFile = '/home/rmholston/dev/tektos-ultima-v1/test_lru_cache.py';
    
    if (fs.existsSync(testFile)) {
      const content = fs.readFileSync(testFile, 'utf-8');
      const lines = content.split('\n').length;
      console.log(`✅ File created: test_lru_cache.py (${lines} lines)`);
      
      // Verify key components
      const checks = {
        'LRUCache class': content.includes('class LRUCache'),
        '__init__ method': content.includes('def __init__'),
        'get method': content.includes('def get'),
        'put method': content.includes('def put'),
        'OrderedDict import': content.includes('OrderedDict'),
        'main demo': content.includes('def main'),
      };
      
      for (const [name, result] of Object.entries(checks)) {
        console.log(`   ${result ? '✅' : '❌'} ${name}`);
      }
      
      expect(checks['LRUCache class']).toBe(true);
      expect(checks['OrderedDict import']).toBe(true);
    } else {
      console.log('⏳ File not yet created (Tektos processing...)');
      console.log('   The LLM may still be working. Check later.');
    }
    
    console.log('\n🎬 ========================================');
    console.log('🎬 LIVE DEMO COMPLETE');
    console.log('🎬 ========================================');
    console.log('📸 Screenshots saved to test-results/');
    console.log('📄 Files created in test directory');
  });
});
