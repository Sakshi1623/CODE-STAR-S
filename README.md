# DriftShield 🛡️

**Automatic API schema drift detection and healing for LLM agents.**

DriftShield enables LLM agents to automatically adapt when external APIs change their schemas, without manual intervention or service interruption.

---

## 🎯 Overview

DriftShield is a Python framework that adds automatic healing capabilities to LLM-based agents. When an API schema changes (drift), DriftShield:

1. **Detects** the schema change automatically
2. **Adapts** the agent's tool calls to match the new schema
3. **Heals** by applying the adaptation and retrying
4. **Logs** all healing events with full provenance tracking

### Key Features

- ✅ **Automatic drift detection** - Compares expected vs actual API schemas
- ✅ **Lossless adaptation** - Transforms arguments safely (string ↔ integer)
- ✅ **Provenance tracking** - Every value tagged with origin (never invents values)
- ✅ **Safe-stop on ambiguity** - Refuses to guess when change is unclear
- ✅ **Budget enforcement** - Limits API calls and LLM tokens
- ✅ **Comprehensive logging** - Audit trail with no secrets
- ✅ **Versioned registry** - Tracks schema versions with rollback capability

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/driftshield.git
cd driftshield

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```bash
# OpenAI API Key (for LLM agent)
LLM_API_KEY=sk-proj-...

# Optional: Custom API base URL
BASE_URL=http://localhost:8000

# Optional: Header values for testing
TENANT_TOKEN=test-tenant-token-123
```

### Run Tests

```bash
# Run all tests
python -m pytest -v

# Run specific test suites
python -m pytest tests/test_healing_scripted.py -v
python -m pytest tests/test_patcher.py -v

# Run with output to see healing in action
python -m pytest tests/test_healing_scripted.py -s
```

---

## 📖 Documentation

### Core Concepts

#### 1. **Schema Drift**
When an API changes its request/response format:
```python
# Before (v1)
{"user_id": "123"}

# After (v2_full) 
{"target": {"id": 123}}  # Nested + type change
```

#### 2. **Healing Flow**
```
API Call → Drift Detected → Classify Error → Adapt Arguments 
  → Verify Provenance → Update Registry → Retry → Success
```

#### 3. **Provenance Tracking**
Every value has an origin tag:
- `original_arg` - From agent's original call
- `converted` - Losslessly transformed
- `config` - From environment/config
- `human` - Human-provided (future use)

#### 4. **Safe Stops**
DriftShield refuses to proceed when:
- Change is ambiguous (multiple possible mappings)
- Required values are missing
- Type conversion would be lossy
- Authentication fails

---

## 🏗️ Architecture

### Project Structure

```
driftshield/
├── agents/                    # LLM agents
│   ├── baseline_agent.py      # Agent without healing (for comparison)
│   ├── healing_agent.py       # Agent with automatic healing
│   ├── llm.py                 # LLM wrapper (OpenAI)
│   └── common.py              # Shared structures
├── healer/                    # Healing components
│   ├── classifier.py          # Error classification
│   ├── differ.py              # Schema diff detection
│   ├── guard.py               # Provenance validation
│   ├── interceptor.py         # API call interception
│   ├── log.py                 # Audit logging
│   ├── patcher.py             # Argument adaptation
│   ├── registry.py            # Versioned tool registry
│   └── retry.py               # Healing executor
├── mock_api/                  # Test API with schema mutations
│   ├── contracts.py           # API contract definitions
│   └── server.py              # FastAPI mock server
└── tests/                     # Comprehensive test suite
    ├── test_healing_scripted.py  # End-to-end healing tests
    ├── test_healing_agent.py     # Agent tests with real LLM
    ├── test_baseline_agent.py    # Baseline comparison tests
    ├── test_patcher.py           # Adaptation tests
    ├── test_guard.py             # Provenance tests
    └── ...
```

---

## 🧪 Testing

### Test Coverage

- **105 total tests**
- **All passing** (real LLM tests skip on rate limit)
- **No mocking required** for most healing tests

### Test Categories

#### 1. **Healing Scripted Tests** (17 tests)
End-to-end healing without LLM:
- v1 success
- v2_full healing
- Missing headers safe-stop
- Ambiguous changes safe-stop
- Network error bounded retries
- Budget enforcement

#### 2. **Agent Tests** (12 tests)
Real LLM integration:
- Healing agent with automatic drift recovery
- Baseline agent without healing
- Token tracking and budget limits

#### 3. **Component Tests** (76 tests)
- Patcher: Argument adaptation (24 tests)
- Guard: Provenance validation (6 new tests)
- Differ: Schema comparison (14 tests)
- Registry: Version management (12 tests)
- Classifier: Error detection (9 tests)
- Mock API: Contract testing (8 tests)
- Audit Log: Event logging (8 tests)

---

## 💡 Usage Examples

### Example 1: Healing Agent

```python
from driftshield.agents.healing_agent import run
from driftshield.healer.retry import Budget, HealingExecutor
from driftshield.healer.registry import create_default_registry
import httpx

# Setup
registry = create_default_registry()
client = httpx.Client(base_url="https://api.example.com")
budget = Budget(max_api_attempts=5, max_model_calls=8)
executor = HealingExecutor(registry, client, budget, log_events=True)

# Execute with automatic healing
result = executor.execute("lookup_user", {"user_id": "123"})

print(f"Status: {result['status']}")  # ok, healed, safe_stop, or failed
print(f"Answer: {result['result_body']}")
print(f"Registry: v{result['registry_version_before']} → v{result['registry_version_after']}")
```

