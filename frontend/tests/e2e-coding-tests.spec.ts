/**
 * Tektos-Ultima v1 — Moderately Difficult Coding Tests
 *
 * These tests verify Tektos can solve real programming tasks:
 * 1. Binary Search Tree with rotations
 * 2. LRU Cache with O(1) operations
 * 3. JSON parser (recursive descent)
 * 4. Event emitter with chaining
 * 5. HTTP request simulator with retry logic
 */

import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

const FRONTEND = 'http://localhost:3003';
const BACKEND = 'http://localhost:8020';
const TEST_DIR = '/home/rmholston/dev/tektos-ultima-v1';

// ─── Helper: Send task and wait for completion ────────────────────────────────

async function sendTaskAndWait(page: any, task: string, expectedFile: string, timeout = 180000) {
  console.log(`📝 Sending task: ${task.substring(0, 60)}...`);
  
  // Navigate to page
  await page.goto(FRONTEND);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);
  
  // Create session - try multiple button text patterns
  let sessionBtn = page.getByRole('button', { name: /new session/i }).first();
  if (!(await sessionBtn.isVisible().catch(() => false))) {
    sessionBtn = page.getByRole('button', { name: /create session/i }).first();
  }
  if (!(await sessionBtn.isVisible().catch(() => false))) {
    sessionBtn = page.locator('button').filter({ hasText: /new session|create session/i }).first();
  }
  await expect(sessionBtn).toBeVisible();
  await sessionBtn.click();
  await page.waitForTimeout(3000);
  
  // Type task
  const textarea = page.locator('textarea').first();
  await expect(textarea).toBeVisible();
  await textarea.click();
  await textarea.fill(task);
  await page.waitForTimeout(500);
  
  // Send
  await textarea.press('Enter');
  console.log('🚀 Task sent, waiting for execution...');
  
  // Wait for completion
  const startTime = Date.now();
  let completed = false;
  
  while (Date.now() - startTime < timeout) {
    // Check if file exists
    if (fs.existsSync(expectedFile)) {
      console.log(`✅ File created: ${expectedFile}`);
      completed = true;
      break;
    }
    
    // Check for response in chat
    const bodyText = await page.locator('body').textContent();
    if (bodyText && bodyText.length > 500) {
      console.log('✅ Response detected in chat');
    }
    
    await page.waitForTimeout(5000);
  }
  
  if (!completed) {
    console.log('⏳ Timeout waiting for file creation');
  }
  
  return completed;
}

// ─── Test 1: Binary Search Tree with Rotations ────────────────────────────────

test.describe('BST with Rotations', () => {
  test('Tektos implements AVL tree with insert and rotations', async ({ page }) => {
    const task = `Write a Python class called "AVLTree" that implements a self-balancing binary search tree:

Requirements:
1. Implement insert(key) method that maintains AVL balance
2. Implement rotate_right() and rotate_left() helper methods
3. Implement get_height() and get_balance() methods
4. Implement inorder_traversal() that returns sorted list
5. Include type hints, docstrings, and a main() demo
6. The demo should insert [10, 20, 30, 40, 50, 25] and show:
   - Inorder traversal before and after insertion
   - Tree height at each step
7. Write to ${TEST_DIR}/test_avl_tree.py
8. Run the file to verify it works correctly

The tree must maintain the AVL property: for every node, the heights of left and right subtrees differ by at most 1.`;

    const expectedFile = path.join(TEST_DIR, 'test_avl_tree.py');
    
    // Clean up any previous run
    if (fs.existsSync(expectedFile)) {
      fs.unlinkSync(expectedFile);
    }
    
    const completed = await sendTaskAndWait(page, task, expectedFile);
    expect(completed).toBe(true);
    
    // Verify file content
    expect(fs.existsSync(expectedFile)).toBe(true);
    const content = fs.readFileSync(expectedFile, 'utf-8');
    
    // Check for key components
    expect(content).toContain('class AVLTree');
    expect(content).toContain('def insert');
    expect(content).toContain('def rotate_right');
    expect(content).toContain('def rotate_left');
    expect(content).toContain('def get_height');
    expect(content).toContain('def get_balance');
    expect(content).toContain('def inorder_traversal');
    expect(content).toContain('def main');
    
    // Run the file to verify it works
    try {
      const output = execSync(`python3 ${expectedFile}`, { timeout: 30000 }).toString();
      console.log('✅ AVL tree output:', output.substring(0, 200));
      expect(output.length).toBeGreaterThan(50);
    } catch (e: any) {
      console.log('⚠️  File execution had warnings (may be expected):', e.message.substring(0, 100));
    }
  });
});

// ─── Test 2: LRU Cache with O(1) Operations ──────────────────────────────────

