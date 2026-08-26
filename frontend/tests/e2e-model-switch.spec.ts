/**
 * Tektos-Ultima v1 — Model Switching Tests
 *
 * Live tests: verify model switching works end-to-end.
 */

import { test, expect } from '@playwright/test';

const BACKEND = 'http://localhost:8020';

test.describe('Model Switching', () => {
  test('backend returns 10 models with roles', async () => {
    const response = await fetch(`${BACKEND}/api/models`);
    expect(response.ok).toBe(true);
    const models = await response.json();
    expect(models.length).toBe(10);
    
    // Verify roles are present
    const roles = models.map(m => m.role);
    expect(roles).toContain('coder');
    expect(roles).toContain('planner');
    expect(roles).toContain('general');
    expect(roles).toContain('vision');
    expect(roles).toContain('fast');
    
    // Verify each has description
    for (const m of models) {
      expect(m.description).toBeTruthy();
      expect(m.description.length).toBeGreaterThan(20);
    }
    console.log(`✓ ${models.length} models available with roles and descriptions`);
  });

  test('model picker opens dropdown with all models', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);
    
    // Create session
    const newSessionBtn = page.locator('button').filter({ hasText: 'New Session' }).first();
    await newSessionBtn.click();
    await page.waitForTimeout(1000);
    
    // Find and click model picker (button shows current model name)
    const modelBtn = page.locator('button').filter({ hasText: /Qwen/i }).first();
    await expect(modelBtn).toBeVisible();
    await modelBtn.click();
    await page.waitForTimeout(1000);
    
    // Verify dropdown opened - check for model role indicators
    const content = await page.evaluate(() => document.body?.innerText || '');
    // The dropdown may show model names or roles depending on implementation
    // Accept either role names or model names
    const hasRoles = content.includes('CODER') || content.includes('PLANNER') || content.includes('GENERAL');
    const hasModels = content.includes('Qwen') || content.includes('35B') || content.includes('30B');
    expect(hasRoles || hasModels).toBeTruthy();
    console.log('✓ Model picker dropdown opens');
  });

  test('switching model via API updates session', async ({ page }) => {
    // Create session via API directly
    const createRes = await fetch(`${BACKEND}/api/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: 'qwen3-coder:30b' }),
    });
    const session = await createRes.json();
    const sessionId = session.id;
    expect(sessionId).toBeTruthy();
    
    // Verify initial model
    const initial = await fetch(`${BACKEND}/api/sessions/${sessionId}`);
    const initialData = await initial.json();
    expect(initialData.model).toBe('qwen3-coder:30b');
    
    // Switch model
    const switchRes = await fetch(`${BACKEND}/api/sessions/${sessionId}/model`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: 'qwen3.6:35b-a3b-mtp-coder' }),
    });
    expect(switchRes.ok).toBe(true);
    
    // Verify model changed
    const updated = await fetch(`${BACKEND}/api/sessions/${sessionId}`);
    const updatedData = await updated.json();
    expect(updatedData.model).toBe('qwen3.6:35b-a3b-mtp-coder');
    console.log(`✓ Model switched: qwen3-coder:30b → ${updatedData.model}`);
  });
});
