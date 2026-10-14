"""Evaluation cases for DriftShield healing agents.

This module defines 15 test cases covering both successful drift healing
and safe refusal scenarios. Each case specifies the contract, fault mode,
task description, and expected agent behavior.
"""

from typing import Literal, TypedDict
from driftshield.agents.common import STANDARD_TASK


class EvalCase(TypedDict):
    """A single evaluation case for testing agent behavior."""
    case_id: str
    """Unique identifier for this case"""
    
    group: Literal["drift", "refuse"]
    """Category: 'drift' for healable cases, 'refuse' for safe-stop cases"""
    
    contract: str | None
    """Contract name to activate, or None for no mutation"""
    
    fault: Literal["expired_token", "server_down"] | None
    """Fault mode to inject, or None for no fault"""
    
    task: str
    """Task description to give to the agent"""
    
    expected_class: str
    """Expected classification result (ok, drift, auth, network, invalid_data, unknown)"""
    
    expected_action: Literal["heal", "refuse"]
    """Expected agent action: 'heal' (succeed/healed) or 'refuse' (safe_stop/failed)"""
    
    expected_text: str | None
    """Expected text in response for heal cases, None for refuse cases"""


# Drift cases: Agent should successfully heal and return "Asha Rao"
DRIFT_CASES: list[EvalCase] = [
    {
        "case_id": "rename_id",
        "group": "drift",
        "contract": "rename_id",
        "fault": None,
        "task": STANDARD_TASK,
        "expected_class": "drift",
        "expected_action": "heal",
        "expected_text": "Asha Rao",
    },
    {
        "case_id": "rename_uid",
        "group": "drift",
        "contract": "rename_uid",
        "fault": None,
        "task": STANDARD_TASK,
        "expected_class": "drift",
        "expected_action": "heal",
        "expected_text": "Asha Rao",
    },
    {
        "case_id": "type_int",
        "group": "drift",
        "contract": "type_int",
        "fault": None,
        "task": STANDARD_TASK,
        "expected_class": "drift",
        "expected_action": "heal",
        "expected_text": "Asha Rao",
    },
    {
        "case_id": "nest_target",
        "group": "drift",
        "contract": "nest_target",
        "fault": None,
        "task": STANDARD_TASK,
        "expected_class": "drift",
        "expected_action": "heal",
        "expected_text": "Asha Rao",
    },
    {
        "case_id": "nest_deep",
        "group": "drift",
        "contract": "nest_deep",
        "fault": None,
        "task": STANDARD_TASK,
        "expected_class": "drift",
        "expected_action": "heal",
        "expected_text": "Asha Rao",
    },
    {
        "case_id": "header_tenant",
        "group": "drift",
        "contract": "header_tenant",
        "fault": None,
        "task": STANDARD_TASK,
        "expected_class": "drift",
        "expected_action": "heal",
        "expected_text": "Asha Rao",
    },
    {
        "case_id": "header_rename",
        "group": "drift",
        "contract": "header_rename",
        "fault": None,
        "task": STANDARD_TASK,
        "expected_class": "drift",
        "expected_action": "heal",
        "expected_text": "Asha Rao",
    },
    {
        "case_id": "v2_full",
        "group": "drift",
        "contract": "v2_full",
        "fault": None,
        "task": STANDARD_TASK,
        "expected_class": "drift",
        "expected_action": "heal",
        "expected_text": "Asha Rao",
    },
    {
        "case_id": "combo",
        "group": "drift",
        "contract": "combo",
        "fault": None,
        "task": STANDARD_TASK,
        "expected_class": "drift",
        "expected_action": "heal",
        "expected_text": "Asha Rao",
    },
]


# Refuse cases: Agent should safely stop without healing
REFUSE_CASES: list[EvalCase] = [
    {
        "case_id": "invalid_data",
        "group": "refuse",
        "contract": None,
        "fault": None,
        "task": 'Look up the user with id "hello" and tell me their name.',
        "expected_class": "invalid_data",
        "expected_action": "refuse",
        "expected_text": None,
    },
    {
        "case_id": "expired_token",
        "group": "refuse",
        "contract": None,
        "fault": "expired_token",
        "task": STANDARD_TASK,
        "expected_class": "auth",
        "expected_action": "refuse",
        "expected_text": None,
    },
    {
        "case_id": "server_down",
        "group": "refuse",
        "contract": None,
        "fault": "server_down",
        "task": STANDARD_TASK,
        "expected_class": "network",
        "expected_action": "refuse",
        "expected_text": None,
    },
    {
        "case_id": "header_billing",
        "group": "refuse",
        "contract": "header_billing",
        "fault": None,
        "task": STANDARD_TASK,
        "expected_class": "drift",
        "expected_action": "refuse",
        "expected_text": None,
    },
    {
        "case_id": "ambiguous",
        "group": "refuse",
        "contract": "ambiguous",
        "fault": None,
        "task": STANDARD_TASK,
        "expected_class": "drift",
        "expected_action": "refuse",
        "expected_text": None,
    },
    {
        "case_id": "combo_billing",
        "group": "refuse",
        "contract": "combo_billing",
        "fault": None,
        "task": STANDARD_TASK,
        "expected_class": "drift",
        "expected_action": "refuse",
        "expected_text": None,
    },
]


# All evaluation cases
EVAL_CASES: list[EvalCase] = DRIFT_CASES + REFUSE_CASES


def validate_cases() -> tuple[bool, list[str]]:
    """
    Validate that all evaluation cases are well-formed.
    
    Returns:
        Tuple of (valid, errors) where valid is True if all cases pass validation,
        and errors is a list of error messages
    """
    from driftshield.mock_api.contracts import CONTRACTS
    
    errors: list[str] = []
    
    # Check for duplicate case IDs
    case_ids = [case["case_id"] for case in EVAL_CASES]
    if len(case_ids) != len(set(case_ids)):
        duplicates = [cid for cid in case_ids if case_ids.count(cid) > 1]
        errors.append(f"Duplicate case IDs found: {set(duplicates)}")
    
    # Validate each case
    for case in EVAL_CASES:
        case_id = case["case_id"]
        
        # Check that contract names exist
        if case["contract"] is not None:
            if case["contract"] not in CONTRACTS:
                errors.append(
                    f"Case '{case_id}': contract '{case['contract']}' not found in CONTRACTS"
                )
        
        # Check group matches expected_action
        if case["group"] == "drift" and case["expected_action"] != "heal":
            errors.append(
                f"Case '{case_id}': drift group should have expected_action='heal'"
            )
        if case["group"] == "refuse" and case["expected_action"] != "refuse":
            errors.append(
                f"Case '{case_id}': refuse group should have expected_action='refuse'"
            )
        
        # Check expected_text is set for heal cases
        if case["expected_action"] == "heal" and case["expected_text"] is None:
            errors.append(
                f"Case '{case_id}': heal cases should specify expected_text"
            )
        if case["expected_action"] == "refuse" and case["expected_text"] is not None:
            errors.append(
                f"Case '{case_id}': refuse cases should have expected_text=None"
            )
    
    return len(errors) == 0, errors
