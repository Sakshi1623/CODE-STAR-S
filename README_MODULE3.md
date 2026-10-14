# DriftShield Module 3 - Interceptor and Classifier

## Files Created

### driftshield/healer/interceptor.py
HTTP interceptor that wraps tool calls with comprehensive error handling.

**Function:** `call_tool(client, registry_tool, tool_name, args, extra_headers) -> CallResult`

- **client**: httpx.Client or FastAPI TestClient
- **registry_tool**: Tool definition from registry
- **tool_name**: Name of tool being called
- **args**: Arguments to send as JSON body
- **extra_headers**: Additional HTTP headers

**CallResult fields:**
- `ok` (bool): Success indicator
- `status` (int | None): HTTP status code or None on network error
- `body` (dict | None): Response body as JSON
- `headers` (dict): Response headers
- `request` (dict): Request body and redacted header names
- `elapsed_seconds` (float): Request duration
- `network_error` (str | None): Error message for connection/timeout failures

**Key behaviors:**
- Never raises exceptions - all errors captured in CallResult
- Redacts header VALUES in request info (keeps names)
- Catches httpx.ConnectError, TimeoutException, NetworkError
- Times every request
- Posts to `BASE_URL/users/lookup`

### driftshield/healer/classifier.py
Classifies tool call failures to distinguish drift from other errors.

**Function:** `classify(result, registry_tool, fetch_live_contract) -> Classification`

**Classification rules (in order):**
1. **network_error set OR status >= 500** → `network`
2. **status 401 or 403** → `auth`
3. **status 400 or 422** → Fetch live contract:
   - If content_hash differs AND (body_schema OR required_headers differ) → `drift`
   - If registry already matches live contract → `invalid_data`
4. **Anything else** → `unknown`

**Classification fields:**
- `kind`: One of "drift", "invalid_data", "auth", "network", "unknown"
- `evidence`: Dict with hashes compared, status, differences
- `live_contract`: Current contract from API (or None)

**Critical rule:** Status code alone NEVER decides drift. The classifier must:
1. Fetch the live contract via GET /schema
2. Compare content_hash
3. If hashes differ, verify body_schema or required_headers actually differ
4. Only classify as drift if real differences exist

This prevents false positives where registry is already up-to-date but data is invalid.

## Tests Created

### tests/test_classifier.py (9 tests, all passing)

1. ✓ **test_drift_detected_when_api_schema_changes**
   - Mutate API to v2_full
   - Send v1 request
   - Assert kind="drift"
   - Assert hashes differ and schema/headers differ

2. ✓ **test_invalid_data_when_registry_matches_contract**
   - Both API and registry on v1
   - Send {"user_id": 123} (integer, not string)
   - Assert kind="invalid_data"
   - Assert registry_hash == live_hash

3. ✓ **test_auth_error_on_expired_token**
   - Fault mode: expired_token
   - Send request
   - Assert kind="auth", status=401

4. ✓ **test_network_error_on_server_down**
   - Fault mode: server_down
   - Send request
   - Assert kind="network", status=503

5. ✓ **test_network_error_on_connection_failure**
   - Client pointing to closed port (localhost:9999)
   - Send request
   - Assert kind="network", status=None, network_error set

6. ✓ **test_call_tool_redacts_header_values**
   - Send request with X-Secret-Token header
   - Assert header name present but value="<redacted>"

7. ✓ **test_call_tool_tracks_elapsed_time**
   - Make request
   - Assert elapsed_seconds >= 0 and < 5.0

8. ✓ **test_call_tool_successful_request**
   - Send valid v1 request
   - Assert ok=True, status=200, body contains user

9. ✓ **test_classifier_unknown_status**
   - Status 418 (unusual code)
   - Assert kind="unknown"

## Running Tests

```bash
# Module 3 tests only
.venv\Scripts\python.exe -m pytest tests\test_classifier.py -v

# All tests (29 total)
.venv\Scripts\python.exe -m pytest tests\ -v
```

## Test Results

```
================================ 29 passed in 5.54s =================================
```

All tests passing:
- 8 mock_api tests ✓
- 12 registry tests ✓
- 9 classifier tests ✓ (NEW)

## Key Design Decisions

### 1. Never Raise Exceptions in call_tool
All errors are captured in CallResult, making error handling deterministic and testable.

### 2. Status Code Alone Insufficient for Drift Detection
A 400 or 422 could mean:
- The API schema changed (drift)
- The data is invalid but schema is correct (invalid_data)

The classifier MUST fetch the live contract and compare:
- content_hash values
- Actual body_schema and required_headers

This prevents false drift classifications when the registry is already current.

### 3. Header Value Redaction
Request info logs header names but redacts values for security. This allows debugging without exposing tokens.

### 4. Timing Tracking
Every request is timed for performance monitoring and timeout analysis.

### 5. Evidence Collection
Classification evidence includes:
- registry_hash vs live_hash
- schema_differs (bool)
- headers_differ (bool)
- status codes
- network_error messages

This makes debugging clear and supports audit logs.

## Compliance with Build Rules

### Rule 2: "A 400 or 422 is not proof of schema drift"
✓ Classifier fetches live contract and compares actual schemas before declaring drift

### Rule 7: "Never log secret values"
✓ Interceptor redacts all header values in request info

### Rule 8: "Healing is deterministic code. The LLM is only used by the agent"
✓ Classification uses pure logic - no LLM calls in healing code

### Rule 9: "Plain Python with type hints, short functions and docstrings"
✓ All functions typed, documented, and focused on single responsibilities

## Dependencies

No new dependencies required - uses existing:
- httpx (already installed)
- typing/typing_extensions (already installed)

## Next Steps

Ready for:
- differ.py (compare registry vs live contract)
- patcher.py (generate patches from diffs)
- guard.py (validate patches don't invent values)
- retry.py (retry logic with budget)
