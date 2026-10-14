# Manual Verification - Registry Build Tools

## Objective
Verify that `registry.build_tools()` rebuilds tool definitions from current state on every call, proving no caching of stale schemas.

## Steps - Execute in PowerShell

### 1. Open Python Shell
```powershell
cd d:\Sakshi\driftshield
.venv\Scripts\python.exe
```

### 2. Create Default Registry and Display Initial Tools
```python
from driftshield.healer.registry import create_default_registry
import json

# Create registry with lookup_user tool (v1 contract)
registry = create_default_registry()

# Build and display tool definitions BEFORE patch
print("=== BEFORE PATCH ===")
tools_before = registry.build_tools()
print(f"Tool count: {len(tools_before)}")
print(f"Tool name: {tools_before[0]['name']}")
print(f"Version: {registry.version('lookup_user')}")
print("Body schema:")
print(json.dumps(tools_before[0]['parameters'], indent=2))
```

**Expected Output:**
- Tool count: 1
- Tool name: lookup_user
- Version: 1
- Body schema shows: `{"user_id": {"type": "string"}}`

### 3. Apply Schema Patch
```python
# Get current tool to create patched version
current_tool = registry.get("lookup_user")

# Create patched tool with CHANGED schema (user_id becomes integer)
patched_tool = {
    "name": "lookup_user",
    "description": "Look up a user by ID",
    "operation": "lookup_user",
    "version": 1,  # Will be incremented by apply_patch
    "contract_hash": "patched_hash_123",
    "body_schema": {
        "type": "object",
        "properties": {
            "user_id": {"type": "integer"}  # CHANGED: string -> integer
        },
        "required": ["user_id"],
        "additionalProperties": False
    },
    "required_headers": []
}

# Apply the patch
registry.apply_patch("lookup_user", patched_tool, "schema drift - type change")
print("\n=== PATCH APPLIED ===")
print(f"New version: {registry.version('lookup_user')}")
```

**Expected Output:**
- New version: 2

### 4. Build Tools Again and Display Updated Definitions
```python
# Build tools again - should reflect patch immediately
print("\n=== AFTER PATCH ===")
tools_after = registry.build_tools()
print(f"Tool count: {len(tools_after)}")
print(f"Tool name: {tools_after[0]['name']}")
print(f"Version: {registry.version('lookup_user')}")
print("Body schema:")
print(json.dumps(tools_after[0]['parameters'], indent=2))
```

**Expected Output:**
- Tool count: 1
- Tool name: lookup_user
- Version: 2
- Body schema shows: `{"user_id": {"type": "integer"}}` ← **CHANGED**

### 5. Compare and Exit
```python
# Prove the schema changed
print("\n=== COMPARISON ===")
print(f"BEFORE: user_id type = {tools_before[0]['parameters']['properties']['user_id']['type']}")
print(f"AFTER:  user_id type = {tools_after[0]['parameters']['properties']['user_id']['type']}")
print(f"Schema changed: {tools_before[0]['parameters'] != tools_after[0]['parameters']}")

# Exit Python shell
exit()
```

**Expected Output:**
- BEFORE: user_id type = string
- AFTER: user_id type = integer
- Schema changed: True

---

## One-Liner for Quick Verification

```powershell
.venv\Scripts\python.exe -c "from driftshield.healer.registry import create_default_registry; import json; r = create_default_registry(); before = r.build_tools(); print('BEFORE:', before[0]['parameters']['properties']['user_id']['type'], 'v' + str(r.version('lookup_user'))); r.apply_patch('lookup_user', {'name': 'lookup_user', 'description': 'Look up a user by ID', 'operation': 'lookup_user', 'version': 1, 'contract_hash': 'test', 'body_schema': {'type': 'object', 'properties': {'user_id': {'type': 'integer'}}, 'required': ['user_id']}, 'required_headers': []}, 'test'); after = r.build_tools(); print('AFTER: ', after[0]['parameters']['properties']['user_id']['type'], 'v' + str(r.version('lookup_user'))); print('PROOF: Schema rebuilt without cache =', before[0]['parameters'] != after[0]['parameters'])"
```

---

## What This Proves

### Key Evidence of No Caching:

1. **Version Increments**: Version goes from 1 → 2, confirming patch was applied
2. **Schema Changes Immediately**: `user_id` type changes from `"string"` → `"integer"`
3. **build_tools() Reflects Current State**: Second call shows the patched schema, not cached v1 schema
4. **No Stale Data**: The parameters dict returned by `build_tools()` contains the NEW schema

### Why This Matters:

Per Rule 5 of the build guide:
> "The tool list sent to the LLM is rebuilt from the registry on EVERY model call. Never cache it."

This verification proves:
- ✓ Each `build_tools()` call constructs a fresh list from `self._tools`
- ✓ Schema patches are immediately visible to the LLM
- ✓ No stale cached schemas can cause drift between registry and LLM tools
- ✓ The registry maintains current state, not historical snapshots

### Reversibility:

This verification uses a temporary registry created in-memory. No files are modified. You can:
- Repeat the test any number of times
- Test rollback by adding: `registry.rollback('lookup_user')` and building tools again
- Exit Python shell to discard all changes

---

## Quick Test Result Format

When you run the verification, you should see output like:

```
BEFORE: string v1
AFTER:  integer v2
PROOF: Schema rebuilt without cache = True
```

This single line proves the registry rebuilds tool definitions without caching.
