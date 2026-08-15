"""
Task: Implement a Binary Search Tree with Common Operations

Write a Python class `BinarySearchTree` that supports:
- `insert(value)` - insert a value into the tree
- `search(value)` - return True if value exists in tree
- `delete(value)` - delete a value from the tree
- `min_value()` - return the minimum value in the tree
- `max_value()` - return the maximum value in the tree
- `inorder_traversal()` - return list of values in sorted order
- `height()` - return the height of the tree

Requirements:
1. Use a nested TreeNode class
2. Implement deletion with the standard 3-case algorithm
3. Handle edge cases: empty tree, deleting root, deleting leaf
4. Include type hints and docstrings
5. Add a main() function with demo usage
6. Write comprehensive test cases covering all methods
"""

from typing import Optional, List


class TreeNode:
    """A node in a binary search tree."""
    
    def __init__(self, value: int):
        self.value = value
        self.left: Optional['TreeNode'] = None
        self.right: Optional['TreeNode'] = None


class BinarySearchTree:
    """A binary search tree with insertion, deletion, and traversal."""
    
    def __init__(self):
        self.root: Optional[TreeNode] = None
    
    def insert(self, value: int) -> None:
        """Insert a value into the BST."""
        if self.root is None:
            self.root = TreeNode(value)
        else:
            self._insert_recursive(self.root, value)
    
    def _insert_recursive(self, node: TreeNode, value: int) -> None:
        """Helper to insert recursively."""
        if value < node.value:
            if node.left is None:
                node.left = TreeNode(value)
            else:
                self._insert_recursive(node.left, value)
        elif value > node.value:
            if node.right is None:
                node.right = TreeNode(value)
            else:
                self._insert_recursive(node.right, value)
    
    def search(self, value: int) -> bool:
        """Search for a value in the BST."""
        return self._search_recursive(self.root, value)
    
    def _search_recursive(self, node: Optional[TreeNode], value: int) -> bool:
        """Helper to search recursively."""
        if node is None:
            return False
        if value == node.value:
            return True
        elif value < node.value:
            return self._search_recursive(node.left, value)
        else:
            return self._search_recursive(node.right, value)
    
    def delete(self, value: int) -> bool:
        """Delete a value from the BST. Returns True if deleted."""
        self.root, deleted = self._delete_recursive(self.root, value)
        return deleted
    
    def _delete_recursive(self, node: Optional[TreeNode], value: int) -> tuple:
        """Helper to delete recursively. Returns (new_node, deleted)."""
        if node is None:
            return None, False
        
        if value < node.value:
            node.left, deleted = self._delete_recursive(node.left, value)
            return node, deleted
        elif value > node.value:
            node.right, deleted = self._delete_recursive(node.right, value)
            return node, deleted
        else:
            # Found the node to delete
            # Case 1: Leaf node (no children)
            if node.left is None and node.right is None:
                return None, True
            # Case 2: One child
            elif node.left is None:
                return node.right, True
            elif node.right is None:
                return node.left, True
            # Case 3: Two children - find in-order successor
            else:
                successor = self._min_value_node(node.right)
                node.value = successor.value
                node.right, _ = self._delete_recursive(node.right, successor.value)
                return node, True
    
    def min_value(self) -> Optional[int]:
        """Return the minimum value in the BST."""
        if self.root is None:
            return None
        current = self.root
        while current.left is not None:
            current = current.left
        return current.value
    
    def max_value(self) -> Optional[int]:
        """Return the maximum value in the BST."""
        if self.root is None:
            return None
        current = self.root
        while current.right is not None:
            current = current.right
        return current.value
    
    def inorder_traversal(self) -> List[int]:
        """Return values in sorted order using in-order traversal."""
        result = []
        self._inorder_recursive(self.root, result)
        return result
    
    def _inorder_recursive(self, node: Optional[TreeNode], result: List[int]) -> None:
        """Helper for in-order traversal."""
        if node:
            self._inorder_recursive(node.left, result)
            result.append(node.value)
            self._inorder_recursive(node.right, result)
    
    def height(self) -> int:
        """Return the height of the tree (0 for empty tree)."""
        return self._height_recursive(self.root)
    
    def _height_recursive(self, node: Optional[TreeNode]) -> int:
        """Helper to compute height recursively."""
        if node is None:
            return 0
        left_height = self._height_recursive(node.left)
        right_height = self._height_recursive(node.right)
        return 1 + max(left_height, right_height)


def main() -> None:
    """Demonstrate Binary Search Tree usage."""
    bst = BinarySearchTree()
    
    # Insert values
    values = [50, 30, 70, 20, 40, 60, 80]
    for v in values:
        bst.insert(v)
    
    print(f"Tree height: {bst.height()}")  # Should be 3
    print(f"In-order: {bst.inorder_traversal()}")  # [20, 30, 40, 50, 60, 70, 80]
    print(f"Min: {bst.min_value()}")  # 20
    print(f"Max: {bst.max_value()}")  # 80
    
    # Search
    print(f"Search 40: {bst.search(40)}")  # True
    print(f"Search 99: {bst.search(99)}")  # False
    
    # Delete a leaf
    bst.delete(20)
    print(f"After deleting 20: {bst.inorder_traversal()}")
    
    # Delete a node with one child
    bst.delete(30)
    print(f"After deleting 30: {bst.inorder_traversal()}")
    
    # Delete a node with two children
    bst.delete(70)
    print(f"After deleting 70: {bst.inorder_traversal()}")
    print(f"Final height: {bst.height()}")


if __name__ == "__main__":
    main()
