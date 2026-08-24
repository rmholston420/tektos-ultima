import os
import pickle


class Cache:
    """A simple file-based cache using pickle for serialization."""

    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _path(self, key):
        return os.path.join(self.cache_dir, f"{key}.pkl")

    def get(self, key):
        path = self._path(key)
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            return pickle.load(f)

    def put(self, key, value):
        path = self._path(key)
        with open(path, "wb") as f:
            pickle.dump(value, f)

    def exists(self, key):
        return os.path.exists(self._path(key))

    def delete(self, key):
        path = self._path(key)
        if os.path.exists(path):
            os.remove(path)

    def clear(self):
        for filename in os.listdir(self.cache_dir):
            if filename.endswith(".pkl"):
                os.remove(os.path.join(self.cache_dir, filename))