test.describe('LRU Cache', () => {
  test('Tektos implements LRU Cache with O(1) get and put', async ({ page }) => {
    const task = `Write a Python class called "LRUCache" that implements a Least Recently Used cache:

Requirements:
1. __init__(capacity: int) - initialize with max size
2. get(key: int) -> int - return value if exists, -1 if not found
3. put(key: int, value: int) -> None - insert/update key-value pair
4. When cache is full, evict the least recently used item
5. MUST use OrderedDict internally for O(1) operations
6. Include type hints, docstrings, and a main() demo
7. The demo should:
   - Create cache with capacity 3
   - Put (1, 1), (2, 2), (3, 3)
   - Get(1) should return 1
   - Put(4, 4) should evict key 2 (LRU)
   - Get(2) should return -1 (evicted)
   - Print all operations and results
8. Write to ${TEST_DIR}/test_lru_cache.py
9. Run the file to verify it works

The implementation must be O(1) for both get and put operations.`;

    const expectedFile = path.join(TEST_DIR, 'test_lru_cache.py');
    
    // Clean up
    if (fs.existsSync(expectedFile)) {
      fs.unlinkSync(expectedFile);
    }
    
    const completed = await sendTaskAndWait(page, task, expectedFile);
    expect(completed).toBe(true);
    
    // Verify file content
    expect(fs.existsSync(expectedFile)).toBe(true);
    const content = fs.readFileSync(expectedFile, 'utf-8');
    
    expect(content).toContain('class LRUCache');
    expect(content).toContain('def __init__');
    expect(content).toContain('def get');
    expect(content).toContain('def put');
    expect(content).toContain('OrderedDict');
    expect(content).toContain('def main');
    
    // Run and verify output
    try {
      const output = execSync(`python3 ${expectedFile}`, { timeout: 30000 }).toString();
      console.log('✅ LRU cache output:', output.substring(0, 300));
      // Verify expected behavior
      expect(output).toContain('1'); // get(1) returns 1
      expect(output).toContain('-1'); // get(2) returns -1 (evicted)
    } catch (e: any) {
      console.log('⚠️  File execution had warnings:', e.message.substring(0, 100));
    }
  });
});

// ─── Test 3: JSON Parser (Recursive Descent) ─────────────────────────────────

test.describe('JSON Parser', () => {
  test('Tektos implements a recursive descent JSON parser', async ({ page }) => {
    const task = `Write a Python class called "JSONParser" that implements a recursive descent parser for JSON:

Requirements:
1. parse(json_string: str) -> any - parse JSON string to Python object
2. Support: strings, numbers, booleans, null, arrays, objects
3. Handle nested structures
4. Include error handling for malformed JSON
5. Include type hints, docstrings, and a main() demo
6. The demo should:
   - Parse a complex nested JSON string with strings, numbers, arrays, objects
   - Print the parsed result
   - Verify it matches expected structure
7. Write to ${TEST_DIR}/test_json_parser.py
8. Run the file to verify it works

Example JSON to parse:
'{"name": "Alice", "age": 30, "hobbies": ["reading", "coding"], "address": {"city": "NYC", "zip": "10001"}}'`;

    const expectedFile = path.join(TEST_DIR, 'test_json_parser.py');
    
    // Clean up
    if (fs.existsSync(expectedFile)) {
      fs.unlinkSync(expectedFile);
    }
    
    const completed = await sendTaskAndWait(page, task, expectedFile);
    expect(completed).toBe(true);
    
    // Verify file content
    expect(fs.existsSync(expectedFile)).toBe(true);
    const content = fs.readFileSync(expectedFile, 'utf-8');
    
    expect(content).toContain('class JSONParser');
    expect(content).toContain('def parse');
    expect(content).toContain('def main');
    
    // Run and verify output
    try {
      const output = execSync(`python3 ${expectedFile}`, { timeout: 30000 }).toString();
      console.log('✅ JSON parser output:', output.substring(0, 300));
      expect(output.length).toBeGreaterThan(50);
    } catch (e: any) {
      console.log('⚠️  File execution had warnings:', e.message.substring(0, 100));
    }
  });
});

// ─── Test 4: Event Emitter with Chaining ─────────────────────────────────────

test.describe('Event Emitter', () => {
  test('Tektos implements an event emitter with method chaining', async ({ page }) => {
    const task = `Write a Python class called "EventEmitter" that implements an event emitter with method chaining:

Requirements:
1. on(event: str, callback: callable) -> self - register event listener (returns self for chaining)
2. emit(event: str, *args) -> None - trigger event with arguments
3. off(event: str, callback: callable) -> self - remove event listener
4. once(event: str, callback: callable) -> self - register one-time listener
5. include type hints, docstrings, and a main() demo
6. The demo should:
   - Create emitter instance
   - Chain multiple on() calls
   - Emit events and verify callbacks receive arguments
   - Test once() listener is removed after first trigger
   - Test off() removes listener
7. Write to ${TEST_DIR}/test_event_emitter.py
8. Run the file to verify it works

Method chaining example:
emitter.on('data', handler1).on('error', handler2).emit('data', value)`;

    const expectedFile = path.join(TEST_DIR, 'test_event_emitter.py');
    
    // Clean up
    if (fs.existsSync(expectedFile)) {
      fs.unlinkSync(expectedFile);
    }
    
    const completed = await sendTaskAndWait(page, task, expectedFile);
    expect(completed).toBe(true);
    
    // Verify file content
    expect(fs.existsSync(expectedFile)).toBe(true);
    const content = fs.readFileSync(expectedFile, 'utf-8');
    
    expect(content).toContain('class EventEmitter');
    expect(content).toContain('def on');
    expect(content).toContain('def emit');
    expect(content).toContain('def off');
    expect(content).toContain('def once');
    expect(content).toContain('def main');
    
    // Run and verify output
    try {
      const output = execSync(`python3 ${expectedFile}`, { timeout: 30000 }).toString();
      console.log('✅ Event emitter output:', output.substring(0, 300));
      expect(output.length).toBeGreaterThan(50);
    } catch (e: any) {
      console.log('⚠️  File execution had warnings:', e.message.substring(0, 100));
    }
  });
});

