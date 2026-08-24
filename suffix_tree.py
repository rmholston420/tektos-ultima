class SuffixTree:
    """Simple suffix tree using a trie with edge labels (start, end) for compact paths."""

    def __init__(self):
        self.root = {}
        self.text = ""

    def build(self, text):
        """Build the suffix tree for *text*."""
        self.text = text
        n = len(text)
        for i in range(n):
            self._add_suffix(text[i:])

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------

    def _add_suffix(self, suffix):
        """Insert one suffix into the tree."""
        node = self.root
        i = 0
        while i < len(suffix):
            ch = suffix[i]
            if ch in node:
                start, end = node[ch]
                edge = self.text[start:end]
                # Walk along the edge as far as possible
                j = 0
                while j < len(edge) and i + j < len(suffix) and edge[j] == suffix[i + j]:
                    j += 1
                if j == len(edge):
                    # edge fully consumed — descend
                    node = node[ch]
                    i += j
                    continue
                # Split the edge at position j
                mid = node[ch][0] + j
                mid_ch = self.text[mid]
                mid_node = {mid_ch: (mid, node[ch][1])}
                node[ch] = (node[ch][0], mid)
                node = mid_node
                i += j
            else:
                # create a fresh edge
                node[ch] = (len(self.text) - len(suffix) + i, len(self.text))
                break

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------

    def search(self, pattern):
        """Return all starting positions of *pattern* in the built text."""
        if not pattern:
            return []
        node = self.root
        for ch in pattern:
            if ch not in node:
                return []
            start, end = node[ch]
            edge = self.text[start:end]
            if not pattern.startswith(edge):
                return []
            pattern = pattern[len(edge):]
            node = node[ch]

        # collect leaf positions beneath *node*
        leaves = self._collect_leaves(node)
        return sorted(leaves)

    def _collect_leaves(self, node):
        """Recursively gather every leaf offset under *node*."""
        result = []
        for _, (start, end) in node.items():
            result.append(start)
            result.extend(self._collect_leaves(node))
        return result

    # ------------------------------------------------------------------
    # longest repeated substring
    # ------------------------------------------------------------------

    def longest_repeated_substring(self):
        """Return the longest substring that appears at least twice."""
        best = ""
        self._walk(node=self.root, current="", best=best)
        return best

    def _walk(self, node, current, best):
        """Depth-first walk; update *best* with the longest label seen."""
        for _, (start, end) in node.items():
            edge = self.text[start:end]
            nxt = current + edge
            if len(nxt) > len(best):
                best = nxt
            self._walk(node, nxt, best)
        return best


# ======================================================================
# demo
# ======================================================================

def main():
    text = "banana"
    tree = SuffixTree()
    tree.build(text)

    print(f"Text: {text}")
    for pat in ["ana", "an", "na", "z", ""]:
        pos = tree.search(pat)
        print(f"  search('{pat}') -> {pos}")

    lrs = tree.longest_repeated_substring()
    print(f"  longest_repeated_substring() -> '{lrs}'")


if __name__ == "__main__":
    main()
