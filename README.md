# agent-model-router

> LLM intelligent routing engine — routes user requests to the optimal model tier.

Complex tasks get premium reasoning models (Claude Opus/Sonnet), simple queries get fast/cheap models (Haiku).
Every message is analyzed and automatically routed to the best model, saving cost while maintaining quality.

---

## One-Liner

```python
from model_router import ModelRouter

router = ModelRouter()                          # Initialize
tier, confidence, _, _ = router.classify("Hi")  # Classify
print(tier)  # → "t0"  pick the fast model
```

Map the returned `tier` to your own model IDs and you're done.

---

## Quick Start (3 Steps)

### 1. Install

```bash
git clone https://github.com/your-org/agent-model-router.git
cd agent-model-router
pip install -e ".[ml]"
```

### 2. Download Models

```bash
python scripts/download_models.py
```

Models are downloaded to `models/` (about 500MB, gitignored).

### 3. Try It

```bash
python -c "
from model_router import ModelRouter
r = ModelRouter()
print(r.classify('Implement quicksort in Python'))
"
```

Output:
```
('t2', 0.87, 'lgbm_main', {'trajectory': 'COLD_START', 'flags': {}})
```
- `t2` = premium tier → complex programming task
- `0.87` = confidence

---

## Three Ways to Use It

### Usage 1: Python Direct Import (Most Common)

Import directly in your Python project, no server needed.

```python
from model_router import ModelRouter

# Initialize (auto-loads models/ and tiers.json)
router = ModelRouter()

# Classify
tier, confidence, source, extra = router.classify(
    message="Help me analyze this code's performance",
    history=[
        {"role": "user", "content": "This code runs a bit slow"},
        {"role": "assistant", "content": "Let me look at the code..."},
    ],
)

# Map tier to your model IDs from tiers.json
models = router.get_tier_models(tier)  # → ["claude-sonnet-4-5-20250514"]
selected_model = models[0]
```

**Full Integration Example** — insert routing before your Agent calls the LLM API:

```python
from model_router import ModelRouter

router = ModelRouter()

def call_llm(messages):
    """Your LLM call function with automatic model selection."""
    # 1. Get the last user message
    user_msg = next(m["content"] for m in reversed(messages) if m["role"] == "user")
    history = messages[:-1]

    # 2. Route
    tier, _, _, _ = router.classify(message=user_msg, history=history)

    # 3. Pick model by tier
    models = router.get_tier_models(tier)
    model = models[0]

    # 4. Call LLM API
    return your_llm_client.chat.completions.create(
        model=model,
        messages=messages,
    )
```

---

### Usage 2: Hermes Agent Integration

Hermes Agent is a Python Agent framework. The plugin **intercepts every LLM request** and auto-selects the model.

**Install:** Make sure `agent-model-router` is installed.

**Register the plugin in Hermes config:**

```python
from integrations.hermes.plugin import ModelRouterPlugin

# Create plugin
router_plugin = ModelRouterPlugin(
    bundle_dir="./models",   # Model dir (default ./models)
    auto_route=True,         # Auto-replace model (default True)
)

# Register to Hermes's pre_api_request hook
# Hermes calls plugin.pre_api_request(context) before each LLM request
```

**Workflow:**

```
Hermes receives user message
  → Triggers pre_api_request hook
    → ModelRouterPlugin calls router.classify()
    → Automatically replaces context["model"] with the optimal model
  → Hermes sends LLM request (with the replaced model)
```

**Manual usage (without hook):**

```python
plugin = ModelRouterPlugin()

context = {
    "messages": [{"role": "user", "content": "Hi"}],
    "model": "claude-haiku-4-5",  # Default model
    "session_id": "abc-123",
}

# Call routing, returns modified context
new_context = plugin.pre_api_request(context)

print(new_context["model"])
# → "claude-sonnet-4-5-20250514" (auto-upgraded to premium)

print(new_context["router_metadata"])
# → {"tier": "t2", "confidence": 0.92, ...}
```

---

### Usage 3: OpenClaw Integration (Node.js)

OpenClaw is a Node.js framework that can't import Python packages directly.
So you **start an HTTP service first**, then use the Node.js plugin to call it.

#### Step 1: Start the Router Service

```bash
uvicorn server.service:app --host 0.0.0.0 --port 8100
```

Or with environment variables:
```bash
MODEL_ROUTER_MODELS_DIR=./models MODEL_ROUTER_PORT=8100 \
  uvicorn server.service:app --host 0.0.0.0 --port 8100
```

Verify:
```bash
curl http://localhost:8100/health
# → {"status": "ok", "model_loaded": true, "tiers": ["t0", "t1", "t2", "t3"]}
```

#### Step 2: Configure the OpenClaw Plugin

Add to your OpenClaw config:

```json
{
  "plugins": {
    "agent-model-router": {
      "enabled": true,
      "serviceUrl": "http://localhost:8100"
    }
  }
}
```

Or set in `.env`:
```bash
MODEL_ROUTER_URL=http://localhost:8100
```

