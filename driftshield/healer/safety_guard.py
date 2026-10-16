"""Pre-flight Patch Safety Guard for validating schema repairs before application."""

from typing import Any, Dict, List, Optional
from driftshield.healer.guard import check_provenance
from driftshield.healer.patch_memory import FailedPatchMemory


class SafetyGuardResult:
    """Outcome of pre-flight patch safety validation."""

    def __init__(self, is_safe: bool, reason: str = "", violations: Optional[List[str]] = None):
        self.is_safe = is_safe
        self.reason = reason
        self.violations = violations or []

    def __bool__(self) -> bool:
        return self.is_safe

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "reason": self.reason,
            "violations": self.violations,
        }

    def __repr__(self) -> str:
        return f"<SafetyGuardResult is_safe={self.is_safe} reason={self.reason!r}>"


class PatchSafetyGuard:
    """
    Pre-flight validator enforcing safe schema evolution and zero-hallucination.
    
    Validates patches before they touch the registry:
    - Rejects inventing missing business values
    - Rejects ambiguous field mappings
    - Rejects unsupported / lossy type conversions
    - Rejects known-bad patches stored in FailedPatchMemory
    - Validates argument payload provenance
    """

    def __init__(self, memory: Optional[FailedPatchMemory] = None):
        self.memory = memory if memory is not None else FailedPatchMemory()

    def validate_patch(
        self,
        tool_name: str,
        current_version: int,
        contract_hash: str,
        changes: List[Dict[str, Any]],
        payload: Optional[Dict[str, Any]] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> SafetyGuardResult:
        """
        Validate whether a patch is safe to apply.
        """
        violations: List[str] = []

        # 1. Check Failed-Patch Memory
        is_bad, bad_reason = self.memory.is_known_bad(
            tool_name=tool_name,
            contract_hash=contract_hash,
            registry_version=current_version,
            changes=changes,
        )
        if is_bad:
            violations.append(bad_reason or "Known-bad patch detected")

        # 2. Inspect Changes for Ambiguity and Missing Business Values
        for c in changes:
            c_type = c.get("type")
            if c_type == "ambiguous":
                candidates = c.get("candidates", [])
                removed = c.get("removed", "unknown")
                violations.append(f"Ambiguous field mapping for '{removed}' (candidates: {candidates})")

            elif c_type == "new_required_field":
                field = c.get("field") or c.get("added")
                violations.append(f"Cannot invent value for new required business field: '{field}'")

            elif c_type == "type_change":
                from_t = c.get("from_type")
                to_t = c.get("to_type")
                # Allowed lossless pairs: integer <-> string
                lossless = (from_t == "string" and to_t == "integer") or (from_t == "integer" and to_t == "string")
                if not lossless:
                    violations.append(f"Unsupported type conversion from '{from_t}' to '{to_t}'")

        # 3. Check Payload Provenance (if payload and provenance are provided)
        if payload is not None and provenance is not None:
            if not check_provenance(payload, provenance):
                violations.append("Payload contains unverified or invented business values (provenance check failed)")

        if violations:
            return SafetyGuardResult(
                is_safe=False,
                reason="; ".join(violations),
                violations=violations,
            )

        return SafetyGuardResult(is_safe=True, reason="Patch passed all pre-flight safety checks")
