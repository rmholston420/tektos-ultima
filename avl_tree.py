"""Concise AVL Tree implementation in Python."""


class AVLNode:
    """Node for AVL tree storing key-value pairs."""

    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.left = None
        self.right = None
        self.height = 1


class AVLTree:
    """Self-balancing Binary Search Tree."""

    def _height(self, node):
        return node.height if node else 0

    def _update(self, node):
        node.height = 1 + max(self._height(node.left), self._height(node.right))

    def balance_factor(self, node):
        """Return balance factor (left height - right height)."""
        return self._height(node.left) - self._height(node.right)

    def _right_rotate(self, y):
        x = y.left
        t2 = x.right
        x.right = y
        y.left = t2
        self._update(y)
        self._update(x)
        return x

    def _left_rotate(self, x):
        y = x.right
        t2 = y.left
        y.left = x
        x.right = t2
        self._update(x)
        self._update(y)
        return y

    def insert(self, key, value):
        """Insert a key-value pair into the AVL tree."""
        def _insert(node):
            if not node:
                return AVLNode(key, value)
            if key < node.key:
                node.left = _insert(node.left)
            elif key > node.key:
                node.right = _insert(node.right)
            else:
                node.value = value
                return node
            self._update(node)
            bf = self.balance_factor(node)
            # Left Left
            if bf > 1 and key < node.left.key:
                return self._right_rotate(node)
            # Right Right
            if bf < -1 and key > node.right.key:
                return self._left_rotate(node)
            # Left Right
            if bf > 1 and key > node.left.key:
                node.left = self._left_rotate(node.left)
                return self._right_rotate(node)
            # Right Left
            if bf < -1 and key < node.right.key:
                node.right = self._right_rotate(node.right)
                return self._left_rotate(node)
            return node
        self.root = _insert(self.root) if hasattr(self, 'root') else AVLNode(key, value)

    def search(self, key):
        """Search for a key. Returns value or None."""
        node = self.root
        while node:
            if key == node.key:
                return node.value
            node = node.left if key < node.key else node.right
        return None

    def delete(self, key):
        """Delete a key from the AVL tree."""
        def _delete(node):
            if not node:
                return node
            if key < node.key:
                node.left = _delete(node.left)
            elif key > node.key:
                node.right = _delete(node.right)
            else:
                if not node.left or not node.right:
                    node = node.left or node.right
                else:
                    succ = node.right
                    while succ.left:
                        succ = succ.left
                    node.key, node.value = succ.key, succ.value
                    node.right = _delete(node.right)
            if not node:
                return node
            self._update(node)
            bf = self.balance_factor(node)
            if bf > 1 and self.balance_factor(node.left) >= 0:
                return self._right_rotate(node)
            if bf > 1 and self.balance_factor(node.left) < 0:
                node.left = self._left_rotate(node.left)
                return self._right_rotate(node)
            if bf < -1 and self.balance_factor(node.right) <= 0:
                return self._left_rotate(node)
            if bf < -1 and self.balance_factor(node.right) > 0:
                node.right = self._right_rotate(node.right)
                return self._left_rotate(node)
            return node
        self.root = _delete(self.root)

    def inorder_traversal(self):
        """Return list of keys in sorted order."""
        result = []
        def _inorder(node):
            if node:
                _inorder(node.left)
                result.append(node.key)
                _inorder(node.right)
        _inorder(self.root)
        return result


def main():
    tree = AVLTree()
    for key in [10, 20, 30, 40, 50, 25]:
        tree.insert(key, key * 10)
    print("Inorder traversal:", tree.inorder_traversal())
    print("Search 25:", tree.search(25))
    print("Search 99:", tree.search(99))


if __name__ == "__main__":
    main()
