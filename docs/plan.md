# Plan: Improve nipoppy test suite with parametrization and boundary conditions

## Context

The nipoppy test suite has 532 tests across 55 files and already uses `@pytest.mark.parametrize` extensively (~268 instances). However, review found several concrete opportunities: tests that repeat identical patterns without parametrization, a test that never runs due to a naming bug, and missing boundary condition coverage for edge cases the code actually handles.

## Changes

### 1. Fix bug: rename `get_participants_sessions` -> `test_get_participants_sessions`

**File:** `tests/unit/tabular/test_manifest.py:140`

The function is missing the `test_` prefix so pytest never collects it. Simply rename it.

### 2. Add boundary cases to `test_check_participant_id` and `test_check_session_id`

**File:** `tests/unit/utils/test_bids.py`

Add parametrize cases for:
- Empty string `""` (after prefix removal, `"sub-"` becomes `""` -> `"".isalnum()` is False -> should raise)
- Already-stripped empty string `""` directly

These are real edge cases the code handles at `bids.py:70`.

### 3. Add boundary cases to `test_apply_substitutions_to_json`

**File:** `tests/unit/utils/test_utils.py`

Add parametrize cases for:
- Empty substitutions dict `{}` -> returns input unchanged
- Multiple occurrences of the same key in values
- Substitution value containing JSON-special chars (backslash) -- verifying it round-trips correctly

### 4. Add boundary cases to `test_process_template_str`

**File:** `tests/unit/utils/test_utils.py`

Add parametrize cases for:
- Empty string -> returns empty string
- String with no template patterns -> returns unchanged (already tested with `"no_replace"`, but add `""`)
- Multiple occurrences of same placeholder in one string

### 5. Add boundary cases to `test_add_path_suffix`

**File:** `tests/unit/utils/test_utils.py`

Add parametrize case for:
- Path with multiple extensions (e.g., `"file.tar.gz"`)

### 6. Add boundary case to `test_get_diff`: empty self

**File:** `tests/unit/tabular/test_base.py`

Add parametrize case for:
- Empty self, non-empty other -> returns empty (0 rows in self means 0 in diff)

### 7. Add boundary case to `test_add_or_update_records`: empty records list

**File:** `tests/unit/tabular/test_base.py`

Add parametrize case for:
- `to_add=[]` -> tabular unchanged

### 8. Add empty-list boundary to `test_get_imaging_subset`

**File:** `tests/unit/tabular/test_manifest.py`

Add parametrize case for:
- All rows have empty datatype lists `[]` -> returns 0 rows regardless of session_id

### 9. Parametrize `test_model_status_invalid`

**File:** `tests/unit/tabular/test_processing_status.py`

The `test_model_bids_id` and `test_model_status` are already well-structured parametrized tests. The real improvement is parametrizing `test_model_status_invalid` with multiple invalid values:

- `"BAD_STATUS"`, `""`, `"SUCCESS"` (wrong case)

### 10. Add `test_add_bind_arg` boundary case: mode=None

**File:** `tests/unit/test_container.py`

Add parametrize case for `mode=None` -> bind arg should not include mode suffix.

## Files to modify

1. `tests/unit/tabular/test_manifest.py` - fix naming bug, add boundary cases
2. `tests/unit/utils/test_bids.py` - add empty string boundary cases
3. `tests/unit/utils/test_utils.py` - add boundary cases to substitution/template/path tests
4. `tests/unit/tabular/test_base.py` - add empty-data boundary cases
5. `tests/unit/tabular/test_processing_status.py` - parametrize invalid status test
6. `tests/unit/test_container.py` - add mode=None boundary case

## Verification

```bash
pytest tests/unit/tabular/test_manifest.py tests/unit/utils/test_bids.py tests/unit/utils/test_utils.py tests/unit/tabular/test_base.py tests/unit/tabular/test_processing_status.py tests/unit/test_container.py -v
```

Confirm all new tests pass, and the previously-hidden `test_get_participants_sessions` now runs.
