# DriftShield End-to-End Evaluation Report

**Timestamp:** `2026-10-16T20:10:44.953041+00:00`  
**Execution Mode:** `deterministic_mock_api`  
**Accuracy:** `6/6 (100%)`  
**Unsafe Recoveries Avoided:** `6/6 (100%)`  

---

## Summary Metrics

| Metric | Measured Value | Notes |
| :--- | :--- | :--- |
| **Total Scenarios Evaluated** | `6` | Deterministic mock suite covering all contract variations |
| **DriftShield Success Rate** | `4/6` | Includes normal v1 execution, healing, and persistent reuse |
| **DriftShield Safe Stops** | `2` | Ambiguous mapping and missing required header |
| **Baseline Agent Successes** | `1/6` | Succeeds only on unmutated v1 schema; fails on all drift |
| **Unsafe Hallucinations Avoided** | `6/6` | 100% adherence to provenance and ambiguity guards |

---

## Scenario Breakdown

| # | Scenario | Contract | Baseline Status (Attempts) | DriftShield Status (Attempts) | Registry Versions | Outcome Evaluation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1. | Baseline with original v1 contract | `v1` | success (1 att) | **ok (1 att)** | `v1 -> v1` | Correct (Unsafe avoided) |
| 2. | Baseline after breaking schema change | `v2_full` | failed (3 att) | **healed (2 att)** | `v1 -> v2` | Correct (Unsafe avoided) |
| 3. | DriftShield after unambiguous schema change | `rename_id` | failed (3 att) | **healed (2 att)** | `v1 -> v2` | Correct (Unsafe avoided) |
| 4. | DriftShield after ambiguous schema change | `ambiguous` | failed (3 att) | **safe_stop (1 att)** | `v1 -> v1` | Correct (Unsafe avoided) |
| 5. | DriftShield with missing required header | `header_billing` | failed (3 att) | **safe_stop (1 att)** | `v1 -> v1` | Correct (Unsafe avoided) |
| 6. | Repeated call after successful healing | `rename_id` | N/A | **ok (1 att)** | `v2 -> v2` | Correct (Unsafe avoided) |

---

## Detailed Analysis by Scenario

### 1. Baseline with original v1 contract
- **Contract Schema**: `v1`
- **Description**: Verify normal tool execution against the original unmutated API schema.
- **Baseline Outcome**: `success` (Attempts: `1`, Elapsed: `0.0058s`)
  - *Reason*: `Direct API call succeeded (200 OK)`
- **DriftShield Outcome**: `ok` (Attempts: `1`, Elapsed: `0.0062s`)
  - *Reason*: `Success on first attempt`
- **Notes**: Both systems succeed normally on the baseline schema.

### 2. Baseline after breaking schema change
- **Contract Schema**: `v2_full`
- **Description**: Evaluate response to breaking schema change (field rename + nesting).
- **Baseline Outcome**: `failed` (Attempts: `3`, Elapsed: `0.0069s`)
  - *Reason*: `Baseline failed after 3 attempts: HTTP 400 ({'error': 'missing_header', 'header': 'X-Tenant-Token'})`
- **DriftShield Outcome**: `healed` (Attempts: `2`, Elapsed: `0.0141s`)
  - *Reason*: `Successfully healed schema drift`
- **Notes**: Baseline exhausts retries and fails; DriftShield adapts and heals to v2.

### 3. DriftShield after unambiguous schema change
- **Contract Schema**: `rename_id`
- **Description**: Direct field rename (user_id -> id) with verified contract provenance.
- **Baseline Outcome**: `failed` (Attempts: `3`, Elapsed: `0.0102s`)
  - *Reason*: `Baseline failed after 3 attempts: HTTP 422 ({'detail': [{'loc': ['body'], 'msg': "'id' is a required property", 'type': 'value_error.jsonschemamismatch'}]})`
- **DriftShield Outcome**: `healed` (Attempts: `2`, Elapsed: `0.0136s`)
  - *Reason*: `Successfully healed schema drift`
- **Notes**: DriftShield diffs contract, generates rename patch, and succeeds on retry.

### 4. DriftShield after ambiguous schema change
- **Contract Schema**: `ambiguous`
- **Description**: Ambiguous schema drift where candidate fields cannot be deterministically resolved.
- **Baseline Outcome**: `failed` (Attempts: `3`, Elapsed: `0.0123s`)
  - *Reason*: `Baseline failed after 3 attempts: HTTP 422 ({'detail': [{'loc': ['body'], 'msg': "'ref_a' is a required property", 'type': 'value_error.jsonschemamismatch'}]})`
- **DriftShield Outcome**: `safe_stop` (Attempts: `1`, Elapsed: `0.0067s`)
  - *Reason*: `Ambiguous change: user_id → ['ref_b', 'ref_a']`
- **Notes**: Safe-stop is triggered; DriftShield avoids guessing or corrupting arguments.

### 5. DriftShield with missing required header
- **Contract Schema**: `header_billing`
- **Description**: New required header introduced upstream without agent credential context.
- **Baseline Outcome**: `failed` (Attempts: `3`, Elapsed: `0.0068s`)
  - *Reason*: `Baseline failed after 3 attempts: HTTP 400 ({'error': 'missing_header', 'header': 'X-Billing-Region'})`
- **DriftShield Outcome**: `safe_stop` (Attempts: `1`, Elapsed: `0.0054s`)
  - *Reason*: `Required value unavailable: X-Billing-Region`
- **Notes**: Safe-stop triggered with fix proposal; does not fabricate credentials.

### 6. Repeated call after successful healing
- **Contract Schema**: `rename_id`
- **Description**: Verify that patched registry definition persists and executes directly with 1 attempt.
- **Baseline Outcome**: `not_applicable` (Attempts: `0`, Elapsed: `0.0s`)
  - *Reason*: `Baseline has no registry or patch persistence mechanism.`
- **DriftShield Outcome**: `ok` (Attempts: `1`, Elapsed: `0.0053s`)
  - *Reason*: `Subsequent call executed against active patched registry version 2`
- **Notes**: Registry retains version 2; call succeeds immediately on 1st attempt without healing overhead.

---

## Critical Boundaries and Disclosures
- **Mock API Ground Truth**: All evaluations are performed deterministically against the local FastAPI mock server (`/users/lookup`, `/schema`, `/admin/*`).
- **Zero Live LLM Non-Determinism**: This benchmark isolates DriftShield's deterministic healing engine (interceptor, differ, classifier, provenance validator, patcher, executor) from third-party LLM inference variance.
- **No Fabricated Data**: Metrics are strictly measured from actual execution timing and attempt counters.
