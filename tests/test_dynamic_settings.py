"""Tests for runtime/dynamic_settings.py — DynamicSettings, SettingsOptimizer, detect_task_type."""

import pytest

from tektos.runtime.dynamic_settings import (
    DynamicSettings,
    ReasoningEffort,
    SettingsOptimizer,
    TaskType,
    detect_task_type,
    get_optimizer,
)


class TestDynamicSettings:
    """Tests for DynamicSettings dataclass."""

    def test_default_values(self):
        s = DynamicSettings()
        assert s.temperature == 0.7
        assert s.top_p == 0.95
        assert s.top_k == 40
        assert s.min_p == 0.05
        assert s.repeat_penalty == 1.1
        assert s.n_predict == 4096
        assert s.seed == -1
        assert s.enable_thinking is False
        assert s.reasoning_effort == ReasoningEffort.MEDIUM
        assert s.cache_prompt is True

    def test_update_single_field(self):
        s = DynamicSettings()
        s.update(temperature=0.3)
        assert s.temperature == 0.3
        assert s.top_p == 0.95  # unchanged

    def test_update_multiple_fields(self):
        s = DynamicSettings()
        s.update(temperature=0.1, top_p=0.8, top_k=10)
        assert s.temperature == 0.1
        assert s.top_p == 0.8
        assert s.top_k == 10

    def test_update_nonexistent_field(self):
        s = DynamicSettings()
        s.update(nonexistent=42)  # should silently ignore
        assert s.temperature == 0.7  # unchanged

    def test_reset_to_defaults(self):
        s = DynamicSettings()
        s.update(temperature=0.1, top_p=0.8)
        s.reset_to_defaults()
        assert s.temperature == 0.7
        assert s.top_p == 0.95
        assert s.top_k == 40
        assert s.enable_thinking is False

    def test_to_payload_empty(self):
        s = DynamicSettings()
        payload = s.to_payload()
        # Only non-default fields should be in payload
        assert "temperature" not in payload  # 0.7 is default
        assert "top_p" not in payload  # 0.95 is default

    def test_to_payload_with_changes(self):
        s = DynamicSettings()
        s.update(temperature=0.3, n_predict=8192)
        payload = s.to_payload()
        assert payload["temperature"] == 0.3
        assert payload["n_predict"] == 8192

    def test_to_payload_with_stop_sequences(self):
        s = DynamicSettings()
        s.update(stop=["\n\n", "USER:"])
        payload = s.to_payload()
        assert payload["stop"] == ["\n\n", "USER:"]

    def test_to_payload_with_json_schema(self):
        s = DynamicSettings()
        s.json_schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        payload = s.to_payload()
        assert payload["json_schema"] == {"type": "object", "properties": {"x": {"type": "string"}}}

    def test_to_memory_entry(self):
        s = DynamicSettings()
        s.update(temperature=0.3, n_predict=8192)
        entry = s.to_memory_entry()
        assert entry["temperature"] == 0.3
        assert entry["n_predict"] == 8192
        assert entry["update_count"] == 1  # incremented by update()

    def test_update_count_increments(self):
        s = DynamicSettings()
        s.update(temperature=0.3)
        assert s._update_count == 1
        s.update(top_p=0.8)
        assert s._update_count == 2


