"""
Red-Black Tree Implementation in Python

A self-balancing binary search tree that maintains the following properties:
1. Every node is either red or black.
2. The root is black.
3. Every leaf (NIL) is black.
4. If a node is red, then both its children are black (no red-red violation).
5. For each node, all simple paths from the node to descendant leaves
   contain the same number of black nodes (black-height consistency).
"""


class Node:
    """Represents a node in the Red-Black Tree."""

    RED = 1
    BLACK = 0

    def __init__(self, key, color=RED, left=None, right=None, parent=None):
        """
        Initialize a Node.

        Args:
            key: The key value stored in this node.
            color: Node color (RED=1 or BLACK=0). Default is RED.
            left: Left child node.
            right: Right child node.
            parent: Parent node.
        """
        self.key = key
        self.color = color
        self.left = left
        self.right = right
        self.parent = parent

    def __repr__(self):
        color_name = "RED" if self.color == self.RED else "BLACK"
        return f"Node(key={self.key}, color={color_name})"


class RedBlackTree:
    """
    Red-Black Tree: a self-balancing binary search tree.

    All operations (insert, search, rotate) maintain the Red-Black invariants,
    ensuring O(log n) time complexity for insert and search.
    """

    def __init__(self):
        """Initialize an empty Red-Black Tree with a sentinel NIL node."""
        self.NIL = Node(None, color=Node.BLACK)  # Sentinel leaf node
        self.root = self.NIL

    # ------------------------------------------------------------------ #
    #  Rotation methods
    # ------------------------------------------------------------------ #

    def left_rotate(self, x):
        """
        Perform a left rotation around node x.

        This makes x's right child the new parent of x.

        Args:
            x: The node to rotate around.
        """
        y = x.right  # Turn y's left subtree into x's right subtree
        x.right = y.left
        if y.left != self.NIL:
            y.left.parent = x
        y.parent = x.parent
        if x.parent == self.NIL:
            self.root = y
        elif x == x.parent.left:
            x.parent.left = y
        else:
            x.parent.right = y
        y.left = x
        x.parent = y

    def right_rotate(self, y):
        """
        Perform a right rotation around node y.

        This makes y's left child the new parent of y.

        Args:
            y: The node to rotate around.
        """
        x = y.left  # Turn x's right subtree into y's left subtree
        y.left = x.right
        if x.right != self.NIL:
            x.right.parent = y
        x.parent = y.parent
        if y.parent == self.NIL:
            self.root = x
        elif y == y.parent.right:
            y.parent.right = x
        else:
            y.parent.left = x
        x.right = y
        y.parent = x

    # ------------------------------------------------------------------ #
    #  Insert
    # ------------------------------------------------------------------ #

    def insert(self, key):
        """
        Insert a key into the Red-Black Tree.

        If the key already exists, it is ignored (no duplicates).

        Args:
            key: The key to insert.
        """
        # Standard BST insert
        z = Node(key, color=Node.RED)
        y = self.NIL
        x = self.root
        while x != self.NIL:
            y = x
            if z.key < x.key:
                x = x.left
            elif z.key > x.key:
                x = x.right
            else:
                # Duplicate key — ignore
                return
        z.parent = y
        if y == self.NIL:
            self.root = z
        elif z.key < y.key:
            y.left = z
        else:
            y.right = z
        z.left = self.NIL
        z.right = self.NIL
        self.insert_fixup(z)

    def insert_fixup(self, z):
        """
        Restore Red-Black properties after insertion.

        The new node is inserted as red. This method re-colors and rotates
        as needed to fix any violations.

        Args:
            z: The newly inserted node.
        """
        while z.parent.color == Node.RED:
            if z.parent == z.parent.parent.left:
                uncle = z.parent.parent.right
                if uncle.color == Node.RED:
                    # Case 1: Uncle is red — recolor
                    z.parent.color = Node.BLACK
                    uncle.color = Node.BLACK
                    z.parent.parent.color = Node.RED
                    z = z.parent.parent
                else:
                    if z == z.parent.right:
                        # Case 2: z is a right child — left rotate
                        z = z.parent
                        self.left_rotate(z)
                    # Case 3: z is a left child — right rotate + recolor
                    z.parent.color = Node.BLACK
                    z.parent.parent.color = Node.RED
                    self.right_rotate(z.parent.parent)
            else:
                uncle = z.parent.parent.left
                if uncle.color == Node.RED:
                    # Case 1: Uncle is red — recolor
                    z.parent.color = Node.BLACK
                    uncle.color = Node.BLACK
                    z.parent.parent.color = Node.RED
                    z = z.parent.parent
                else:
                    if z == z.parent.left:
                        # Case 2: z is a left child — right rotate
                        z = z.parent
                        self.right_rotate(z)
                    # Case 3: z is a right child — left rotate + recolor
                    z.parent.color = Node.BLACK
                    z.parent.parent.color = Node.RED
                    self.left_rotate(z.parent.parent)
        self.root.color = Node.BLACK  # Root is always black

    # ------------------------------------------------------------------ #
    #  Search
    # ------------------------------------------------------------------ #

    def search(self, key):
        """
        Search for a key in the Red-Black Tree.

        Args:
            key: The key to search for.

        Returns:
            True if the key exists, False otherwise.
        """
        current = self.root
        while current != self.NIL:
            if key == current.key:
                return True
            elif key < current.key:
                current = current.left
            else:
                current = current.right
        return False

    # ------------------------------------------------------------------ #
    #  Inorder traversal
    # ------------------------------------------------------------------ #

    def inorder(self):
        """
        Return a list of keys in sorted (inorder) order.

        Returns:
            A list of keys sorted in ascending order.
        """
        result = []
        self._inorder_helper(self.root, result)
        return result

    def _inorder_helper(self, node, result):
        """Helper for inorder traversal."""
        if node == self.NIL:
            return
        self._inorder_helper(node.left, result)
        result.append(node.key)
        self._inorder_helper(node.right, result)

    # ------------------------------------------------------------------ #
    #  Min / Max
    # ------------------------------------------------------------------ #

    def min(self):
        """
        Find the minimum key in the tree.

        Returns:
            The minimum key, or None if the tree is empty.
        """
        if self.root == self.NIL:
            return None
        current = self.root
        while current.left != self.NIL:
            current = current.left
        return current.key

    def max(self):
        """
        Find the maximum key in the tree.

        Returns:
            The maximum key, or None if the tree is empty.
        """
        if self.root == self.NIL:
            return None
        current = self.root
        while current.right != self.NIL:
            current = current.right
        return current.key

    # ------------------------------------------------------------------ #
    #  Height
    # ------------------------------------------------------------------ #

    def height(self):
        """
        Return the height of the tree (longest path from root to leaf).

        Returns:
            The height as an integer. Returns -1 for an empty tree,
            0 for a tree with only the root.
        """
        return self._height_helper(self.root)

    def _height_helper(self, node):
        """Helper to compute tree height recursively."""
        if node == self.NIL:
            return -1
        return 1 + max(self._height_helper(node.left), self._height_helper(node.right))

    # ------------------------------------------------------------------ #
    #  Validation
    # ------------------------------------------------------------------ #

    def is_valid(self):
        """
        Verify that the tree satisfies all Red-Black properties.

        Checks:
          1. Root is black.
          2. No red node has a red child (no red-red violation).
          3. Every path from root to a leaf has the same black-height.

        Returns:
            True if the tree is a valid Red-Black Tree, False otherwise.
        """
        if self.root == self.NIL:
            return True

        # Property 1: Root is black
        if self.root.color != Node.BLACK:
            return False

        # Properties 2 & 3
        return self._validate(self.root, 0) is not None

    def _validate(self, node, black_count):
        """
        Recursively check red-red violations and count black-height.

        Args:
            node: Current node being validated.
            black_count: Number of black nodes on the path so far.

        Returns:
            The black-height of this subtree if valid, or None if invalid.
        """
        if node == self.NIL:
            return black_count

        # Property 2: No red-red violation
        if node.color == Node.RED:
            if (node.left != self.NIL and node.left.color == Node.RED) or \
               (node.right != self.NIL and node.right.color == Node.RED):
                return None

        # Count black nodes (the node itself counts if black)
        new_black_count = black_count + (1 if node.color == Node.BLACK else 0)

        left_bh = self._validate(node.left, new_black_count)
        if left_bh is None:
            return None

        right_bh = self._validate(node.right, new_black_count)
        if right_bh is None:
            return None

        # Property 5: Black-height consistency
        if left_bh != right_bh:
            return None

        return left_bh


