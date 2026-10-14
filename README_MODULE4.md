# DriftShield Module 4 - Schema Differ

## Files Created

### driftshield/healer/differ.py
Schema difference detection with intelligent pairing and change classification.

**Function:** `diff(old_tool, live_contract) -> list[Change]`

Compares registry tool's body_schema and required_headers with live contract.

**Algorithm:**

1. **Flatten schemas** to leaf paths:
   - `{"user_id": {"type": "string"}}` → `{("user_id",): "string"}`
   - `{"target": {"id": {"type": "integer"}}}` → `{("target", "id"): "integer"}`

2. **Identify changes**:
   - `removed` = old paths not in new
   - `added` = new paths not in old
   - `common` paths with different types → type_change

3. **Pair removed/added paths (three strategies)**:
   
   **a) Declared mappings (tier 1):**
   - If live_contract.mappings contains `{from: "user_id", to: "target.id"}`
   - Pair user_id with target.id
   - This is from the contract itself (highest confidence)
   
   **b) Inference (tier 2):**
   - If exactly ONE path removed AND exactly ONE path added
   - AND they have the SAME type
   - Infer they are paired (rename or nesting)
   
   **c) Ambiguous (no pairing):**
   - Multiple removed or multiple added
   - OR single removed + single added with DIFFERENT types
   - Emit `ambiguous` change with candidates
   - Do NOT guess - requires human intervention

4. **Classify paired changes**:
   - **rename**: Only last path segment changed (user_id → id)
   - **nesting**: Parent path changed (user_id → target.id)
   - **both**: Emit nesting (takes precedence)
   - If types also differ, emit separate type_change

5. **Detect unpaired additions**:
   - Added required fields with no pairing → `new_required_field`
   - These need a value source (cannot be invented)

6. **Header changes**:
   - New headers in live → `new_header`
   - Removed headers → `removed_header`

**Change Types:**
- `rename` - Field renamed (same parent, different name)
- `nesting` - Field moved to different parent path
- `type_change` - Type changed (string → integer)
- `new_required_field` - New field added (needs value source)
- `new_header` - New required header
- `removed_header` - Header no longer required
- `ambiguous` - Cannot determine mapping (multiple candidates)

**Tier System:**
- **Tier 1**: From declared mapping or contract itself (high confidence)
- **Tier 2**: Inferred by unique-pair rule (medium confidence)

## Tests Created

### tests/test_differ.py (14 tests, all passing)

**Tests per contract name:**

1. ✓ **test_diff_equal_schemas_returns_empty**
   - v1 tool vs v1 contract → no changes

2. ✓ **test_diff_rename_id**
   - rename_id contract: user_id → id
   - Assert rename change, tier=1 (from mapping)

3. ✓ **test_diff_type_int**
   - type_int contract: string → integer
   - Assert type_change

4. ✓ **test_diff_nest_target**
   - nest_target contract: user_id → target.id
   - Assert nesting change, tier=1 (from mapping)

5. ✓ **test_diff_header_tenant**
   - header_tenant contract: adds X-Tenant-Token
   - Assert new_header

6. ✓ **test_diff_v2_full**
   - v2_full contract: nesting + type_change + new_header
   - Assert all three changes detected

7. ✓ **test_diff_combo**
   - combo contract: same as v2_full
   - Assert nesting + type_change + new_header

8. ✓ **test_diff_header_billing**
   - header_billing contract: adds X-Billing-Region
   - Assert new_header

9. ✓ **test_diff_ambiguous**
   - ambiguous contract: user_id removed, ref_a and ref_b added, NO mappings
   - Assert ambiguous change with candidates

**Additional edge case tests:**

10. ✓ **test_diff_inferred_pairing_same_type**
    - Single removed + single added, same type, no mapping
    - Assert rename with tier=2 (inferred)

11. ✓ **test_diff_no_pairing_different_types**
    - Single removed + single added, DIFFERENT types
    - Assert NO pairing, ambiguous instead

12. ✓ **test_diff_removed_header**
    - Header removed from requirements
    - Assert removed_header

13. ✓ **test_diff_new_required_field**
    - New field added to required list
    - Assert new_required_field

14. ✓ **test_diff_deeply_nested_paths**
    - level1.level2.field type change
    - Assert correct dotted path notation

## Running Tests

```bash
# Module 4 tests only
.venv\Scripts\python.exe -m pytest tests\test_differ.py -v

# All tests (43 total)
.venv\Scripts\python.exe -m pytest tests\ -v
```

## Test Results

```
================================ 43 passed in 5.55s =================================
```

All tests passing:
- 8 mock_api tests ✓
- 12 registry tests ✓
- 9 classifier tests ✓
- 14 differ tests ✓ (NEW)

## Key Design Decisions

### 1. Tier System for Confidence
- **Tier 1**: Declared mappings or contract-derived (100% confidence)
- **Tier 2**: Inferred by unique-pair heuristic (high confidence, but not certain)

This allows patcher/guard to make different decisions based on confidence level.

### 2. Ambiguous = No Guessing
When faced with multiple candidates or type mismatches, the differ emits `ambiguous` change.

**Example:** user_id removed, ref_a and ref_b added with no mapping
- Could be either one, we don't know
- Emit ambiguous with candidates list
- Patcher/guard will reject this (cannot invent values)

### 3. Flattening to Leaf Paths
Schemas are flattened to paths like `("target", "id")` for comparison.

**Benefits:**
- Handles arbitrary nesting depth
- Makes path comparison simple
- Easy to convert to dotted notation for display

### 4. Type Changes Stand Alone
Even in paired changes, type differences are separate events.

**Example:** user_id (string) → target.id (integer)
- Emit: nesting change (user_id → target.id)
- Emit: type_change (string → integer)

This allows patcher to handle each concern independently.

### 5. New Required Fields Need Value Sources
Added fields that are required cannot be patched if they have no source.

The differ marks them as `new_required_field` so the guard can reject patches that would need to invent values.

## Algorithm Highlights

### Path Flattening
```python
{
  "properties": {
    "target": {
      "type": "object",
      "properties": {
        "id": {"type": "integer"}
      }
    }
  }
}
```
Becomes:
```python
{("target", "id"): "integer"}
```

### Pairing Strategy
```
Removed: [user_id]
Added: [target.id]
Mapping: {from: "user_id", to: "target.id"}

→ Tier 1 pairing: user_id ↔ target.id
```

```
Removed: [old_field]
Added: [new_field]
No mapping, but both are "string"

→ Tier 2 pairing: old_field ↔ new_field (inferred)
```

```
Removed: [user_id]
Added: [ref_a, ref_b]
No mapping

→ Ambiguous: cannot choose between candidates
```

### Change Classification
```python
# Rename: same depth, different name
user_id → id
# Path: ("user_id",) → ("id",)
# Only last segment changed

# Nesting: different depth or parent
user_id → target.id
# Path: ("user_id",) → ("target", "id")
# Parent changed
```

## Compliance with Build Rules

### Rule 3: "A patch may only rearrange or losslessly convert values"
✓ Differ detects when new required fields appear with no source (new_required_field)
✓ Guard will use this to reject patches that would invent values

### Rule 8: "Healing is deterministic code"
✓ All diff logic is pure function - no randomness, no LLM calls

### Rule 9: "Plain Python with type hints, short functions"
✓ Helper functions for flattening, path conversion, classification
✓ All functions typed and documented

## Next Steps

Ready for:
- **patcher.py** - Generate patches from diff changes
- **guard.py** - Validate patches don't invent values
- **retry.py** - Retry logic with budget tracking

The differ provides the foundational analysis that patcher and guard will use to safely heal schema drift.