#### Step 3: Plugin Works Automatically

The plugin `integrations/openclaw/plugins/agent-model-router/index.js`
registers as a `preRequest` hook. Before each LLM request:

```
User sends message
  → OpenClaw triggers preRequest hook
    → Node.js plugin POSTs to http://localhost:8100/classify
    → Returns tier + confidence
    → Plugin replaces context.model with the tier's model
  → OpenClaw sends LLM request (with the replaced model)
```

**Manual API call (without plugin):**

```bash
curl -X POST http://localhost:8100/classify \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Help me write a REST API",
    "history": []
  }'
```

Response:
```json
{
  "tier": "t2",
  "confidence": 0.87,
  "source": "lgbm_main",
  "extra": {
    "trajectory": "COLD_START",
    "flags": {}
  }
}
```

```javascript
// Call from Node.js
const res = await fetch("http://localhost:8100/classify", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: "Hello", history: [] }),
});
const data = await res.json();
console.log(data.tier); // → "t0"
```

---

## Return Values

`router.classify()` returns 4 values:

| Value | Type | Description |
|-------|------|-------------|
| `tier` | `str` | Tier ID (`t0`/`t1`/`t2`/`t3`) |
| `confidence` | `float` | Classification confidence (0.0 ~ 1.0) |
| `source` | `str` | Decision source (`lgbm_main` / `lgbm_aux` / `mlp`) |
| `extra` | `dict` | Metadata (trajectory, flags, etc.) |

## Route Classes

Internally, requests are classified as R0 ~ R3, mapped to t0 ~ t3:

| Class | Tier | Typical Scenarios |
|-------|------|-------------------|
| R0 | t0 (fast) | "Hi", "Thanks", simple Q&A |
| R1 | t1 (standard) | Translation, summarization, general Q&A |
| R2 | t2 (premium) | Coding, analysis, debugging, long documents |
| R3 | t3 (premium-reasoning) | Architecture design, comparison, deep reasoning |

## Customize Model Tiers

Edit `tiers.json`:

```json
[
  {
    "tier": "t0",
    "models": ["claude-haiku-4-5-20251001"],
    "description": "Fast & cheap"
  },
  {
    "tier": "t2",
    "models": ["claude-sonnet-4-5-20250514", "gpt-4.1"],
    "description": "Best quality"
  }
]
```

Changes take effect immediately. Reload at runtime:

```python
router.reload_tiers()
```

List models for a tier:
```python
router.get_tier_models("t2")
# → ["claude-sonnet-4-5-20250514", "gpt-4.1"]
```

List all tiers:
```python
router.get_available_tiers()
# → ["t0", "t1", "t2", "t3"]
```

## HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/classify` | POST | Classification request |
| `/tiers` | GET | List all tiers |
| `/tiers/reload` | POST | Reload tier config from disk |

## How It Works (Brief)

```
User request → Feature extraction(390-dim) → 3-head ensemble → 8-step postprocessing → Tier output
```

390-dim features: hand-crafted(51) + TF-IDF(102) + context(10) + history(16) + BGE embedding(192) + assistant(12) + continuation/reasoning(7)

3-head ensemble: LightGBM primary + LightGBM auxiliary + ONNX MLP

8-step postprocessing ensures safe decisions: margin upgrade, R1 rescue, under-routing safety net, flag overrides, etc.

---

## Install Options

```bash
pip install -e .          # Basic — HTTP service only, no numpy
pip install -e ".[ml]"    # Full — with ML inference (recommended)
pip install -e ".[ml,dev]" # Dev — with test tools
```

| Category | Packages |
|----------|----------|
| Core | pydantic, fastapi, uvicorn, pyyaml |
| ML | numpy, onnxruntime, lightgbm, scikit-learn, tokenizers |
| Dev | pytest, httpx |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_ROUTER_MODELS_DIR` | `./models` | Model artifacts directory |
| `MODEL_ROUTER_TIERS_PATH` | `./tiers.json` | Tier config path |
| `MODEL_ROUTER_PORT` | `8100` | HTTP service port |
| `MODEL_ROUTER_URL` | `http://localhost:8100` | OpenClaw service URL |

## Project Structure

```
agent-model-router/
├── src/model_router/          # Core package
│   ├── router.py              # ModelRouter main entry
│   ├── engine/                # Inference engine
│   ├── features.py            # Feature extraction
│   ├── controller.py          # Thinking mode / Prompt strategy
│   ├── flags.py               # Risk flag detection
│   ├── trajectory.py          # Conversation trajectory
│   └── bge_onnx.py            # BGE ONNX backend
├── server/service.py          # FastAPI HTTP service
├── scripts/download_models.py # Model download script
├── integrations/              # Framework integrations
│   ├── hermes/plugin.py       # Hermes Agent plugin
│   └── openclaw/              # OpenClaw plugin
├── tiers.json                 # Tier configuration
└── tests/                     # Tests
```

## License

Apache-2.0
