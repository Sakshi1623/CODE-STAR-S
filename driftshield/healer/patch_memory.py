"""Failed-patch memory to track and prevent repeated bad patch applications."""

import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple, Union


class FailedPatchMemory:
    """
    Stores and queries failed schema patches.
    
    Prevents DriftShield from repeatedly trying the same broken patch
    for an unchanged contract and registry snapshot.
    """

    def __init__(self, ttl_seconds: Optional[int] = None):
        """
        Args:
            ttl_seconds: Optional time-to-live in seconds for failed records (None = no expiry)
        """
        # key: (tool_name, contract_hash, registry_version, patch_fingerprint)
        # value: {"timestamp": float, "reason": str, "attempts": int}
        self._memory: Dict[Tuple[str, str, int, str], Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def compute_fingerprint(changes: Union[List[Dict[str, Any]], Dict[str, Any]]) -> str:
        """Generate a deterministic SHA-256 fingerprint for a patch or change set."""
        serialized = json.dumps(changes, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]

    def record_failure(
        self,
        tool_name: str,
        contract_hash: str,
        registry_version: int,
        changes: Union[List[Dict[str, Any]], Dict[str, Any]],
        reason: str,
    ) -> str:
        """
        Record a patch failure.
        
        Returns the patch fingerprint.
        """
        fingerprint = self.compute_fingerprint(changes)
        key = (tool_name, contract_hash, registry_version, fingerprint)
        
        if key in self._memory:
            self._memory[key]["attempts"] += 1
            self._memory[key]["timestamp"] = time.time()
            self._memory[key]["reason"] = reason
        else:
            self._memory[key] = {
                "timestamp": time.time(),
                "reason": reason,
                "attempts": 1,
            }
        return fingerprint

    def is_known_bad(
        self,
        tool_name: str,
        contract_hash: str,
        registry_version: int,
        changes: Union[List[Dict[str, Any]], Dict[str, Any]],
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if the proposed patch is already known to fail under current contract/version.
        
        Returns (is_bad, failure_reason).
        """
        fingerprint = self.compute_fingerprint(changes)
        key = (tool_name, contract_hash, registry_version, fingerprint)
        
        entry = self._memory.get(key)
        if not entry:
            return False, None

        if self.ttl_seconds is not None:
            if time.time() - entry["timestamp"] > self.ttl_seconds:
                del self._memory[key]
                return False, None

        return True, f"Patch {fingerprint} previously failed ({entry['attempts']}x): {entry['reason']}"

    def invalidate(self, tool_name: Optional[str] = None) -> int:
        """Clear memory for a tool or all tools (e.g., after human intervention)."""
        if tool_name is None:
            count = len(self._memory)
            self._memory.clear()
            return count
        
        keys_to_delete = [k for k in self._memory if k[0] == tool_name]
        for k in keys_to_delete:
            del self._memory[k]
        return len(keys_to_delete)
