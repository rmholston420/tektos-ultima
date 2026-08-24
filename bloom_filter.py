import hashlib


class BloomFilter:
    def __init__(self, size: int, hash_count: int):
        self.size = size
        self.hash_count = hash_count
        self.bit_array = bytearray(size)

    def _hashes(self, item: str):
        for i in range(self.hash_count):
            digest = hashlib.sha256(f"{i}:{item}".encode()).digest()
            yield int.from_bytes(digest[:4], "big") % self.size

    def add(self, item: str):
        for pos in self._hashes(item):
            self.bit_array[pos] = 1

    def contains(self, item: str) -> bool:
        return all(self.bit_array[pos] for pos in self._hashes(item))


def main():
    bf = BloomFilter(size=1000, hash_count=3)

    words = ["apple", "banana", "cherry", "date", "elderberry"]
    for w in words:
        bf.add(w)

    for w in words:
        print(f"{w}: {bf.contains(w)}")

    print(f"fig: {bf.contains('fig')}")
    print(f"grape: {bf.contains('grape')}")


if __name__ == "__main__":
    main()
