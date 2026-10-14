"""Tests for evaluation case definitions."""

import pytest

from eval.cases import EVAL_CASES, DRIFT_CASES, REFUSE_CASES, validate_cases
from driftshield.mock_api.contracts import CONTRACTS


def test_case_count():
    """Verify we have exactly 15 cases: 9 drift + 6 refuse."""
    assert len(DRIFT_CASES) == 9, f"Expected 9 drift cases, got {len(DRIFT_CASES)}"
    assert len(REFUSE_CASES) == 6, f"Expected 6 refuse cases, got {len(REFUSE_CASES)}"
    assert len(EVAL_CASES) == 15, f"Expected 15 total cases, got {len(EVAL_CASES)}"


def test_all_contract_names_exist():
    """Verify every contract name referenced by a case exists in CONTRACTS."""
    for case in EVAL_CASES:
        if case["contract"] is not None:
            assert case["contract"] in CONTRACTS, \
                f"Case '{case['case_id']}' references unknown contract '{case['contract']}'"


def test_case_ids_unique():
    """Verify all case IDs are unique."""
    case_ids = [case["case_id"] for case in EVAL_CASES]
    assert len(case_ids) == len(set(case_ids)), \
        f"Duplicate case IDs found: {[cid for cid in case_ids if case_ids.count(cid) > 1]}"


def test_drift_cases_have_expected_text():
    """Verify all drift cases specify expected_text."""
    for case in DRIFT_CASES:
        assert case["expected_text"] is not None, \
            f"Drift case '{case['case_id']}' should have expected_text"
        assert case["expected_text"] == "Asha Rao", \
            f"Drift case '{case['case_id']}' should expect 'Asha Rao'"


def test_refuse_cases_have_no_expected_text():
    """Verify refuse cases have expected_text=None."""
    for case in REFUSE_CASES:
        assert case["expected_text"] is None, \
            f"Refuse case '{case['case_id']}' should have expected_text=None"


def test_group_matches_action():
    """Verify group and expected_action are consistent."""
    for case in EVAL_CASES:
        if case["group"] == "drift":
            assert case["expected_action"] == "heal", \
                f"Drift case '{case['case_id']}' should have expected_action='heal'"
        elif case["group"] == "refuse":
            assert case["expected_action"] == "refuse", \
                f"Refuse case '{case['case_id']}' should have expected_action='refuse'"


def test_validate_cases_function():
    """Verify the validate_cases() function passes."""
    valid, errors = validate_cases()
    assert valid, f"Case validation failed with errors: {errors}"


def test_drift_case_ids():
    """Verify the expected drift case IDs are present."""
    expected_drift = {
        "rename_id", "rename_uid", "type_int", "nest_target", "nest_deep",
        "header_tenant", "header_rename", "v2_full", "combo"
    }
    actual_drift = {case["case_id"] for case in DRIFT_CASES}
    assert actual_drift == expected_drift, \
        f"Drift case IDs mismatch. Expected: {expected_drift}, Got: {actual_drift}"


def test_refuse_case_ids():
    """Verify the expected refuse case IDs are present."""
    expected_refuse = {
        "invalid_data", "expired_token", "server_down",
        "header_billing", "ambiguous", "combo_billing"
    }
    actual_refuse = {case["case_id"] for case in REFUSE_CASES}
    assert actual_refuse == expected_refuse, \
        f"Refuse case IDs mismatch. Expected: {expected_refuse}, Got: {actual_refuse}"


def test_invalid_data_case_has_custom_task():
    """Verify invalid_data case has the custom task with 'hello'."""
    invalid_data_case = next(c for c in REFUSE_CASES if c["case_id"] == "invalid_data")
    assert "hello" in invalid_data_case["task"].lower(), \
        "invalid_data case should ask for user id 'hello'"


def test_fault_cases_have_no_contract():
    """Verify fault-based refuse cases (expired_token, server_down) use v1 (None)."""
    fault_cases = [c for c in REFUSE_CASES if c["fault"] is not None]
    for case in fault_cases:
        assert case["contract"] is None, \
            f"Fault case '{case['case_id']}' should have contract=None (uses v1)"


def test_new_contracts_included():
    """Verify the four new contracts are referenced in eval cases."""
    new_contracts = {"rename_uid", "nest_deep", "header_rename", "combo_billing"}
    referenced_contracts = {case["contract"] for case in EVAL_CASES if case["contract"]}
    
    for contract in new_contracts:
        assert contract in referenced_contracts, \
            f"New contract '{contract}' should be referenced in eval cases"
