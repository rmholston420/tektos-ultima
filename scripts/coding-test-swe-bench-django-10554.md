# Tektos Coding Test: SWE-bench Style Task

## Task: Fix Django Union QuerySet Ordering Bug

### Background
This is a real-world bug from the Django project (GitHub issue #29834, SWE-bench task `django__django-10554`). It tests whether Tektos can:
1. Understand a bug report with reproduction steps
2. Navigate a large codebase to find the root cause
3. Write a correct fix that passes existing tests

### The Bug
When using `QuerySet.union()` with `order_by()` on one of the combined querysets, subsequent operations like `.order_by()` or `.values_list()` on the union result cause a `ProgrammingError` because Django generates an invalid `ORDER BY` clause referencing a column position that doesn't exist in the union's select list.

### Reproduction
```python
>>> Dimension.objects.values_list('id', flat=True)
<QuerySet [10, 11, 12, 13, 14, 15, 16, 17, 18]>
>>> qs = (Dimension.objects.filter(pk__in=[10, 11]).union(
...     Dimension.objects.filter(pk__in=[16, 17]).order_by('order')))
>>> qs
<QuerySet [<Dimension: boeksoort>, <Dimension: grootboek>, ...>]
# this causes re-evaluation of the original qs to break
>>> qs.order_by().values_list('pk', flat=True)
<QuerySet [16, 11, 10, 17]>
>>> qs[0]  # breaks
```

Error: `django.db.utils.ProgrammingError: ORDER BY position 4 is not in select list`

### What Tektos Should Do
1. Clone the Django repository at the commit before the fix
2. Reproduce the bug
3. Find the root cause in `django/db/models/sql/compiler.py`
4. Write a fix that ensures the union's ORDER BY clause uses valid column references
5. Run the test suite to verify the fix passes without breaking existing tests

### Success Criteria
- The reproduction case no longer raises `ProgrammingError`
- The test `test_union_with_values_list_and_order` passes
- The test `test_union_with_values_list_on_annotated_and_unannotated` passes
- No existing tests are broken by the fix

### Evaluation
Tektos will be evaluated on:
- **Understanding**: Does it correctly interpret the bug report?
- **Navigation**: Can it find the relevant code in a 100K+ line codebase?
- **Fix quality**: Is the fix minimal, correct, and non-regressive?
- **Verification**: Does it actually run tests and confirm they pass?