class TestSettingsOptimizer:
    """Tests for SettingsOptimizer."""

    def test_optimize_for_code_generation(self):
        opt = SettingsOptimizer()
        settings = opt.optimize_for_task(TaskType.CODE_GENERATION, "write a function")
        assert settings.temperature == 0.3
        assert settings.top_p == 0.9
        assert settings.top_k == 20
        assert settings.n_predict == 8192
        assert settings.repeat_penalty == 1.2
        assert settings.cache_prompt is True

    def test_optimize_for_code_review(self):
        opt = SettingsOptimizer()
        settings = opt.optimize_for_task(TaskType.CODE_REVIEW, "review this code")
        assert settings.temperature == 0.1
        assert settings.top_p == 0.8
        assert settings.top_k == 10
        assert settings.n_predict == 2048

    def test_optimize_for_planning(self):
        opt = SettingsOptimizer()
        settings = opt.optimize_for_task(TaskType.PLANNING, "design an architecture")
        assert settings.temperature == 0.5
        assert settings.n_predict == 16384
        assert settings.enable_thinking is True
        assert settings.reasoning_effort == ReasoningEffort.HIGH

    def test_optimize_for_debugging(self):
        opt = SettingsOptimizer()
        settings = opt.optimize_for_task(TaskType.DEBUGGING, "fix this bug")
        assert settings.temperature == 0.2
        assert settings.enable_thinking is True
        assert settings.reasoning_effort == ReasoningEffort.HIGH

    def test_optimize_for_simple_query(self):
        opt = SettingsOptimizer()
        settings = opt.optimize_for_task(TaskType.SIMPLE_QUERY, "what is 2+2?")
        assert settings.temperature == 0.1
        assert settings.n_predict == 1024
        assert settings.cache_prompt is True

    def test_optimize_for_creative_writing(self):
        opt = SettingsOptimizer()
        settings = opt.optimize_for_task(TaskType.CREATIVE_WRITING, "write a story")
        assert settings.temperature == 0.9
        assert settings.top_p == 0.98
        assert settings.top_k == 50
        assert settings.repeat_penalty == 1.0

    def test_optimize_for_data_analysis(self):
        opt = SettingsOptimizer()
        settings = opt.optimize_for_task(TaskType.DATA_ANALYSIS, "analyze this data")
        assert settings.temperature == 0.2
        assert settings.json_schema is not None
        assert settings.json_schema["type"] == "object"

    def test_optimize_for_reasoning(self):
        opt = SettingsOptimizer()
        settings = opt.optimize_for_task(TaskType.REASONING, "think through this problem")
        assert settings.temperature == 0.3
        assert settings.n_predict == 16384
        assert settings.enable_thinking is True
        assert settings.reasoning_effort == ReasoningEffort.HIGH

    def test_optimize_for_default(self):
        opt = SettingsOptimizer()
        settings = opt.optimize_for_task(TaskType.SIMPLE_QUERY, "hello")
        assert settings.temperature == 0.1

    def test_record_metric(self):
        opt = SettingsOptimizer()
        opt.record_metric({"cache_hit_rate": 0.8, "throughput": 100})
        assert len(opt._metric_history) == 1

    def test_record_metric_truncates_history(self):
        opt = SettingsOptimizer()
        for i in range(150):
            opt.record_metric({"cache_hit_rate": 0.5, "throughput": 50})
        assert len(opt._metric_history) == 100

    def test_get_recommendations_empty(self):
        opt = SettingsOptimizer()
        assert opt.get_recommendations() == []

    def test_get_recommendations_planning(self):
        opt = SettingsOptimizer()
        for _ in range(6):
            opt.optimize_for_task(TaskType.PLANNING, "plan something")
        recs = opt.get_recommendations()
        assert any("planning" in r.lower() for r in recs)

    def test_get_recommendations_code_generation(self):
        opt = SettingsOptimizer()
        for _ in range(11):
            opt.optimize_for_task(TaskType.CODE_GENERATION, "write code")
        recs = opt.get_recommendations()
        assert any("temperature" in r.lower() for r in recs)

    def test_to_memory_entry(self):
        opt = SettingsOptimizer()
        opt.optimize_for_task(TaskType.CODE_GENERATION, "write code")
        entry = opt.to_memory_entry()
        assert entry["task_history_count"] == 1
        assert "recommendations" in entry


class TestDetectTaskType:
    """Tests for detect_task_type convenience function."""

    def test_planning_keywords(self):
        assert detect_task_type("design an architecture") == TaskType.PLANNING
        assert detect_task_type("plan the strategy") == TaskType.PLANNING
        assert detect_task_type("architect a solution") == TaskType.PLANNING

    def test_debugging_keywords(self):
        assert detect_task_type("fix this bug") == TaskType.DEBUGGING
        assert detect_task_type("debug the error") == TaskType.DEBUGGING
        assert detect_task_type("error in the code") == TaskType.DEBUGGING

    def test_code_review_keywords(self):
        assert detect_task_type("review this code") == TaskType.CODE_REVIEW
        assert detect_task_type("audit the implementation") == TaskType.CODE_REVIEW
        assert detect_task_type("check for issues") == TaskType.CODE_REVIEW

    def test_code_generation_keywords(self):
        assert detect_task_type("write code") == TaskType.CODE_GENERATION
        assert detect_task_type("implement a function") == TaskType.CODE_GENERATION
        assert detect_task_type("create a new module") == TaskType.CODE_GENERATION
        assert detect_task_type("build a feature") == TaskType.CODE_GENERATION

    def test_data_analysis_keywords(self):
        assert detect_task_type("analyze this data") == TaskType.DATA_ANALYSIS
        assert detect_task_type("statistics on the dataset") == TaskType.DATA_ANALYSIS

    def test_reasoning_keywords(self):
        assert detect_task_type("think through this") == TaskType.REASONING
        assert detect_task_type("explain the reasoning") == TaskType.REASONING

    def test_creative_writing_keywords(self):
        assert detect_task_type("write a story") == TaskType.CREATIVE_WRITING
        assert detect_task_type("write a poem") == TaskType.CREATIVE_WRITING

    def test_simple_query_default(self):
        assert detect_task_type("hello") == TaskType.SIMPLE_QUERY
        assert detect_task_type("what time is it?") == TaskType.SIMPLE_QUERY
        assert detect_task_type("random question") == TaskType.SIMPLE_QUERY

    def test_case_insensitive(self):
        assert detect_task_type("WRITE CODE") == TaskType.CODE_GENERATION
        assert detect_task_type("Fix this BUG") == TaskType.DEBUGGING


class TestGetOptimizer:
    """Tests for get_optimizer singleton."""

    def test_singleton(self):
        opt1 = get_optimizer()
        opt2 = get_optimizer()
        assert opt1 is opt2
