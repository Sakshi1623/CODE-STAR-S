# DriftShield Phase 1 - Mock API

## Running Tests

From the project root (`d:\Sakshi\driftshield`):

```bash
.venv\Scripts\pytest tests\test_mock_api.py -v
```

## Running the Server

From the project root (`d:\Sakshi\driftshield`):

```bash
.venv\Scripts\uvicorn driftshield.mock_api.server:app --reload --port 8000
```

The server will be available at `http://localhost:8000`

## API Endpoints

- **GET /schema** - Returns the active contract
- **POST /users/lookup** - Look up a user (validates against active contract)
- **POST /admin/mutate** - Switch to a different contract (e.g., `{"to": "v2_full"}`)
- **POST /admin/reset** - Reset to v1 contract
- **POST /admin/fault** - Inject faults (e.g., `{"mode": "expired_token"}` or `{"mode": null}`)
- **GET /admin/stats** - Get execution statistics

## Available Contracts

- `v1` - Basic schema with `user_id` string
- `v2_full` - Nested target.id integer + X-Tenant-Token header
- `rename_id` - Renamed field from user_id to id
- `type_int` - Type change from string to integer
- `nest_target` - Nesting change to target.id
- `header_tenant` - Added X-Tenant-Token header
- `combo` - Combined changes (nesting + type + header)
- `header_billing` - X-Billing-Region header (not in config)
- `ambiguous` - Two new fields ref_a and ref_b with no mappings

## Test Results

All 8 tests passing:
✓ v1 accepts user_id
✓ v2_full migration behavior
✓ Hash stability
✓ Hash parity with response headers
✓ All contracts with valid/invalid requests
✓ Fault modes (401, 503)
✓ Execution stats
✓ User differentiation (123: Asha Rao, 124: Ravi Iyer)
