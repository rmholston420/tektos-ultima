import json
import time
import os


class KVStore:
    def __init__(self, persist_file=None):
        self._store = {}  # key -> {"value": ..., "expires": float | None}
        self._persist_file = persist_file
        if persist_file and os.path.exists(persist_file):
            self._load()

    def set(self, key, value, ttl_seconds=None):
        expires = time.time() + ttl_seconds if ttl_seconds else None
        self._store[key] = {"value": value, "expires": expires}
        self._save()

    def get(self, key):
        self._cleanup()
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry["expires"] is not None and time.time() > entry["expires"]:
            del self._store[key]
            return None
        return entry["value"]

    def delete(self, key):
        if key in self._store:
            del self._store[key]
            self._save()

    def _cleanup(self):
        now = time.time()
        expired = [k for k, v in self._store.items()
                   if v["expires"] is not None and now > v["expires"]]
        for k in expired:
            del self._store[k]

    def _save(self):
        if not self._persist_file:
            return
        data = {k: v["value"] for k, v in self._store.items()
                if v["expires"] is None}
        with open(self._persist_file, "w") as f:
            json.dump(data, f)

    def _load(self):
        with open(self._persist_file, "r") as f:
            data = json.load(f)
        self._store = {k: {"value": v, "expires": None}
                       for k, v in data.items()}


def main():
    import tempfile
    path = tempfile.mktemp(suffix=".json")

    store = KVStore(persist_file=path)

    # Basic set/get
    store.set("name", "Alice")
    store.set("age", 30)
    print(store.get("name"))   # Alice
    print(store.get("age"))    # 30
    print(store.get("missing"))  # None

    # TTL: expires after 2 seconds
    store.set("temp", "hello", ttl_seconds=2)
    print(store.get("temp"))   # hello
    time.sleep(3)
    print(store.get("temp"))   # None (expired)

    # Delete
    store.delete("name")
    print(store.get("name"))   # None

    # Persistence survives across instances
    store2 = KVStore(persist_file=path)
    print(store2.get("age"))   # 30
    print(store2.get("temp"))  # None (expired and not persisted)

    os.unlink(path)


if __name__ == "__main__":
    main()
