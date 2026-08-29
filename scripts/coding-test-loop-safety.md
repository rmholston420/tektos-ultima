# Tektos Coding Test: Loop Safety Repetition Detection Bug

## Task
Fix a bug in `src/tektos/runtime/loop_safety.py` where the repetition detection logic has a false positive when the agent makes different tool calls but with the same text output length.

## The Bug
In `_detect_repetition()` (line ~293), Pattern 2 checks if the last 3 snapshots have the same `text_length`:

```python
if len(snapshots) >= 3:
    lengths = [s.text_length for s in snapshots[-3:]]
    if len(set(lengths)) == 1 and lengths[0] > 0:
        return True
```

**The problem:** This triggers a false positive when the agent legitimately produces responses of the same character count (e.g., 3 turns of ~500-char responses). The check should require that the text_length is *unusually* consistent — specifically, it should only flag repetition when the text_length is within a narrow band (±10%) of each other, not when they're exactly equal.

Additionally, the check uses `snapshots[-3:]` but `snapshots` is a `deque`, and the method receives `snapshots` as a `list` parameter. The slice `[-3:]` on a deque works, but the logic should use `len(snapshots)` consistently.

## What Tektos Should Do
1. Read `src/tektos/runtime/loop_safety.py`
2. Identify the false positive in Pattern 2 of `_detect_repetition()`
3. Fix the comparison to use a tolerance band (±10%) instead of exact equality
4. Ensure the fix doesn't break the other two repetition patterns
5. Write a test that demonstrates the bug and verifies the fix

## Success Criteria
- The exact-equality check is replaced with a tolerance-based check (±10%)
- Pattern 1 (tool sequence matching) still works correctly
- Pattern 3 (textless tool loops) still works correctly
- A new test case proves that 3 turns with similar-length outputs (e.g., 490, 500, 510 chars) do NOT trigger false positive
- A test case proves that 3 turns with identical-length outputs (e.g., 500, 500, 500 chars) still triggers detection

## Evaluation
Tektos will be evaluated on:
- **Code reading**: Can it understand the existing logic and identify the bug?
- **Fix quality**: Is the tolerance band implemented correctly without breaking other patterns?
- **Testing**: Does it write proper tests that cover both the bug and regression?
- **Precision**: Does it make minimal changes (only what's needed)?
