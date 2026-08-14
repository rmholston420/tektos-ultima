# Benchmarking Best Practices

## Principles

### Measure What Matters
- Benchmarking is useless if you measure the wrong thing.
- Focus on metrics that correlate with user value: time-to-solution, correctness, cost.
- Don't optimize for metrics that don't matter (e.g., raw throughput if quality drops).

### Reproducibility
- Every benchmark must be deterministic (or account for randomness).
- Fix all random seeds.
- Control for system load, temperature, and hardware state.
- Document the exact environment (OS, drivers, hardware, model versions).

### Comparison Fairness
- Compare apples to apples — same inputs, same hardware, same conditions.
- Use the same evaluation criteria across all variants.
- Blind evaluation when possible (reviewer doesn't know which variant produced what).

---

## Benchmark Design

### Benchmark Categories
1. **Performance** — How fast? (latency, throughput, memory)
2. **Quality** — How good? (accuracy, relevance, completeness)
3. **Efficiency** — How much resource? (tokens, cost, energy)
4. **Reliability** — How consistent? (pass rate, flakiness, error rate)

### Benchmark Structure
```python
@dataclass
class BenchmarkResult:
    name: str
    variant: str
    model: str
    input_count: int
    avg_latency_ms: float
    p99_latency_ms: float
    throughput_per_sec: float
    quality_score: float  # 0-1, from evaluation
    cost_per_100: float
    success_rate: float
    timestamp: str
    environment: dict  # GPU, drivers, OS, etc.
```

---

## Performance Benchmarking

### Latency Measurement
```python
import time
from statistics import median, p99

def benchmark(fn, n_iterations=100, warmup=10):
    # Warmup
    for _ in range(warmup):
        fn()

    # Measure
    latencies = []
    for _ in range(n_iterations):
        start = time.perf_counter_ns()
        fn()
        latencies.append((time.perf_counter_ns() - start) / 1e6)  # ms

    return {
        "mean": sum(latencies) / len(latencies),
        "median": median(latencies),
        "p99": p99(latencies),
        "min": min(latencies),
        "max": max(latencies),
    }
```

### Throughput Measurement
```python
import asyncio

async def benchmark_throughput(fn, concurrency=1, n_requests=1000):
    """Measure how many requests per second."""
    async with asyncio.Semaphore(concurrency):
        start = time.perf_counter()
        tasks = [fn() for _ in range(n_requests)]
        await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
    return n_requests / elapsed  # requests/sec
```

### Memory Measurement
```python
import tracemalloc

def benchmark_memory(fn):
    tracemalloc.start()
    fn()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "current_bytes": current,
        "peak_bytes": peak,
        "peak_mb": peak / (1024 * 1024),
    }
```

---

## Quality Benchmarking

### Evaluation Criteria
| Criterion | Description | Scoring |
|-----------|-------------|---------|
| Correctness | Does it work? | Binary: pass/fail |
| Completeness | Did it do everything? | 0-1 ratio |
| Efficiency | Did it use reasonable resources? | 0-1 score |
| Readability | Is the output code clean? | 1-5 scale |
| Safety | No security issues? | Binary: pass/fail |

### Automated Evaluation
```python
def evaluate_code(output: str, spec: str) -> dict:
    """Evaluate code against specification."""
    return {
        "spec_violations": check_spec_violations(output, spec),
        "test_pass_rate": run_tests(output),
        "style_score": check_style(output),
        "security_score": check_security(output),
        "overall_score": weighted_average([
            ("spec", 0.4),
            ("tests", 0.3),
            ("style", 0.15),
            ("security", 0.15),
        ]),
    }
```

### Human Evaluation (when automated isn't enough)
- Use blinded review (reviewer doesn't know variant)
- Multiple reviewers, average scores
- Inter-rater reliability (Cohen's kappa > 0.8)
- Clear scoring rubrics

---

## Cost Benchmarking

### Token Economy
```python
def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost based on model pricing."""
    pricing = {
        "gpt-4": {"input": 0.03, "output": 0.06},  # per 1K tokens
        "claude-sonnet": {"input": 0.003, "output": 0.015},
    }
    prices = pricing[model]
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1000
```

### Efficiency Metrics
- **Tokens per task** — Lower is better
- **Cost per successful task** — Lower is better
- **Time per successful task** — Lower is better
- **Cost per unit of quality** — Lower is better

---

## Benchmarking Workflow

### Step-by-Step Process
1. **Define objective** — What are we trying to prove or discover?
2. **Design benchmark** — Inputs, metrics, evaluation criteria
3. **Control environment** — Fix hardware, software, randomness
4. **Run warmup** — Eliminate cold-start bias
5. **Run benchmark** — Multiple iterations, randomize order
6. **Collect results** — All metrics, not just the ones you want
7. **Analyze** — Statistics, not just averages
8. **Report** — Transparent, reproducible, honest

### Statistical Analysis
```python
from scipy import stats

def compare_benchmarks(a: list[float], b: list[float]) -> dict:
    """Compare two benchmark series."""
    t_stat, p_value = stats.ttest_ind(a, b)
    return {
        "mean_a": sum(a) / len(a),
        "mean_b": sum(b) / len(b),
        "p_value": p_value,
        "significant": p_value < 0.05,
        "effect_size": abs(sum(a) / len(a) - sum(b) / len(b)) / max(sum(a) / len(a), 1),
    }
```

---

## Common Pitfalls

### Pitfall 1: Cherry-Picking
- Don't show only the best runs.
- Show the full distribution.
- Report worst case, not just average.

### Pitfall 2: Ignoring Warmup
- First few runs are always slower (cold cache, JIT compilation).
- Always warm up before measuring.

### Pitfall 3: Confounding Variables
- If you change multiple things at once, you can't tell what caused the difference.
- Change one variable at a time.

### Pitfall 4: Small Sample Sizes
- 3 runs is not a benchmark. Use at least 50.
- Report confidence intervals.

### Pitfall 5: Optimizing for the Benchmark
- If you're optimizing for throughput but users care about latency, you're optimizing the wrong thing.
- Always align metrics with actual user needs.

---

## Tektos-Specific Benchmarks

### Self-Improvement Loop
- Track: lessons per session, improvement trajectory, model performance over time
- Metric: `quality_improvement_rate` — does the system get better?

### Session Quality
- Track: success rate, time-to-solution, test coverage generated
- Metric: `average_session_quality` — how good are completed sessions?

### Resource Efficiency
- Track: GPU utilization, memory usage, token consumption per session
- Metric: `efficiency_score` — quality per unit of resource

---

*Last updated: 2026-08-14*