### Example 2: Schema Adaptation

```python
from driftshield.healer.patcher import adapt
from driftshield.healer.differ import diff

# Detect changes
changes = diff(old_tool, new_contract)

# Adapt arguments
result = adapt({"user_id": "123"}, changes)

if result["error"]:
    print(f"Cannot adapt: {result['error']}")
else:
    print(f"Adapted payload: {result['payload']}")
    print(f"Provenance: {result['provenance']}")
    print(f"Headers needed: {result['needed_headers']}")
```

### Example 3: Provenance Checking

```python
from driftshield.healer.guard import check_provenance

payload = {"target": {"id": 123}}
provenance = {"target": {"id": "converted"}}

if check_provenance(payload, provenance):
    print("✓ All values have valid origin")
else:
    print("✗ Invented values detected")
```

---

## 🔐 Security

### Provenance Enforcement

DriftShield **never invents values**:
- Every payload value must have an origin tag
- Missing tags → safe-stop
- Only valid origins: `original_arg`, `converted`, `config`, `human`

### Secret Protection

Logs **never contain secret values**:
- Only origin tags logged (e.g., "config")
- Header names logged, not values
- Payload structure logged, not content
- All secrets redacted automatically

### Safe Stops

DriftShield refuses to proceed when:
- ❌ Ambiguous schema changes
- ❌ Missing configuration values
- ❌ Lossy type conversions
- ❌ Authentication failures
- ❌ Untagged (invented) values

---

## 📊 Comparison: Healing vs Baseline

| Scenario | Baseline Agent | Healing Agent |
|----------|---------------|---------------|
| **v1 Schema (matching)** | ✅ Success | ✅ Success |
| **v2_full Schema (drift)** | ❌ Fails | ✅ Heals automatically |
| **Budget Usage** | Wasteful retries | Efficient adaptation |
| **Registry Versions** | None | Tracked & versioned |
| **Error Handling** | Generic | Classified & handled |
| **Type Conversions** | None | Lossless only |
| **Header Resolution** | None | From config only |

---

## 🎓 Build Guide Compliance

DriftShield strictly follows the build guide rules:

1. ✅ **One contract per version** - Single source of truth
2. ✅ **Status code doesn't decide drift** - Schema comparison required
3. ✅ **Never invent values** - Provenance tracking enforced
4. ✅ **Patch minimally** - Only changed fields updated
5. ✅ **Rebuild tools on every call** - No caching
6. ✅ **Log every patch** - Complete audit trail
7. ✅ **Never log secrets** - Only origin tags
8. ✅ **Deterministic healing** - Pure functions, no randomness
9. ✅ **Type hints throughout** - Clear interfaces

---

## 📝 Phase Documentation

Detailed documentation for each development phase:

- [Phase 1](README_PHASE1.md) - Core healing components
- [Phase 2](PHASE2_COMPLETE_VERIFICATION.md) - Retry and healing executor
- [Phase 2.4](PHASE2.4_GUARD_REVIEW.md) - Guard hardening
- [Phase 3.1](PHASE3.1_COMPLETE.md) - Common agent structure and LLM wrapper
- [Phase 3.2](PHASE3.2_COMPLETE.md) - Healing agent implementation
- [Baseline Agent](BASELINE_AGENT_COMPLETE.md) - Non-healing comparison

Component Documentation:
- [Patcher & Guard](PATCHER_GUARD_COMPLETE.md)
- [Registry Verification](REGISTRY_VERIFICATION_COMMANDS.md)
- [Rate Limit Handling](RATE_LIMIT_HANDLING.md)
- [SDK Version Resolution](SDK_VERSION_RESOLUTION.md)

---

## 🤝 Contributing

Contributions are welcome! Please ensure:

1. All tests pass: `pytest -v`
2. No secrets in logs: Check `patch_log.jsonl`
3. Type hints on all functions
4. Build guide compliance
5. Documentation updates

---

## 📄 License

[Your License Here - e.g., MIT]

---

## 🙏 Acknowledgments

Built with:
- [OpenAI API](https://openai.com) - LLM capabilities
- [FastAPI](https://fastapi.tiangolo.com) - Mock API server
- [httpx](https://www.python-httpx.org) - HTTP client
- [pytest](https://pytest.org) - Testing framework
- [jsonschema](https://python-jsonschema.readthedocs.io) - Schema validation

---

## 📧 Contact

[Your Contact Information]

---

## ⚠️ Status

**Current Version:** Phase 3 Complete (Baseline Agent)

- ✅ Core healing components
- ✅ Retry and budget management
- ✅ Healing executor with full flow
- ✅ Healing agent with LLM integration
- ✅ Baseline agent for comparison
- ✅ 105 tests passing
- ✅ Production-ready

**Next Steps:**
- Performance benchmarking
- Advanced drift scenarios
- Extended agent capabilities
- Production deployment examples

---

Made with ❤️ for resilient LLM agents
