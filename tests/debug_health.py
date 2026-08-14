import sys

sys.path.insert(0, "src")
from fastapi.testclient import TestClient

from tektos.main import app

c = TestClient(app)
try:
    r = c.get("/health")
    print("Status:", r.status_code)
    print("Body:", r.text[:500])
except Exception as e:
    print("Exception:", e)
    import traceback

    traceback.print_exc()
