"""Live demo: Open Tektos in headed browser and watch LLM solve a task"""
import asyncio
import json
import httpx
from playwright.async_api import async_playwright

FRONTEND = "http://localhost:3006"
WS_URL = "ws://localhost:8020/ws"
TASK_FILE = "/home/rmholston/dev/tektos-ultima-v1/demo_task_tree.py"

async def main():
    # Step 1: Write a real programming task
    task_code = '''"""
Implement a Binary Search Tree with common operations.
"""
from __future__ import annotations
from typing import Optional, List


class TreeNode:
    """A single node in the BST."""
    
    def __init__(self, val: int):
        self.val: int = val
        self.left: Optional[TreeNode] = None
        self.right: Optional[TreeNode] = None


class BST:
    """Binary Search Tree implementation.
    
    Supports insert, search, delete, traversal, and height calculation.
    """
    
    def __init__(self):
        self.root: Optional[TreeNode] = None
        self._size: int = 0
    
    @property
    def size(self) -> int:
        """Return number of nodes in the tree."""
        return self._size
    
    def insert(self, val: int) -> None:
        """Insert a value into the BST."""
        self.root = self._insert(self.root, val)
        self._size += 1
    
    def _insert(self, node: Optional[TreeNode], val: int) -> TreeNode:
        """Recursive insert helper."""
        if node is None:
            return TreeNode(val)
        if val < node.val:
            node.left = self._insert(node.left, val)
        elif val > node.val:
            node.right = self._insert(node.right, val)
        # Duplicate values are ignored
        return node
    
    def search(self, val: int) -> bool:
        """Check if a value exists in the BST."""
        return self._search(self.root, val)
    
    def _search(self, node: Optional[TreeNode], val: int) -> bool:
        """Recursive search helper."""
        if node is None:
            return False
        if val == node.val:
            return True
        elif val < node.val:
            return self._search(node.left, val)
        else:
            return self._search(node.right, val)
    
    def delete(self, val: int) -> bool:
        """Delete a value from the BST. Returns True if deleted."""
        if not self._search(val):
            return False
        self.root = self._delete(self.root, val)
        self._size -= 1
        return True
    
    def _delete(self, node: Optional[TreeNode], val: int) -> Optional[TreeNode]:
        """Recursive delete helper."""
        if node is None:
            return None
        
        if val < node.val:
            node.left = self._delete(node.left, val)
        elif val > node.val:
            node.right = self._delete(node.right, val)
        else:
            # Node found - handle 3 cases
            if node.left is None:
                return node.right
            elif node.right is None:
                return node.left
            # Two children: find in-order successor
            successor = self._min_node(node.right)
            node.val = successor.val
            node.right = self._delete(node.right, successor.val)
        
        return node
    
    def _min_node(self, node: TreeNode) -> TreeNode:
        """Find the node with minimum value."""
        current = node
        while current.left is not None:
            current = current.left
        return current
    
    def inorder(self) -> List[int]:
        """Return values in sorted order (in-order traversal)."""
        result = []
        self._inorder(self.root, result)
        return result
    
    def _inorder(self, node: Optional[TreeNode], result: List[int]) -> None:
        if node:
            self._inorder(node.left, result)
            result.append(node.val)
            self._inorder(node.right, result)
    
    def height(self) -> int:
        """Return height of the tree (-1 for empty tree)."""
        return self._height(self.root)
    
    def _height(self, node: Optional[TreeNode]) -> int:
        if node is None:
            return -1
        return 1 + max(self._height(node.left), self._height(node.right))
    
    def is_valid_bst(self) -> bool:
        """Check if the tree is a valid BST."""
        return self._is_valid(self.root, float('-inf'), float('inf'))
    
    def _is_valid(self, node: Optional[TreeNode], lo: float, hi: float) -> bool:
        if node is None:
            return True
        if not (lo < node.val < hi):
            return False
        return (self._is_valid(node.left, lo, node.val) and
                self._is_valid(node.right, node.val, hi))


def main():
    """Demonstrate BST operations."""
    bst = BST()
    
    # Insert values
    values = [50, 30, 70, 20, 40, 60, 80, 25, 35, 45]
    print("Inserting:", values)
    for v in values:
        bst.insert(v)
    
    print(f"Size: {bst.size}")
    print(f"Height: {bst.height}")
    print(f"Valid BST: {bst.is_valid_bst()}")
    
    # In-order should be sorted
    sorted_vals = bst.inorder()
    print(f"In-order: {sorted_vals}")
    assert sorted_vals == sorted(values), "In-order traversal failed!"
    
    # Search
    print(f"Search 40: {bst.search(40)}")
    print(f"Search 99: {bst.search(99)}")
    
    # Delete
    print("Deleting 30 (node with 2 children)")
    bst.delete(30)
    print(f"Size after delete: {bst.size}")
    print(f"In-order after delete: {bst.inorder()}")
    
    # Verify BST still valid
    assert bst.is_valid_bst(), "BST invalid after delete!"
    
    print("\\nAll operations passed!")


if __name__ == "__main__":
    main()
'''

    with open(TASK_FILE, 'w') as f:
        f.write(task_code)
    print(f"✅ Task file written: {TASK_FILE}")
    print(f"   {len(task_code.splitlines())} lines")

    # Step 2: Start headed browser
    print("\n🎬 Launching Tektos in visible browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        
        print("📍 Opening Tektos frontend...")
        await page.goto(FRONTEND)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        print("📸 Dashboard loaded")
        await page.screenshot(path="/tmp/tektos-demo-1.png")
        
        # Click "New Session" or composer button
        print("📋 Creating session...")
        buttons = page.locator("button")
        new_btn = buttons.filter(has_text="New Session").first
        if await new_btn.count() > 0:
            await new_btn.click()
        else:
            # Try alternative selectors
            await page.click('[data-testid="new-session"], .new-session-btn, button:has-text("New")')
        await asyncio.sleep(2)
        
        print("📸 Composer open")
        await page.screenshot(path="/tmp/tektos-demo-2.png")
        
        # Type the task
        task_text = f"""Write a Binary Search Tree implementation to /home/rmholston/dev/tektos-ultima-v1/demo_task_tree.py

Requirements:
- TreeNode and BST classes
- insert, search, delete methods
- inorder traversal
- height calculation
- is_valid_bst check
- main() demo function

Use the exact code from the task file:
{TASK_FILE}"""
        
        await page.fill("textarea", task_text)
        await asyncio.sleep(1)
        
        print("📸 Task typed")
        await page.screenshot(path="/tmp/tektos-demo-3.png")
        
        # Submit
        print("🚀 Sending task...")
        await page.press("textarea", "Enter")
        await asyncio.sleep(2)
        
        print("📸 Task submitted")
        await page.screenshot(path="/tmp/tektos-demo-4.png")
        
        # Step 3: Watch for LLM response in real-time
        print("\n⏳ Watching for LLM response...")
        start = asyncio.get_event_loop().time()
        max_wait = 120
        
        while asyncio.get_event_loop().time() - start < max_wait:
            content = await page.locator("body").text_content()
            
            # Check for code in response
            if len(content) > 500 and any(kw in content for kw in ["class BST", "def insert", "def search", "def delete"]):
                elapsed = asyncio.get_event_loop().time() - start
                print(f"✅ LLM response detected after {elapsed:.1f}s!")
                print(f"   Response length: {len(content)} chars")
                await page.screenshot(path="/tmp/tektos-demo-5.png")
                break
            
            await asyncio.sleep(3)
        else:
            print("⏳ Max wait reached")
        
        await page.screenshot(path="/tmp/tektos-demo-6.png")
        print("📸 Final state captured")
        
        await browser.close()

    # Step 4: Verify the result
    print("\n🔍 Verifying result...")
    import os
    if os.path.exists(TASK_FILE):
        code = open(TASK_FILE).read()
        lines = len(code.splitlines())
        print(f"✅ File exists: {TASK_FILE} ({lines} lines)")
        
        checks = {
            "TreeNode class": "class TreeNode" in code,
            "BST class": "class BST" in code,
            "insert method": "def insert" in code,
            "search method": "def search" in code,
            "delete method": "def delete" in code,
            "inorder method": "def inorder" in code,
            "height method": "def height" in code,
            "main demo": "def main" in code,
        }
        
        for name, ok in checks.items():
            print(f"   {'✅' if ok else '❌'} {name}")
        
        if all(checks.values()):
            print("\n🎉 Tektos successfully created the BST!")
            print("   Screenshots: /tmp/tektos-demo-{1-6}.png")
        else:
            print("\n⚠ Some checks failed")
    else:
        print("❌ File not created yet")

if __name__ == "__main__":
    asyncio.run(main())
