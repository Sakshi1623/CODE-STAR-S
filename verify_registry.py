"""Verify registry implementation without modifying any files.

This script demonstrates:
1. Creating a registry with initial state
2. Building tools and inspecting the lookup_user definition
3. Applying a valid patch
4. Verifying the tool definition changes and version increments
"""

from driftshield.healer.registry import create_default_registry
from driftshield.mock_api.contracts import CONTRACTS
import json

print("=" * 70)
print("STEP 1: Create registry in initial state")
print("=" * 70)

# Create registry using the project's factory function
registry = create_default_registry()

# Get initial version
initial_version = registry.version("lookup_user")
print(f"\nInitial registry version: {initial_version}")

print("\n" + "=" * 70)
print("STEP 2: Build tools and print lookup_user definition")
print("=" * 70)

# Build tools for LLM
tools_before = registry.build_tools()
print(f"\nNumber of tools: {len(tools_before)}")
print(f"\nTool definition before patch:")
print(json.dumps(tools_before[0], indent=2))

# Also inspect the raw tool from registry
tool_before = registry.get("lookup_user")
print(f"\nRaw tool body_schema before patch:")
print(json.dumps(tool_before["body_schema"], indent=2))
print(f"Contract hash before: {tool_before['contract_hash']}")

print("\n" + "=" * 70)
print("STEP 3: Apply a valid patch (v1 -> v2_full)")
print("=" * 70)

# Get v2_full contract for the patch
v2_full_contract = CONTRACTS["v2_full"]

# Create new snapshot matching v2_full contract
# This follows the same pattern used in the healing tests
patched_tool = tool_before.copy()
patched_tool["body_schema"] = v2_full_contract["body_schema"]
patched_tool["required_headers"] = v2_full_contract["required_headers"]
patched_tool["contract_hash"] = v2_full_contract["content_hash"]

print(f"\nApplying patch with reason: 'schema drift detected'")
print(f"New schema type: {v2_full_contract['body_schema']['type']}")
print(f"New required fields: {v2_full_contract['body_schema'].get('required', [])}")

# Apply the patch
registry.apply_patch("lookup_user", patched_tool, "schema drift detected")

patched_version = registry.version("lookup_user")
print(f"\nVersion after patch: {patched_version}")

print("\n" + "=" * 70)
print("STEP 4: Build tools again and print updated definition")
print("=" * 70)

# Build tools again - should reflect the patch (no caching per Rule 5)
tools_after = registry.build_tools()
print(f"\nNumber of tools: {len(tools_after)}")
print(f"\nTool definition after patch:")
print(json.dumps(tools_after[0], indent=2))

# Inspect raw tool after patch
tool_after = registry.get("lookup_user")
print(f"\nRaw tool body_schema after patch:")
print(json.dumps(tool_after["body_schema"], indent=2))
print(f"Contract hash after: {tool_after['contract_hash']}")

print("\n" + "=" * 70)
print("VERIFICATION RESULTS")
print("=" * 70)

# Verify changes occurred
schema_changed = (
    tool_before["body_schema"] != tool_after["body_schema"]
)
version_incremented = patched_version == initial_version + 1
hash_changed = tool_before["contract_hash"] != tool_after["contract_hash"]

print(f"\n✓ Schema changed: {schema_changed}")
print(f"  Before: {list(tool_before['body_schema'].get('properties', {}).keys())}")
print(f"  After:  {list(tool_after['body_schema'].get('properties', {}).keys())}")

print(f"\n✓ Version incremented: {version_incremented}")
print(f"  Before: {initial_version}")
print(f"  After:  {patched_version}")

print(f"\n✓ Contract hash changed: {hash_changed}")
print(f"  Before: {tool_before['contract_hash'][:16]}...")
print(f"  After:  {tool_after['contract_hash'][:16]}...")

print(f"\n✓ Headers changed: {tool_before['required_headers'] != tool_after['required_headers']}")
print(f"  Before: {tool_before['required_headers']}")
print(f"  After:  {tool_after['required_headers']}")

# Final summary
if schema_changed and version_incremented and hash_changed:
    print("\n" + "=" * 70)
    print("✅ ALL VERIFICATIONS PASSED")
    print("=" * 70)
    print("\nRegistry correctly:")
    print("  1. Created with initial state (v1 contract)")
    print("  2. Built tools with initial definition")
    print("  3. Applied patch with new snapshot")
    print("  4. Updated tool definition and incremented version")
    print("  5. Built tools again with updated definition (no caching)")
else:
    print("\n" + "=" * 70)
    print("❌ VERIFICATION FAILED")
    print("=" * 70)
