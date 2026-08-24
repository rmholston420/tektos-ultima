"""Cache - File-based cache for build task outputs."""

import os
import pickle
from typing import Any, Optional


class Cache:
    """File-based cache that stores task outputs keyed by cache hash.

    Uses pickle for serialization. Stores files in cache_dir/key.pkl.
    """

    def __init__(self, cache_dir: str = ".build_cache"):
        """Initialize the cache.

        Args:
            cache_dir: Directory to store cached files.
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _key_path(self, key: str) -> str:
        """Get the file path for a cache key.

        Args:
            key: The cache key.

        Returns:
            Full path to the cached file.
        """
        safe_key = key.replace("/", "_").replace("\\", "_")
        return os.path.join(self.cache_dir, f"{safe_key}.pkl")

    def get(self, key: str) -> Optional[Any]:
        """Get a cached value.

        Args:
            key: The cache key.

        Returns:
            The cached value, or None if not found.
        """
        path = self._key_path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except (pickle.UnpicklingError, EOFError, OSError):
            return None

    def put(self, key: str, value: Any) -> None:
        """Store a value in the cache.

        Args:
            key: The cache key.
            value: The value to cache.
        """
        path = self._key_path(key)
        with open(path, "wb") as f:
            pickle.dump(value, f)

    def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: The cache key.

        Returns:
            True if the key exists.
        """
        return os.path.exists(self._key_path(key))

    def delete(self, key: str) -> None:
        """Remove a key from the cache.

        Args:
            key: The cache key to remove.
        """
        path = self._key_path(key)
        if os.path.exists(path):
            os.remove(path)

    def clear(self) -> None:
        """Remove all cached files."""
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                if filename.endswith(".pkl"):
                    os.remove(os.path.join(self.cache_dir, filename))

    def size(self) -> int:
        """Get the number of cached items.

        Returns:
            Number of cached items.
        """
        if not os.path.exists(self.cache_dir):
            return 0
        return len([f for f in os.listdir(self.cache_dir) if f.endswith(".pkl")])