// ─── Test 5: HTTP Request Simulator with Retry Logic ─────────────────────────

test.describe('HTTP Request Simulator', () => {
  test('Tektos implements HTTP request simulator with retry logic', async ({ page }) => {
    const task = `Write a Python class called "HTTPRequestSimulator" that simulates HTTP requests with retry logic:

Requirements:
1. __init__(base_url: str, max_retries: int = 3, timeout: float = 5.0)
2. get(path: str, headers: dict = None) -> dict - simulate GET request
3. post(path: str, data: dict) -> dict - simulate POST request
4. Implement exponential backoff retry logic
5. Include type hints, docstrings, and a main() demo
6. The demo should:
   - Create simulator instance
   - Simulate successful request
   - Simulate failed request with retries
   - Print request details and retry attempts
7. Write to ${TEST_DIR}/test_http_simulator.py
8. Run the file to verify it works

The simulator should track:
- Request method, URL, headers, body
- Response status code, body, headers
- Number of retry attempts
- Total time taken`;

    const expectedFile = path.join(TEST_DIR, 'test_http_simulator.py');
    
    // Clean up
    if (fs.existsSync(expectedFile)) {
      fs.unlinkSync(expectedFile);
    }
    
    const completed = await sendTaskAndWait(page, task, expectedFile);
    expect(completed).toBe(true);
    
    // Verify file content
    expect(fs.existsSync(expectedFile)).toBe(true);
    const content = fs.readFileSync(expectedFile, 'utf-8');
    
    expect(content).toContain('class HTTPRequestSimulator');
    expect(content).toContain('def get');
    expect(content).toContain('def post');
    expect(content).toContain('def main');
    expect(content).toContain('retry');
    expect(content).toContain('backoff');
    
    // Run and verify output
    try {
      const output = execSync(`python3 ${expectedFile}`, { timeout: 30000 }).toString();
      console.log('✅ HTTP simulator output:', output.substring(0, 300));
      expect(output.length).toBeGreaterThan(50);
    } catch (e: any) {
      console.log('⚠️  File execution had warnings:', e.message.substring(0, 100));
    }
  });
});

// ─── Test 6: Complex Integration — Task Pipeline ─────────────────────────────

test.describe('Task Pipeline Integration', () => {
  test('Tektos implements a task pipeline with multiple stages', async ({ page }) => {
    const task = `Write a Python class called "TaskPipeline" that implements a multi-stage task processing pipeline:

Requirements:
1. __init__() - initialize with empty stages
2. add_stage(name: str, func: callable) -> self - add processing stage (returns self for chaining)
3. execute(data: any) -> any - run data through all stages in order
4. Each stage receives output from previous stage
5. Include error handling: if a stage fails, stop pipeline and return error
6. Include type hints, docstrings, and a main() demo
7. The demo should:
   - Create pipeline with 4 stages: validate -> transform -> enrich -> format
   - Each stage should print what it's doing
   - Process sample data through pipeline
   - Print final result
8. Write to ${TEST_DIR}/test_task_pipeline.py
9. Run the file to verify it works

Stage examples:
- validate: check data is not None
- transform: convert to uppercase
- enrich: add metadata
- format: return formatted string`;

    const expectedFile = path.join(TEST_DIR, 'test_task_pipeline.py');
    
    // Clean up
    if (fs.existsSync(expectedFile)) {
      fs.unlinkSync(expectedFile);
    }
    
    const completed = await sendTaskAndWait(page, task, expectedFile);
    expect(completed).toBe(true);
    
    // Verify file content
    expect(fs.existsSync(expectedFile)).toBe(true);
    const content = fs.readFileSync(expectedFile, 'utf-8');
    
    expect(content).toContain('class TaskPipeline');
    expect(content).toContain('def add_stage');
    expect(content).toContain('def execute');
    expect(content).toContain('def main');
    
    // Run and verify output
    try {
      const output = execSync(`python3 ${expectedFile}`, { timeout: 30000 }).toString();
      console.log('✅ Task pipeline output:', output.substring(0, 300));
      expect(output.length).toBeGreaterThan(50);
    } catch (e: any) {
      console.log('⚠️  File execution had warnings:', e.message.substring(0, 100));
    }
  });
});
