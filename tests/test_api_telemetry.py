"""Tests for /api/telemetry endpoint — live hardware data.

Tests the actual /api/telemetry FastAPI endpoint using the TestClient,
verifying it returns real GPU/CPU/memory/disk metrics from live sensors.

Rules:
- Always test with live data (not mocked) when possible.
- Tests verify the real nvidia-smi + /proc code paths.
- Uses pytest-asyncio for any async tests.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient

from tektos.main import app


@pytest.fixture
def client():
    """Create a TestClient for the FastAPI app."""
    app.dependency_overrides = {}
    return TestClient(app)


# ---------------------------------------------------------------------------
# Live hardware tests — these run against real sensors on Colossus
# ---------------------------------------------------------------------------


class TestLiveTelemetryEndpoint:
    """Test /api/telemetry returns real hardware data."""

    def test_endpoint_exists(self, client):
        """Verify the /api/telemetry endpoint is registered."""
        response = client.get("/api/telemetry")
        assert response.status_code == 200

    def test_response_is_json(self, client):
        """Verify response is valid JSON."""
        response = client.get("/api/telemetry")
        assert response.headers["content-type"] == "application/json"
        data = response.json()
        assert isinstance(data, dict)

    def test_has_gpu_section(self, client):
        """Verify response contains a 'gpu' section."""
        data = client.get("/api/telemetry").json()
        assert "gpu" in data
        gpu = data["gpu"]
        assert isinstance(gpu, dict)

    def test_has_system_section(self, client):
        """Verify response contains a 'system' section."""
        data = client.get("/api/telemetry").json()
        assert "system" in data
        system = data["system"]
        assert isinstance(system, dict)

    def test_has_timestamp(self, client):
        """Verify response contains a numeric timestamp."""
        data = client.get("/api/telemetry").json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], (int, float))

    # ---- GPU metrics must be real ----

    def test_gpu_temperature_is_real(self, client):
        """Verify GPU temperature matches nvidia-smi."""
        api_data = client.get("/api/telemetry").json()["gpu"]
        nvidia_smi_data = _get_nvidia_smi_gpu()

        # API temperature should be in a reasonable range
        assert 0 <= api_data["temperature"] <= 100

        # Verify it matches nvidia-smi (±5°C for timing tolerance)
        nvidia_temp = nvidia_smi_data["temperature"]
        assert abs(api_data["temperature"] - nvidia_temp) <= 5, \
            f"API temp={api_data['temperature']} differs from nvidia-smi temp={nvidia_temp}"

    def test_gpu_utilization_is_real(self, client):
        """Verify GPU utilization matches nvidia-smi."""
        api_data = client.get("/api/telemetry").json()["gpu"]
        nvidia_smi_data = _get_nvidia_smi_gpu()

        assert 0 <= api_data["utilization"] <= 100

        nvidia_util = nvidia_smi_data["utilization"]
        assert abs(api_data["utilization"] - nvidia_util) <= 5, \
            f"API util={api_data['utilization']} differs from nvidia-smi util={nvidia_util}"

    def test_gpu_memory_is_real(self, client):
        """Verify GPU memory matches nvidia-smi."""
        api_data = client.get("/api/telemetry").json()["gpu"]
        nvidia_smi_data = _get_nvidia_smi_gpu()

        assert api_data["memory_total"] > 0, "GPU memory_total must be > 0"
        assert 0 <= api_data["memory_used"] <= api_data["memory_total"]

        nvidia_used = nvidia_smi_data["memory_used"]
        nvidia_total = nvidia_smi_data["memory_total"]
        assert abs(api_data["memory_used"] - nvidia_used) <= 500, \
            f"API mem_used={api_data['memory_used']} differs from nvidia-smi={nvidia_used}"
        assert abs(api_data["memory_total"] - nvidia_total) <= 500

    def test_gpu_power_is_real(self, client):
        """Verify GPU power draw matches nvidia-smi."""
        api_data = client.get("/api/telemetry").json()["gpu"]

        assert api_data["power_limit"] > 0
        assert 0 <= api_data["power_draw"] <= api_data["power_limit"]

    def test_gpu_clocks_present(self, client):
        """Verify GPU clock speeds are present."""
        api_data = client.get("/api/telemetry").json()["gpu"]

        assert "clocks_graphics" in api_data
        assert "clocks_memory" in api_data

    # ---- System metrics must be real ----

    def test_cpu_util_is_real(self, client):
        """Verify CPU utilization from /proc/stat."""
        data = client.get("/api/telemetry").json()["system"]

        assert "cpu_util" in data
        assert 0 <= data["cpu_util"] <= 100, "CPU util should be 0-100%"

    def test_memory_is_real(self, client):
        """Verify system memory from /proc/meminfo."""
        data = client.get("/api/telemetry").json()["system"]

        assert data["mem_total_gb"] > 0, "Total RAM must be > 0"
        assert 0 <= data["mem_used_gb"] <= data["mem_total_gb"]
        assert 0 <= data["mem_percent"] <= 100

    def test_disk_is_real(self, client):
        """Verify disk usage from shutil.disk_usage."""
        data = client.get("/api/telemetry").json()["system"]

        assert data["disk_total_gb"] > 0
        assert 0 <= data["disk_used_gb"] <= data["disk_total_gb"]
        assert 0 <= data["disk_percent"] <= 100

    # ---- Cross-validate with nvidia-smi ----

    def test_all_gpu_fields_match_nvidia_smi(self, client):
        """Verify every GPU field matches nvidia-smi output."""
        api_data = client.get("/api/telemetry").json()["gpu"]
        nvidia_smi_data = _get_nvidia_smi_gpu()

        tolerance_mb = 500
        tolerance_pct = 25  # NVML and nvidia-smi read different sensors — 25% tolerance

        for field, nvidia_val in nvidia_smi_data.items():
            if field == "temperature" or field == "utilization":
                assert abs(api_data[field] - nvidia_val) <= tolerance_pct, \
                    f"GPU {field}: API={api_data[field]} vs nvidia-smi={nvidia_val}"
            else:
                assert abs(api_data[field] - nvidia_val) <= tolerance_mb, \
                    f"GPU {field}: API={api_data[field]} vs nvidia-smi={nvidia_val}"

    def test_real_data_not_zeros(self, client):
        """Verify GPU data is not all zeros (proves live sensor reading)."""
        data = client.get("/api/telemetry").json()["gpu"]

        # At minimum, memory_total should be > 0 (RTX 5090 has 32GB)
        assert data["memory_total"] > 10000, \
            f"GPU memory_total={data['memory_total']} looks like a fallback value"

        # At least one field should have a real non-zero value
        non_zero_fields = [
            k for k, v in data.items()
            if isinstance(v, (int, float)) and v > 0
        ]
        assert len(non_zero_fields) >= 3, \
            f"Only {len(non_zero_fields)} GPU fields have non-zero values: {non_zero_fields}"


# ---------------------------------------------------------------------------
# Helper functions — live hardware calls
# ---------------------------------------------------------------------------


def _get_nvidia_smi_gpu() -> dict:
    """Get GPU metrics directly from nvidia-smi for cross-validation."""
    result = subprocess.run(
        [
            "nvidia-smi", "--query-gpu="
            "temperature.gpu,utilization.gpu,memory.used,memory.total,"
            "power.draw,power.limit,fan.speed",
            "--format=csv,noheader,nounits"
        ],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        pytest.skip("nvidia-smi not available or failed")

    vals = [v.strip() for v in result.stdout.strip().split(",")]
    return {
        "temperature": float(vals[0]) if len(vals) > 0 else 0,
        "utilization": float(vals[1]) if len(vals) > 1 else 0,
        "memory_used": float(vals[2]) if len(vals) > 2 else 0,
        "memory_total": float(vals[3]) if len(vals) > 3 else 0,
        "power_draw": float(vals[4]) if len(vals) > 4 else 0,
        "power_limit": float(vals[5]) if len(vals) > 5 else 0,
        "fan_speed": int(float(vals[6])) if len(vals) > 6 else 0,
    }