# ---------------------------------------------------------------------- #
#  Main — demo, insert 15+ nodes, print inorder, verify, test search
# ---------------------------------------------------------------------- #

if __name__ == "__main__":
    print("=" * 60)
    print("  Red-Black Tree — Demo and Validation")
    print("=" * 60)

    tree = RedBlackTree()

    # Insert 18 nodes (well over the 15+ requirement)
    keys = [10, 20, 30, 15, 5, 25, 35, 1, 7, 12, 18, 22, 28, 32, 40, 3, 9, 14]
    print(f"\nInserting {len(keys)} keys: {keys}")

    for k in keys:
        tree.insert(k)

    # Test duplicate insertion (should be ignored)
    print("\nAttempting to insert duplicate key 10... (should be ignored)")
    tree.insert(10)
    print("  Done — duplicate ignored.")

    # Inorder traversal
    print(f"\nInorder traversal: {tree.inorder()}")

    # Min / Max
    print(f"Minimum key: {tree.min()}")
    print(f"Maximum key: {tree.max()}")

    # Height
    print(f"Tree height: {tree.height()}")

    # Validation
    valid = tree.is_valid()
    print(f"\nRed-Black Tree valid: {valid}")
    if valid:
        print("  ✓ Root is black")
        print("  ✓ No red-red violations")
        print("  ✓ Black-height is consistent")
    else:
        print("  ✗ Tree is INVALID!")

    # Search tests
    print("\n--- Search Tests ---")
    search_keys = [10, 15, 40, 99, 1, 35, 7]
    for key in search_keys:
        found = tree.search(key)
        status = "FOUND" if found else "NOT FOUND"
        print(f"  search({key}) -> {status}")

    print("\n" + "=" * 60)
    print("  Demo complete.")
    print("=" * 60)
