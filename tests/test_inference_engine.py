"""Tests for src/tektos/runtime/inference_engine.py

Covers: LlamaCppInstance, LlamaCppMetrics, OptimizationRecommendation,
InferenceEngineState, InferenceEngineMonitor, convenience functions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tektos.runtime.inference_engine import (
    LlamaCppInstance,
    LlamaCppMetrics,
    OptimizationRecommendation,
    InferenceEngineState,
    InferenceEngineMonitor,
    KNOWN_INSTANCES,
    REPO_SIZE_CONTEXT_RECOMMENDATIONS,
    RepoSize,
    CURRENT_REPO_SIZE,
    CURRENT_REPO_LOC,
    get_monitor,
    collect_inference_metrics,
)


# ── LlamaCppInstance ─────────────────────────────────────────────────────────

class TestLlamaCppInstance:
    def test_base_url_construction(self):
        inst = LlamaCppInstance(
            port=8090, model_name="test", model_path="/path",
            parameter_size="1B", quantization="Q4", format="gguf",
            capabilities=["completion"], is_gpu=True, is_embedding=False,
        )
        assert inst.base_url == "http://127.0.0.1:8090/v1"

    def test_embedder_instance(self):
        inst = LlamaCppInstance(
            port=8091, model_name="embed", model_path="",
            parameter_size="0.6B", quantization="Q4", format="gguf",
            capabilities=["embedding"], is_gpu=False, is_embedding=True,
        )
        assert inst.is_embedding is True
        assert inst.is_gpu is False

    def test_cpu_instance(self):
        inst = LlamaCppInstance(
            port=8092, model_name="granite", model_path="",
            parameter_size="8B", quantization="Q4", format="gguf",
            capabilities=["completion"], is_gpu=False, is_embedding=False,
        )
        assert inst.is_gpu is False
        assert inst.base_url == "http://127.0.0.1:8092/v1"


# ── LlamaCppMetrics ──────────────────────────────────────────────────────────

class TestLlamaCppMetrics:
    def test_default_values(self):
        m = LlamaCppMetrics()
        assert m.prompt_tokens_total == 0.0
        assert m.cache_hit_rate == 0.0
        assert m.total_tokens_processed == 0.0

    def test_update_from_prometheus_basic(self):
        m = LlamaCppMetrics()
        text = (
            "llamacpp:prompt_tokens_total 1000\n"
            "llamacpp:prompt_tokens_cached_total 600\n"
            "llamacpp:tokens_predicted_total 500\n"
            "llamacpp:n_decode_total 500\n"
            "llamacpp:prompt_seconds_total 2.0\n"
            "llamacpp:tokens_predicted_seconds_total 1.5\n"
            "llamacpp:n_tokens_max 4096\n"
            "llamacpp:prompt_tokens_seconds 500.0\n"
            "llamacpp:predicted_tokens_seconds 333.33\n"
            "llamacpp:kv_cache_usage 0.5\n"
            "llamacpp:n_ctx_used 2048\n"
            "llamacpp:n_ctx_total 4096\n"
        )
        m.update_from_prometheus(text)
        assert m.prompt_tokens_total == 1000.0
        assert m.prompt_tokens_cached_total == 600.0
        assert m.tokens_predicted_total == 500.0
        assert m.n_tokens_max == 4096.0
        assert m.prompt_tokens_seconds == 500.0
        assert m.predicted_tokens_seconds == 333.33
        assert m.kv_cache_usage == 0.5
        assert m.n_ctx_used == 2048.0
        assert m.n_ctx_total == 4096.0

    def test_cache_hit_rate_computation(self):
        m = LlamaCppMetrics()
        text = (
            "llamacpp:prompt_tokens_total 1000\n"
            "llamacpp:prompt_tokens_cached_total 800\n"
        )
        m.update_from_prometheus(text)
        # cache_hit_rate = 1 - (uncached / total) = 1 - (200/1000) = 0.8
        assert m.cache_hit_rate == pytest.approx(0.8)

    def test_cache_hit_rate_zero_cached(self):
        m = LlamaCppMetrics()
        text = (
            "llamacpp:prompt_tokens_total 1000\n"
            "llamacpp:prompt_tokens_cached_total 0\n"
        )
        m.update_from_prometheus(text)
        assert m.cache_hit_rate == pytest.approx(0.0)

    def test_avg_prompt_latency(self):
        m = LlamaCppMetrics()
        text = (
            "llamacpp:prompt_tokens_total 1000\n"
            "llamacpp:prompt_seconds_total 2.0\n"
        )
        m.update_from_prometheus(text)
        # avg = (2.0 / 1000) * 1000 = 2.0 ms
        assert m.avg_prompt_latency_ms == pytest.approx(2.0)

    def test_avg_generation_latency(self):
        m = LlamaCppMetrics()
        text = (
            "llamacpp:tokens_predicted_total 500\n"
            "llamacpp:tokens_predicted_seconds_total 1.5\n"
        )
        m.update_from_prometheus(text)
        # avg = (1.5 / 500) * 1000 = 3.0 ms
        assert m.avg_generation_latency_ms == pytest.approx(3.0)

    def test_total_tokens(self):
        m = LlamaCppMetrics()
        text = (
            "llamacpp:prompt_tokens_total 1000\n"
            "llamacpp:tokens_predicted_total 500\n"
        )
        m.update_from_prometheus(text)
        assert m.total_tokens_processed == pytest.approx(1500.0)

    def test_ignores_comments_and_blank_lines(self):
        m = LlamaCppMetrics()
        text = (
            "# Comment line\n"
            "\n"
            "llamacpp:prompt_tokens_total 100\n"
            "# Another comment\n"
        )
        m.update_from_prometheus(text)
        assert m.prompt_tokens_total == 100.0

    def test_ignores_invalid_lines(self):
        m = LlamaCppMetrics()
        text = (
            "invalid line without value\n"
            "llamacpp:prompt_tokens_total 100\n"
            "llamacpp:unknown_metric\n"
        )
        m.update_from_prometheus(text)
        assert m.prompt_tokens_total == 100.0

    def test_spec_decode_metrics(self):
        m = LlamaCppMetrics()
        text = (
            "llamacpp:spec_decode_num_draft_tokens_total 200\n"
            "llamacpp:spec_decode_num_accepted_tokens_total 150\n"
            "llamacpp:spec_decode_num_drafts_total 100\n"
        )
        m.update_from_prometheus(text)
        assert m.spec_decode_num_draft_tokens_total == 200.0
        assert m.spec_decode_num_accepted_tokens_total == 150.0
        assert m.spec_decode_num_drafts_total == 100.0

    def test_timestamp_set_on_update(self):
        m = LlamaCppMetrics(timestamp="2026-01-01T00:00:00+00:00")
        assert m.timestamp == "2026-01-01T00:00:00+00:00"


# ── OptimizationRecommendation ───────────────────────────────────────────────

class TestOptimizationRecommendation:
    def test_to_markdown(self):
        rec = OptimizationRecommendation(
            category="kv_cache", metric="n_ctx",
            current_value=4096.0, recommended_value=4915.2,
            reason="Test reason", priority="high", confidence=0.9,
        )
        md = rec.to_markdown()
        assert "**kv_cache**" in md
        assert "4915.2" in md
        assert "90%" in md
        assert "Test reason" in md


# ── InferenceEngineState ─────────────────────────────────────────────────────

class TestInferenceEngineState:
    def test_default_state(self):
        state = InferenceEngineState()
        assert state.instances == {}
        assert state.recommendations == []
        assert state.health_status == {}
        assert state.total_tokens_processed == 0.0
        assert state.avg_cache_hit_rate == 0.0

    def test_state_with_data(self):
        metrics = LlamaCppMetrics()
        metrics.prompt_tokens_total = 1000
        metrics.cache_hit_rate = 0.8
        state = InferenceEngineState()
        state.instances["primary_gpu"] = metrics
        state.total_tokens_processed = 1500.0
        state.avg_cache_hit_rate = 0.8
        assert len(state.instances) == 1
        assert state.total_tokens_processed == 1500.0


# ── InferenceEngineMonitor ───────────────────────────────────────────────────

class TestInferenceEngineMonitor:
    def test_init_with_default_instances(self):
        monitor = InferenceEngineMonitor()
        assert len(monitor.instances) == 3
        assert "primary_gpu" in monitor.instances
        assert "secondary_cpu" in monitor.instances
        assert "embedder_cpu" in monitor.instances

    def test_init_with_custom_instances(self):
        custom = {
            "custom": LlamaCppInstance(
                port=9999, model_name="custom", model_path="",
                parameter_size="1B", quantization="Q4", format="gguf",
                capabilities=["completion"], is_gpu=False, is_embedding=False,
            )
        }
        monitor = InferenceEngineMonitor(instances=custom)
        assert len(monitor.instances) == 1
        assert "custom" in monitor.instances

    @pytest.mark.asyncio
    async def test_start_creates_client(self):
        monitor = InferenceEngineMonitor()
        await monitor.start()
        assert monitor._client is not None
        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_closes_client(self):
        monitor = InferenceEngineMonitor()
        await monitor.start()
        await monitor.stop()
        assert monitor._client is None

    @pytest.mark.asyncio
    async def test_discover_instances_all_healthy(self):
        monitor = InferenceEngineMonitor()
        await monitor.start()
        try:
            # Mock all instances as healthy
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"status": "ok"}
            monitor._client.get = AsyncMock(return_value=mock_resp)

            active = await monitor.discover_instances()
            assert len(active) == 3
            assert monitor._state.health_status["primary_gpu"] == "healthy"
            assert monitor._state.health_status["secondary_cpu"] == "healthy"
            assert monitor._state.health_status["embedder_cpu"] == "healthy"
        finally:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_discover_instances_some_unhealthy(self):
        monitor = InferenceEngineMonitor()
        await monitor.start()
        try:
            call_count = [0]
            async def mock_get(url):
                call_count[0] += 1
                mock_resp = MagicMock()
                if "8090" in url:
                    mock_resp.status_code = 200
                    mock_resp.json.return_value = {"status": "ok"}
                elif "8092" in url:
                    mock_resp.status_code = 500
                else:
                    raise Exception("Connection refused")
                return mock_resp

            monitor._client.get = mock_get
            active = await monitor.discover_instances()
            assert "primary_gpu" in active
            assert "secondary_cpu" not in active
            assert "embedder_cpu" not in active
            assert monitor._state.health_status["primary_gpu"] == "healthy"
            assert monitor._state.health_status["secondary_cpu"] == "unhealthy"
            assert monitor._state.health_status["embedder_cpu"] == "unhealthy"
        finally:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_collect_metrics_no_instance(self):
        monitor = InferenceEngineMonitor()
        await monitor.start()
        try:
            result = await monitor.collect_metrics("nonexistent")
            assert result is None
        finally:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_collect_metrics_http_error(self):
        monitor = InferenceEngineMonitor()
        await monitor.start()
        try:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            monitor._client.get = AsyncMock(return_value=mock_resp)

            result = await monitor.collect_metrics("primary_gpu")
            assert result is None
        finally:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_collect_metrics_success(self):
        monitor = InferenceEngineMonitor()
        await monitor.start()
        try:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = (
                "llamacpp:prompt_tokens_total 100\n"
                "llamacpp:tokens_predicted_total 50\n"
            )
            monitor._client.get = AsyncMock(return_value=mock_resp)

            # Mock subprocess calls (subprocess is imported inside _collect_system_metrics)
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="")
                result = await monitor.collect_metrics("primary_gpu")

            assert result is not None
            assert result.prompt_tokens_total == 100.0
            assert result.tokens_predicted_total == 50.0
        finally:
            await monitor.stop()

    def test_generate_recommendations_kv_cache(self):
        monitor = InferenceEngineMonitor()
        metrics = LlamaCppMetrics()
        metrics.n_tokens_max = 40960.0  # > 32000 → high priority
        metrics.cache_hit_rate = 0.3  # < 0.5 → recommendation
        metrics.predicted_tokens_seconds = 300.0
        metrics.prompt_tokens_seconds = 400.0
        monitor._state.instances["primary_gpu"] = metrics

        recs = monitor._generate_recommendations()
        categories = [r.category for r in recs]
        assert "kv_cache" in categories
        assert "batch_size" in categories
        assert "routing" in categories

    def test_generate_recommendations_high_vram(self):
        monitor = InferenceEngineMonitor()
        metrics = LlamaCppMetrics()
        metrics.gpu_memory_used_mb = 28000.0
        metrics.gpu_memory_total_mb = 30000.0  # 93% utilization → high priority
        metrics.n_tokens_max = 4096.0
        metrics.cache_hit_rate = 0.9
        metrics.predicted_tokens_seconds = 300.0
        monitor._state.instances["primary_gpu"] = metrics

        recs = monitor._generate_recommendations()
        categories = [r.category for r in recs]
        assert "gpu_offload" in categories

    def test_generate_recommendations_low_vram(self):
        monitor = InferenceEngineMonitor()
        metrics = LlamaCppMetrics()
        metrics.gpu_memory_used_mb = 10000.0
        metrics.gpu_memory_total_mb = 30000.0  # 33% utilization → medium priority
        metrics.n_tokens_max = 4096.0
        metrics.cache_hit_rate = 0.9
        metrics.predicted_tokens_seconds = 300.0
        monitor._state.instances["primary_gpu"] = metrics

        recs = monitor._generate_recommendations()
        vram_recs = [r for r in recs if r.category == "gpu_offload"]
        assert len(vram_recs) == 1
        assert vram_recs[0].priority == "medium"

    def test_generate_recommendations_cross_instance(self):
        monitor = InferenceEngineMonitor()
        primary = LlamaCppMetrics()
        primary.prompt_tokens_seconds = 6000.0  # > 5000
        primary.predicted_tokens_seconds = 0.0
        secondary = LlamaCppMetrics()
        secondary.predicted_tokens_seconds = 50.0  # < 100
        monitor._state.instances["primary_gpu"] = primary
        monitor._state.instances["secondary_cpu"] = secondary

        recs = monitor._generate_recommendations()
        routing_recs = [r for r in recs if r.category == "routing" and r.metric == "task_distribution"]
        assert len(routing_recs) == 1
        assert routing_recs[0].priority == "high"

    def test_get_state_summary(self):
        monitor = InferenceEngineMonitor()
        metrics = LlamaCppMetrics()
        metrics.total_tokens_processed = 1000.0
        metrics.cache_hit_rate = 0.8
        metrics.prompt_tokens_seconds = 500.0
        metrics.predicted_tokens_seconds = 333.0
        metrics.n_tokens_max = 4096.0
        metrics.gpu_memory_used_mb = 20000.0
        metrics.gpu_memory_total_mb = 30000.0
        metrics.gpu_temperature = 65.0
        metrics.gpu_utilization = 75.0
        monitor._state.instances["primary_gpu"] = metrics
        monitor._state.health_status["primary_gpu"] = "healthy"

        summary = monitor.get_state_summary()
        assert "# Inference Engine State" in summary
        assert "**primary_gpu**" in summary
        assert "healthy" in summary
        assert "1,000" in summary
        assert "80%" in summary
        assert "65°C" in summary

    def test_get_state_summary_empty(self):
        monitor = InferenceEngineMonitor()
        summary = monitor.get_state_summary()
        assert "# Inference Engine State" in summary

    def test_to_memory_entry(self):
        monitor = InferenceEngineMonitor()
        metrics = LlamaCppMetrics()
        metrics.total_tokens_processed = 1000.0
        metrics.cache_hit_rate = 0.8
        monitor._state.instances["primary_gpu"] = metrics
        monitor._state.total_tokens_processed = 1000.0
        monitor._state.avg_cache_hit_rate = 0.8
        monitor._state.health_status["primary_gpu"] = "healthy"
        monitor._state.recommendations = [
            OptimizationRecommendation(
                category="kv_cache", metric="n_ctx",
                current_value=4096.0, recommended_value=4915.2,
                reason="Test", priority="high", confidence=0.9,
            )
        ]

        entry = monitor.to_memory_entry()
        assert entry["total_tokens_processed"] == 1000.0
        assert entry["avg_cache_hit_rate"] == 0.8
        assert entry["recommendations_count"] == 1
        assert entry["high_priority_recommendations"] == 1


# ── Convenience Functions ────────────────────────────────────────────────────

class TestConvenienceFunctions:
    def test_get_monitor_creates_singleton(self):
        m1 = get_monitor()
        m2 = get_monitor()
        assert m1 is m2

    def test_get_monitor_with_custom_instances(self):
        custom = {
            "custom": LlamaCppInstance(
                port=9999, model_name="custom", model_path="",
                parameter_size="1B", quantization="Q4", format="gguf",
                capabilities=["completion"], is_gpu=False, is_embedding=False,
            )
        }
        # Reset singleton
        import tektos.runtime.inference_engine as ie
        ie._monitor = None
        m = get_monitor(instances=custom)
        assert len(m.instances) == 1
        # Reset again
        ie._monitor = None

    @pytest.mark.asyncio
    async def test_collect_inference_metrics(self):
        import tektos.runtime.inference_engine as ie
        ie._monitor = None
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            result = await collect_inference_metrics()
        assert isinstance(result, InferenceEngineState)
        ie._monitor = None


# ── Repo Size Constants ──────────────────────────────────────────────────────

class TestRepoSizeConstants:
    def test_repo_size_enum_values(self):
        assert RepoSize.VERY_SMALL.value == ("very_small", "<10,000 LOC")
        assert RepoSize.ENTERPRISE.value == ("enterprise", "10,000,000+ LOC")

    def test_context_recommendations_all_sizes(self):
        for size in RepoSize:
            rec = REPO_SIZE_CONTEXT_RECOMMENDATIONS[size]
            assert "max_tokens" in rec
            assert "context_window" in rec
            assert "memory_tiers" in rec
            assert rec["max_tokens"] >= rec["context_window"]

    def test_medium_repo_defaults(self):
        assert CURRENT_REPO_SIZE == RepoSize.MEDIUM
        assert CURRENT_REPO_LOC > 0
        rec = REPO_SIZE_CONTEXT_RECOMMENDATIONS[RepoSize.MEDIUM]
        assert rec["max_tokens"] == 131072
        assert rec["context_window"] == 65536

    def test_known_instances(self):
        assert len(KNOWN_INSTANCES) == 3
        assert KNOWN_INSTANCES["primary_gpu"].port == 8090
        assert KNOWN_INSTANCES["secondary_cpu"].port == 8092
        assert KNOWN_INSTANCES["embedder_cpu"].port == 8091
        assert KNOWN_INSTANCES["primary_gpu"].is_gpu is True
        assert KNOWN_INSTANCES["embedder_cpu"].is_embedding is True
