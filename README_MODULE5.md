# DriftShield Module 5 - Patcher and Guard

## Files Created

### driftshield/healer/patcher.py
Argument adaptation and registry snapshot generation with lossless conversions.

**Function:** `adapt(args, changes) -> AdaptResult`

Transforms agent's original arguments to match new schema.

**Process:**
1. **Tag original values**: All values start as `original_arg`
2. **Apply changes**:
   - **rename/nesting**: Move value to new path, tag as `converted`
   - **type_change**: Convert if lossless, else error
   - **new_required_field**: ERROR (no source)
   - **ambiguous**: ERROR (cannot guess)
   - **new_header**: Add to `needed_headers` list
3. **Return AdaptResult** with:
   - `payload`: Transformed arguments
   - `provenance`: Origin tag for each leaf value
   - `needed_headers`: List of headers to resolve
   - `error`: Error message if adaptation failed

**Lossless Conversions:**
- ✓ String of digits → Integer: `"123"` → `123`
- ✓ Integer → String: `123` → `"123"`
- ✗ Non-numeric string → Integer: `"abc"` → ERROR
- ✗ Float string → Integer: `"12.5"` → ERROR
- ✗ Any other conversion → ERROR

**Function:** `build_new_snapshot(old_tool, changes, live_contract) -> Tool | None`

Creates new registry snapshot by applying changes.

**Process:**
1. Copy old tool structure
2. Replace `body_schema` and `required_headers` with live contract versions
3. Update `contract_hash` to live contract hash
4. **Verify** result matches live contract exactly
5. If mismatch → return None (incomplete diff)

This ensures the patch is complete and correct.

---

### driftshield/healer/guard.py
Value origin verification and header resolution with strict safety rules.

**Function:** `resolve_headers(needed_headers, get_value) -> (headers, provenance, missing)`

Resolves header values ONLY from config.

**Rules:**
- NEVER takes values from LLM
- NEVER takes values from error messages
- ONLY uses `config.get_header_value()` (or custom getter)
- Missing headers go in `missing` list for human intervention

**Returns:**
- `headers`: Name → value for resolved headers
- `provenance`: Name → "config" origin tag
- `missing`: List of unresolved header names

**Function:** `check_provenance(payload, provenance) -> bool`

Verifies EVERY leaf value has a valid origin tag.

**Valid Origins:**
- `original_arg` - From agent's original call
- `converted` - Losslessly transformed
- `config` - From environment/config
- `human` - Human-provided (for future use)

**Rejection Criteria:**
- ✗ Any leaf value without provenance tag
- ✗ Any invalid origin tag
- ✗ Partial tagging (some values tagged, some not)

**Critical:** Any untagged value is considered **invented** and REJECTED.

This prevents the healer from making up values.

---

## Tests Created

### tests/test_patcher.py (18 tests, all passing)

**Adaptation Tests:**

1. ✓ **test_adapt_v1_to_v2_full**
   - Args: `{"user_id": "123"}`
   - Result: `{"target": {"id": 123}}`
   - Provenance: `target.id` = `converted`
   - Headers: `[X-Tenant-Token]`

2. ✓ **test_adapt_non_numeric_user_id_fails**
   - Args: `{"user_id": "abc"}`
   - type_int contract requires integer
   - Error: Cannot losslessly convert

3. ✓ **test_adapt_ambiguous_fails**
   - ambiguous contract: user_id → ref_a or ref_b?
   - Error: Ambiguous change

4. ✓ **test_adapt_rename_preserves_value**
   - rename_id: user_id → id
   - Value preserved, tagged as converted

5. ✓ **test_adapt_nesting_creates_structure**
   - nest_target: user_id → target.id
   - Creates nested structure

6. ✓ **test_adapt_lossless_int_to_string**
   - String "123" → Integer 123
   - Lossless conversion

7. ✓ **test_adapt_multiple_changes**
   - combo contract: nesting + type + header
   - All changes applied correctly

**Guard Tests:**

8. ✓ **test_resolve_headers_from_config**
   - X-Tenant-Token resolved from config
   - Value: "test-tenant-token-123"
   - Origin: "config"

9. ✓ **test_resolve_headers_missing**
   - X-Billing-Region not in config
   - Goes in `missing` list

10. ✓ **test_check_provenance_rejects_untagged_value**
    - Payload has `invented_field` with no provenance
    - REJECTED

11. ✓ **test_check_provenance_accepts_fully_tagged**
    - All values have provenance
    - ACCEPTED

12. ✓ **test_check_provenance_with_nested_structure**
    - Deeply nested payload
    - All leaves tagged
    - ACCEPTED

13. ✓ **test_check_provenance_rejects_partial_tagging**
    - field1 tagged, field2 not tagged
    - REJECTED

14. ✓ **test_check_provenance_accepts_multiple_origins**
    - original_arg, converted, config, human
    - All valid origins
    - ACCEPTED

15. ✓ **test_check_provenance_rejects_invalid_origin**
    - Invalid origin tag: "invented"
    - REJECTED

