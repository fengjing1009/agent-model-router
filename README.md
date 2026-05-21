# agent-model-router

> LLM intelligent routing engine — routes user requests to the optimal model tier.
>
> LLM 智能路由引擎 — 把用户请求自动分到最合适的模型。

🌐 **[中文版 README →](README_zh.md)** | **[English README →](README.md)**

> This project is based on the routing implementation in [OpenSquilla](https://github.com/opensquilla/opensquilla).

Complex tasks get premium reasoning models, simple queries get fast models.
复杂任务用高级推理模型，简单查询用快速/低成本模型。

---

## One-Liner / 一句话说明

```python
from model_router import ModelRouter

router = ModelRouter()                          # Initialize / 初始化
tier, confidence, _, _ = router.classify("你好")  # Classify / 分类
print(tier)  # → "t0"  pick the fast model / 选 fast 模型
```

Map the returned `tier` to your own model IDs and you're done.
把 `classify()` 返回的 `tier` 映射到你自己的模型 ID，就完成了。

---

## Quick Start (3 Steps) / 快速开始（3 步）

### 1. Install / 安装

```bash
git clone https://github.com/fengjing1009/agent-model-router.git
cd agent-model-router
pip install -e ".[ml]"
```

### 2. Download Models / 下载模型

```bash
python scripts/download_models.py
```

Models are downloaded to `models/` (about 84MB, gitignored).
模型文件会下载到 `models/` 目录（约 84MB，已 gitignore）。

### 3. Try It / 试一下

```bash
python -c "
from model_router import ModelRouter
r = ModelRouter()
print(r.classify('用 Python 实现一个快速排序'))
"
```

Output / 输出：
```
('t2', 0.87, 'lgbm_main', {'trajectory': 'COLD_START', 'flags': {}})
```
- `t2` = premium tier → complex programming task / 复杂编程任务
- `0.87` = confidence / 置信度

---

## Three Ways to Use It / 三种用法

### Usage 1: Python Direct Import / Python 直接调用（最常见）

Import directly in your Python project, no server needed.
在你的 Python 项目里直接 import，不需要起服务。

```python
from model_router import ModelRouter

# Initialize (auto-loads models/ and tiers.json) / 初始化（自动加载模型和配置）
router = ModelRouter()

# Classify / 分类
tier, confidence, source, extra = router.classify(
    message="帮我分析这段代码的性能问题",
    history=[
        {"role": "user", "content": "这段代码跑得有点慢"},
        {"role": "assistant", "content": "让我看看代码..."},
    ],
)

# Map tier to your model IDs from tiers.json / 根据 tiers.json 映射到模型
models = router.get_tier_models(tier)  # → ["glm-5", "qwen3-max-2026-01-23"]
selected_model = models[0]
```

**Full Integration Example** — insert routing before your Agent calls the LLM API:

**完整集成示例** — 在你的 Agent 调用 LLM API 前插入路由：

```python
from model_router import ModelRouter

router = ModelRouter()

def call_llm(messages):
    """Your LLM call function with automatic model selection."""
    # 1. Get the last user message / 取最后一条用户消息
    user_msg = next(m["content"] for m in reversed(messages) if m["role"] == "user")
    history = messages[:-1]

    # 2. Route / 路由
    tier, _, _, _ = router.classify(message=user_msg, history=history)

    # 3. Pick model by tier / 根据 tier 选模型
    models = router.get_tier_models(tier)
    model = models[0]

    # 4. Call LLM API / 调用 LLM API
    return your_llm_client.chat.completions.create(
        model=model,
        messages=messages,
    )
```

---

### Usage 2: Hermes Agent Integration / Hermes Agent 集成

Hermes Agent is a Python Agent framework. The plugin **intercepts every LLM request** and auto-selects the model.
Hermes Agent 是一个 Python Agent 框架。插件会**拦截每次 LLM 请求**，自动选模型。

**Register the plugin / 注册插件：**

```python
from integrations.hermes.plugin import ModelRouterPlugin

# Create plugin / 创建插件
router_plugin = ModelRouterPlugin(
    bundle_dir="./models",   # Model dir (default ./models) / 模型目录
    auto_route=True,         # Auto-replace model (default True) / 自动替换模型
)

# Register to Hermes's pre_api_request hook
# 注册到 Hermes 的 pre_api_request 钩子
# Hermes calls plugin.pre_api_request(context) before each LLM request
# Hermes 每次发 LLM 请求前会调用 plugin.pre_api_request(context)
```

**Workflow / 工作流程：**

```
Hermes receives user message / Hermes 收到用户消息
  → Triggers pre_api_request hook / 触发 pre_api_request 钩子
    → ModelRouterPlugin calls router.classify()
    → Automatically replaces context["model"] with the optimal model / 自动替换为最优模型
  → Hermes sends LLM request (with the replaced model) / 发送 LLM 请求（使用替换后的模型）
```

**Manual usage (without hook) / 手动使用（不用钩子）：**

```python
plugin = ModelRouterPlugin()

context = {
    "messages": [{"role": "user", "content": "你好"}],
    "model": "qwen3.5-plus",  # Default model / 默认模型
    "session_id": "abc-123",
}

# Call routing, returns modified context / 调用路由，返回修改后的 context
new_context = plugin.pre_api_request(context)

print(new_context["model"])
# → "glm-5" (auto-upgraded to premium / 已自动升级为 premium)

print(new_context["router_metadata"])
# → {"tier": "t2", "confidence": 0.92, ...}
```

---

### Usage 3: OpenClaw Integration (Node.js) / OpenClaw 集成（Node.js）

OpenClaw is a Node.js framework that can't import Python packages directly.
So you **start an HTTP service first**, then use the Node.js plugin to call it.
OpenClaw 是 Node.js 框架，不能直接 import Python 包。
所以需要**先启动 HTTP 服务**，再用 Node.js 插件调用。

#### Step 1: Start the Router Service / 启动路由服务

```bash
uvicorn server.service:app --host 0.0.0.0 --port 8100
```

Verify / 验证服务：
```bash
curl http://localhost:8100/health
# → {"status": "ok", "tiers": ["t0", "t1", "t2", "t3"]}
```

#### Step 2: Configure the OpenClaw Plugin / 配置 OpenClaw 插件

Add to your OpenClaw config / 添加到 OpenClaw 配置：

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

Or set in `.env` / 或在 `.env` 中设置：
```bash
MODEL_ROUTER_URL=http://localhost:8100
```

#### Step 3: Plugin Works Automatically / 插件自动生效

The plugin registers as a `before_model_resolve` hook. Before each LLM request:
插件注册为 `before_model_resolve` 钩子。每次 OpenClaw 发 LLM 请求前：

```
User sends message / 用户发消息
  → OpenClaw triggers before_model_resolve hook / 触发 before_model_resolve 钩子
    → Node.js plugin POSTs to http://localhost:8100/classify / 调用 HTTP 接口
    → Returns tier + model + provider + confidence
    → Plugin returns { modelOverride, providerOverride }
  → OpenClaw sends LLM request (with the replaced model and provider) / 发送 LLM 请求
```

The plugin uses `model` and `provider` returned by the service directly — no hardcoded tier-to-model mapping needed.
插件直接使用服务返回的 `model` 和 `provider`，无需在插件侧硬编码映射。

**Manual API call (without plugin) / 手动调用服务（不用插件）：**

```bash
curl -X POST http://localhost:8100/classify \
  -H "Content-Type: application/json" \
  -d '{
    "message": "帮我写一个 REST API",
    "history": []
  }'
```

Response / 返回：
```json
{
  "tier": "t2",
  "model": "kimi-k2.5",
  "provider": "bailian",
  "confidence": 0.87,
  "source": "v4_phase3",
  "extra": {
    "route_class": "R2",
    "difficulty_score": 0.72,
    "thinking_mode": "T2",
    "prompt_policy": "P2",
    "flags": {}
  }
}
```

```javascript
// Call from Node.js / Node.js 中调用
const res = await fetch("http://localhost:8100/classify", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: "你好", history: [] }),
});
const data = await res.json();
console.log(data.tier); // → "t0"
```

---

## Return Values / 返回值

`router.classify()` returns 4 values / 返回 4 个值：

| Value / 值 | Type / 类型 | Description / 说明 |
|------------|-------------|-------------------|
| `tier` | `str` | Tier ID (`t0`/`t1`/`t2`/`t3`) |
| `confidence` | `float` | Classification confidence (0.0 ~ 1.0) / 分类置信度 |
| `source` | `str` | Decision source (`v4_phase3` / `heuristic` / `user_specified`) |
| `extra` | `dict` | Metadata (route_class, difficulty_score, model, provider, etc.) / 元数据 |

HTTP `/classify` endpoint returns / 端点返回：

| Field / 字段 | Type / 类型 | Description / 说明 |
|--------------|-------------|-------------------|
| `tier` | `str` | Tier ID |
| `model` | `str` | Selected model ID |
| `provider` | `str` | Model provider (`bailian` / `local` etc.) |
| `confidence` | `float` | Classification confidence |
| `source` | `str` | Decision source |
| `extra` | `dict` | Additional metadata |

## Route Classes / 路由类别

Internally, requests are classified as R0 ~ R3, mapped to t0 ~ t3:
路由内部将请求分为 R0 ~ R3，映射到 t0 ~ t3：

| Class / 类别 | Tier / 层级 | Typical Scenarios / 典型场景 |
|--------------|-------------|------------------------------|
| R0 | t0 (fast) | "你好"、"谢谢"、简单问答 |
| R1 | t1 (standard) | 翻译、总结、一般性问答 |
| R2 | t2 (premium) | 编程、分析、调试、长文档处理 |
| R3 | t3 (premium-reasoning) | 架构设计、对比分析、深度推理 |

## Customize Model Tiers / 自定义模型层级

Edit `tiers.json` / 编辑 `tiers.json`：

```json
[
  {
    "tier": "t0",
    "models": [
      {"id": "Qwen3-27B-AWQ", "provider": "local"},
      {"id": "qwen3.5-plus", "provider": "bailian"}
    ],
    "description": "Fast & low cost — Q&A, classification, greetings"
  },
  {
    "tier": "t1",
    "models": [
      {"id": "MiniMax-M2.5", "provider": "bailian"}
    ],
    "description": "Balanced — translation, summarization, routine coding",
    "threshold": 0.4
  },
  {
    "tier": "t2",
    "models": [
      {"id": "kimi-k2.5", "provider": "bailian"}
    ],
    "description": "Best quality — complex coding, code analysis, debugging",
    "threshold": 0.6
  },
  {
    "tier": "t3",
    "models": [
      {"id": "qwen3-coder-plus", "provider": "bailian"}
    ],
    "description": "Deep reasoning — architecture design, complex reasoning, code optimization"
  }
]
```

**Per-model provider**: models within the same tier can come from different providers.
For example, in t0, `Qwen3-27B-AWQ` is locally deployed (`local`) while `qwen3.5-plus` uses bailian (`bailian`).

**每模型独立配置 provider**：同一层级的模型可以来自不同厂商。

Changes take effect immediately. Reload at runtime / 改完立即生效，运行中重载：

```python
router.reload_tiers()
```

List models for a tier / 查看某层级的模型：
```python
router.get_tier_models("t2")
# → ["glm-5", "qwen3-max-2026-01-23"]
```

List all tiers / 查看所有层级：
```python
router.get_available_tiers()
# → ["t0", "t1", "t2", "t3"]
```

## HTTP Endpoints / HTTP 端点

| Endpoint / 端点 | Method / 方法 | Description / 说明 |
|-----------------|---------------|-------------------|
| `/health` | GET | Health check, returns service status and available tiers |
| `/classify` | POST | Classification request, returns tier + model + provider |
| `/tiers` | GET | List all tiers / 列出所有层级 |
| `/tiers/reload` | POST | Reload tier config / 重载层级配置 |
| `/health/status` | GET | Per-model health status and provider for each tier |
| `/health/report` | POST | Report model failure (param `model_name`) |

### Health Check Example / 健康检查示例

```bash
GET /health/status
```
```json
{
  "t0": {
    "models": {
      "Qwen3-27B-AWQ": {"healthy": true, "provider": "local"},
      "qwen3.5-plus": {"healthy": true, "provider": "bailian"}
    }
  },
  "t1": {
    "models": {
      "MiniMax-M2.5": {"healthy": true, "provider": "bailian"}
    }
  }
}
```

```bash
POST /health/report?model_name=kimi-k2.5
```

After a model is reported as failed, it is temporarily excluded after 3 consecutive failures within 300 seconds. The router automatically selects the next healthy model in the same tier.

### User-Specified Model / 指定模型

If a user explicitly specifies a model in the message (e.g., "使用模型 Qwen3-27B-AWQ 回答天气"), the router uses that model directly, skipping classification:

```python
router.classify("使用模型 Qwen3-27B-AWQ 回答成都今天天气")
# → ("Qwen3-27B-AWQ", 1.0, "user_specified", {"model": "Qwen3-27B-AWQ", "provider": "local", ...})
```

Supported formats: `使用模型 XXX`, `用模型 XXX`, `model: XXX`, `model=XXX`

## How It Works (Brief) / 工作原理（简介）

```
User request → Feature extraction(390-dim) → 3-head ensemble → 8-step postprocessing → Tier output
用户请求   → 特征提取(390维)         → 三头集成预测    → 8步后处理         → 输出层级
```

390-dim features: hand-crafted(51) + TF-IDF(102) + context(10) + history(16) + BGE embedding(192) + assistant(12) + continuation/reasoning(7)

390 维特征：手工特征(51) + TF-IDF(102) + 上下文(10) + 历史(16) + BGE嵌入(192) + 助手特征(12) + 延续/推理(7)

3-head ensemble: LightGBM primary + LightGBM auxiliary + ONNX MLP

三头集成：LightGBM 主模型 + LightGBM 辅助模型 + ONNX MLP

8-step postprocessing ensures safe decisions: margin upgrade, R1 rescue, under-routing safety net, flag overrides, etc.

8 步后处理保证决策安全：边界升级、R1 救援、低估安全网、标志覆盖等

---

## Install Options / 安装选项

```bash
pip install -e .          # Basic — HTTP service only, no numpy / 基础版
pip install -e ".[ml]"    # Full — with ML inference (recommended) / 完整版（推荐）
pip install -e ".[ml,dev]" # Dev — with test tools / 开发版
```

| Category / 分类 | Packages / 包 |
|-----------------|---------------|
| Core / 核心 | pydantic, fastapi, uvicorn, pyyaml |
| ML | numpy, onnxruntime, lightgbm, scikit-learn, tokenizers |
| Dev / 开发 | pytest, httpx |

## Environment Variables / 环境变量

| Variable / 变量 | Default / 默认值 | Description / 说明 |
|-----------------|------------------|-------------------|
| `MODEL_ROUTER_MODELS_DIR` | `./models` | Model artifacts directory / 模型文件目录 |
| `MODEL_ROUTER_TIERS_PATH` | `./tiers.json` | Tier config path / 层级配置路径 |
| `MODEL_ROUTER_PORT` | `8100` | HTTP service port / HTTP 服务端口 |
| `MODEL_ROUTER_URL` | `http://localhost:8100` | OpenClaw service URL / OpenClaw 服务地址 |

## Project Structure / 项目结构

```
agent-model-router/
├── src/model_router/          # Core package / 核心包
│   ├── router.py              # ModelRouter main entry / 主入口
│   ├── engine/                # Inference engine / 推理引擎
│   ├── features.py            # Feature extraction / 特征提取
│   ├── controller.py          # Thinking mode / Prompt strategy / 思考模式/Prompt 策略
│   ├── flags.py               # Risk flag detection / 风险标志检测
│   ├── trajectory.py          # Conversation trajectory / 对话轨迹分类
│   └── bge_onnx.py            # BGE ONNX backend / BGE ONNX 后端
├── server/service.py          # FastAPI HTTP service / HTTP 服务
├── scripts/download_models.py # Model download script / 模型下载脚本
├── integrations/              # Framework integrations / 框架集成
│   ├── hermes/plugin.py       # Hermes Agent plugin / Hermes 插件
│   └── openclaw/              # OpenClaw plugin / OpenClaw 插件
├── tiers.json                 # Tier configuration / 层级配置
└── tests/                     # Tests / 测试
```

## License / 许可证

Apache-2.0
