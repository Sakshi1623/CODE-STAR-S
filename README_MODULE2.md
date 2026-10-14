# DriftShield Module 2 - Registry and Logging

## Files Created

### driftshield/config.py
- Loads `.env` file with python-dotenv
- Exposes `BASE_URL` (default: http://localhost:8000)
- `get_header_value(header_name)` maps known headers to environment variables
  - `X-Tenant-Token` → `TENANT_TOKEN` env var
  - Unknown headers return `None` (e.g., `X-Billing-Region`)
- Returns tuple `(value, "config")` or `None`

### driftshield/healer/registry.py
- `ToolRegistry` class holds versioned tool definitions
- Each tool: name, description, operation, version, contract_hash, body_schema, required_headers
- Methods:
  - `register(tool)` - Register or update a tool
  - `get(name)` - Retrieve tool by name
  - `build_tools()` - Build fresh function-calling list (NO caching)
  - `apply_patch(name, new_snapshot, reason)` - Bump version, save history
  - `rollback(name)` - Restore previous version, version still increases
  - `version(name)` - Get current version number
- `create_default_registry()` - Creates registry with `lookup_user` tool matching contract v1
- Versions always increase (never decrease), even on rollback

### driftshield/healer/log.py
- Append-only JSON lines file: `patch_log.jsonl`
- `log_event(dict)` - Adds UTC timestamp, redacts secrets, writes one line
- Redacts keys named: `value`, `token`, `secret` → `"<redacted>"`
- Recursive redaction through nested dicts and lists
- `read_all()` - Returns all logged events

### .env
```
BASE_URL=http://localhost:8000
TENANT_TOKEN=test-tenant-token-123
```

## Tests Created

### tests/test_registry.py (12 tests, all passing)

1. ✓ `test_registry_register_and_get` - Basic register and retrieve
2. ✓ `test_build_tools_reflects_patch_immediately` - No caching, immediate reflection
3. ✓ `test_version_increases_on_patch` - Version 1 → 2 → 3 on patches
4. ✓ `test_version_increases_on_rollback` - Version increases even on rollback
5. ✓ `test_rollback_restores_old_schema` - Body schema restored correctly
6. ✓ `test_rollback_without_history_raises` - Raises KeyError when no history
7. ✓ `test_log_redacts_secrets` - Redacts value, token, secret keys
8. ✓ `test_log_redacts_nested_secrets` - Recursive redaction in nested structures
9. ✓ `test_create_default_registry` - Default registry has lookup_user
10. ✓ `test_build_tools_no_caching` - Returns fresh list every time
11. ✓ `test_config_get_header_value` - Maps X-Tenant-Token, returns None for unknown
12. ✓ `test_config_base_url` - Loads BASE_URL from .env

## Running Tests

```bash
# Module 2 tests only
.venv\Scripts\pytest tests\test_registry.py -v

# All tests (20 total)
.venv\Scripts\pytest tests\ -v
```

## Test Results

```
================================ 20 passed in 1.34s =================================
```

All Phase 1 (8 tests) + Module 2 (12 tests) passing.

## Key Design Decisions

1. **Version Management**: Versions monotonically increase, even on rollback. This ensures audit trail integrity.

2. **No Caching**: `build_tools()` builds fresh list every call to ensure LLM always sees current state.

3. **Secret Redaction**: Case-insensitive matching on `value`, `token`, `secret` keys, recursive through nested structures.

4. **Config Strategy**: Only known headers mapped to env vars. Unknown headers (like X-Billing-Region) return `None` as required for guard logic.

5. **History Management**: Previous versions stored in list per tool, enabling rollback with full history.

## Dependencies Added

- `python-dotenv>=1.0.0` for .env loading