16. ✓ **test_resolve_headers_custom_getter**
    - Custom getter function
    - Works correctly

**Snapshot Tests:**

17. ✓ **test_build_new_snapshot_matches_contract**
    - New snapshot matches live contract exactly
    - body_schema, required_headers, contract_hash all match

18. ✓ **test_build_new_snapshot_unchanged_fields_preserved**
    - name, description, operation unchanged
    - Minimal patch test

---

## Running Tests

```bash
# Module 5 tests only
.venv\Scripts\python.exe -m pytest tests\test_patcher.py -v

# All tests (61 total)
.venv\Scripts\python.exe -m pytest tests\ -v
```

## Test Results

```
================================ 61 passed in 5.93s =================================
```

All tests passing:
- 8 mock_api tests ✓
- 12 registry tests ✓
- 9 classifier tests ✓
- 14 differ tests ✓
- 18 patcher/guard tests ✓ (NEW)

---

## Key Design Decisions

### 1. Lossless Conversions Only

**Allowed:**
```python
"123" → 123  # String of digits to int
123 → "123"  # Int to string
```

**Rejected:**
```python
"abc" → ???  # Not numeric - REJECT
"12.5" → ??? # Decimal - REJECT
```

This ensures no data loss or misinterpretation.

### 2. Every Value Must Have Provenance

The guard tracks the origin of EVERY leaf value:

```python
payload = {"target": {"id": 123}}
provenance = {"target.id": "converted"}  # From user_id

# Without provenance = INVENTED = REJECT
```

This is Rule 3 from the build guide: "A patch may only rearrange or losslessly convert values that already exist in the original call, or read values from config."

### 3. Headers Only From Config

```python
# ✓ ALLOWED
config.get_header_value("X-Tenant-Token")
# → ("test-tenant-token-123", "config")

# ✗ FORBIDDEN
# - Reading from LLM output
# - Reading from error messages
# - Guessing or inventing values
```

If a header isn't in config, it goes to `missing` for human intervention.

### 4. Snapshot Verification

`build_new_snapshot` verifies the result matches live contract:

```python
new_tool["body_schema"] == live_contract["body_schema"]
new_tool["required_headers"] == live_contract["required_headers"]
```

If not, returns None (incomplete diff).

This ensures we never apply a partial or incorrect patch.

### 5. Ambiguous Changes Rejected

When differ emits `ambiguous` change:
```python
removed: "user_id"
candidates: ["ref_a", "ref_b"]
```

The patcher returns ERROR - cannot choose which candidate without guessing.

This prevents the healer from inventing mappings.

---

## Compliance with Build Rules

### Rule 3: "Never invent a value"
✓ `check_provenance` rejects any untagged value
✓ `adapt` errors on new_required_field (no source)
✓ `adapt` errors on ambiguous (cannot guess mapping)

### Rule 4: "Patch minimally"
✓ `build_new_snapshot` preserves name, description, operation
✓ Only changes body_schema, required_headers, contract_hash

### Rule 7: "Never log secret values"
✓ Headers resolved but values tracked separately
✓ Provenance logs origin, not value

### Rule 8: "Healing is deterministic code"
✓ All logic is pure functions
✓ No randomness, no LLM calls in healing

### Rule 9: "Plain Python with type hints"
✓ All functions typed
✓ Short, focused functions with clear responsibilities

---

## Value Origin Flow

```
Original Call:
{"user_id": "123"}  → provenance: {"user_id": "original_arg"}

After Adaptation (v1 → v2_full):
{"target": {"id": 123}}  → provenance: {"target.id": "converted"}

Header Resolution:
X-Tenant-Token: "test-token"  → provenance: {"X-Tenant-Token": "config"}

Guard Check:
✓ All leaves have valid origin tags
✓ No invented values
✓ Patch is safe to apply
```

---

## Error Cases

### Lossy Conversion
```python
adapt({"user_id": "abc"}, type_int_changes)
→ ERROR: "Cannot losslessly convert user_id from string to integer with value abc"
```

### Ambiguous Mapping
```python
adapt({"user_id": "123"}, ambiguous_changes)
→ ERROR: "Ambiguous change: user_id could map to ['ref_a', 'ref_b']"
```

### New Required Field
```python
adapt(args, [{"type": "new_required_field", "path": "extra"}])
→ ERROR: "New required field extra has no source value"
```

### Missing Header
```python
resolve_headers(["X-Billing-Region"])
→ missing: ["X-Billing-Region"]
# Human intervention required
```

### Untagged Value (Invented)
```python
check_provenance(
  {"user_id": "123", "invented": "value"},
  {"user_id": "original_arg"}
)
→ False (invented field has no provenance)
```

---

## Next Steps

Ready for:
- **retry.py** - Retry logic with budget (5 API, 8 model calls)
- **Integration** - Combine all healer components
- **End-to-end tests** - Full drift scenarios

The patcher and guard form the core safety layer, ensuring patches never invent values and always maintain provenance.
