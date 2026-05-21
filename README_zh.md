# agent-model-router

> LLM 智能路由引擎 — 把用户请求自动分到最合适的模型。

🌐 **[English README →](README.md)**

复杂任务用高级推理模型，简单查询用快速/低成本模型。
每条消息分析后自动选择最优模型，节省成本、保证质量。

---

## 一句话说明

```python
from model_router import ModelRouter

router = ModelRouter()                          # 初始化
tier, confidence, _, _ = router.classify("你好") # 分类
print(tier)  # → "t0"  选 fast 模型
```

把 `classify()` 返回的 `tier` 映射到你自己的模型 ID，就完成了。

---

## 快速开始（3 步）

### 1. 安装

```bash
git clone https://github.com/fengjing1009/agent-model-router.git
cd agent-model-router
pip install -e ".[ml]"
```

### 2. 下载模型

```bash
python scripts/download_models.py
```

模型文件会下载到 `models/` 目录（约 500MB，gitignore 掉了）。

### 3. 试一下

```bash
python -c "
from model_router import ModelRouter
r = ModelRouter()
print(r.classify('用 Python 实现一个快速排序'))
"
```

输出类似：
```
('t2', 0.87, 'lgbm_main', {'trajectory': 'COLD_START', 'flags': {}})
```
- `t2` = premium 层级 → 复杂编程任务
- `0.87` = 置信度

---

## 三种用法

### 用法 1：Python 直接调用（最常见）

在你的 Python 项目里直接 import，不需要起服务。

```python
from model_router import ModelRouter

# 初始化（自动加载 models/ 和 tiers.json）
router = ModelRouter()

# 调用
tier, confidence, source, extra = router.classify(
    message="帮我分析这段代码的性能问题",
    history=[
        {"role": "user", "content": "这段代码跑得有点慢"},
        {"role": "assistant", "content": "让我看看代码..."},
    ],
)

# 根据你的 tiers.json 映射到具体模型
models = router.get_tier_models(tier)  # → ["glm-5", "qwen3-max-2026-01-23"]
selected_model = models[0]
```

**完整集成示例** — 在你的 Agent 调用 LLM API 前插入路由：

```python
from model_router import ModelRouter

router = ModelRouter()

def call_llm(messages):
    """你的 LLM 调用函数，自动选择模型。"""
    # 1. 取最后一条用户消息
    user_msg = next(m["content"] for m in reversed(messages) if m["role"] == "user")
    history = messages[:-1]

    # 2. 路由
    tier, _, _, _ = router.classify(message=user_msg, history=history)

    # 3. 根据 tier 选模型
    models = router.get_tier_models(tier)
    model = models[0]

    # 4. 调用 LLM API
    return your_llm_client.chat.completions.create(
        model=model,
        messages=messages,
    )
```

---

### 用法 2：Hermes Agent 集成

Hermes Agent 是一个 Python Agent 框架。插件会**拦截每次 LLM 请求**，自动选模型。

**在 Hermes 配置中注册插件：**

```python
from integrations.hermes.plugin import ModelRouterPlugin

# 创建插件
router_plugin = ModelRouterPlugin(
    bundle_dir="./models",   # 模型目录（默认 ./models）
    auto_route=True,         # 自动替换 model（默认 True）
)

# 注册到 Hermes 的 pre_api_request 钩子
# Hermes 每次发 LLM 请求前会调用 plugin.pre_api_request(context)
```

**工作流程：**

```
Hermes 收到用户消息
  → 触发 pre_api_request 钩子
    → ModelRouterPlugin 调用 router.classify()
    → 自动把 context["model"] 替换为最优模型
  → Hermes 发送 LLM 请求（使用替换后的 model）
```

**手动使用（不用钩子）：**

```python
plugin = ModelRouterPlugin()

context = {
    "messages": [{"role": "user", "content": "你好"}],
    "model": "qwen3.5-plus",  # 默认模型
    "session_id": "abc-123",
}

# 调用路由，返回修改后的 context
new_context = plugin.pre_api_request(context)

print(new_context["model"])
# → "glm-5" （已自动替换为 premium 模型）

print(new_context["router_metadata"])
# → {"tier": "t2", "confidence": 0.92, ...}
```

---

### 用法 3：OpenClaw 集成（Node.js）

OpenClaw 是 Node.js 框架，不能直接 import Python 包。
所以需要**先启动 HTTP 服务**，再用 Node.js 插件调用。

#### 第 1 步：启动路由服务

```bash
uvicorn server.service:app --host 0.0.0.0 --port 8100
```

验证服务：
```bash
curl http://localhost:8100/health
# → {"status": "ok", "tiers": ["t0", "t1", "t2", "t3"]}
```

#### 第 2 步：配置 OpenClaw 插件

在 OpenClaw 配置中添加：

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

或在 `.env` 中设置：
```bash
MODEL_ROUTER_URL=http://localhost:8100
```

#### 第 3 步：插件自动生效

插件 `integrations/openclaw/plugins/agent-model-router/index.js`
注册为 `before_model_resolve` 钩子。每次 OpenClaw 发 LLM 请求前：

```
用户发消息
  → OpenClaw 触发 before_model_resolve 钩子
    → Node.js 插件 POST 到 http://localhost:8100/classify
    → 返回 tier + model + provider + confidence
    → 插件返回 { modelOverride, providerOverride }
  → OpenClaw 发送 LLM 请求（使用替换后的 model 和 provider）
```

插件直接使用服务返回的 `model` 和 `provider`，无需在插件侧硬编码映射。

**手动调用服务（不用插件）：**

```bash
curl -X POST http://localhost:8100/classify \
  -H "Content-Type: application/json" \
  -d '{
    "message": "帮我写一个 REST API",
    "history": []
  }'
```

返回：
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
// 在 Node.js 中调用
const res = await fetch("http://localhost:8100/classify", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: "你好", history: [] }),
});
const data = await res.json();
console.log(data.tier); // → "t0"
```

---

## 返回值说明

`router.classify()` 返回 4 个值：

| 值 | 类型 | 说明 |
|----|------|------|
| `tier` | `str` | 层级 ID（`t0`/`t1`/`t2`/`t3`） |
| `confidence` | `float` | 分类置信度（0.0 ~ 1.0） |
| `source` | `str` | 决策来源（`v4_phase3` / `heuristic` / `user_specified`） |
| `extra` | `dict` | 元数据（route_class、difficulty_score、model、provider 等） |

HTTP `/classify` 端点返回：

| 字段 | 类型 | 说明 |
|------|------|------|
| `tier` | `str` | 层级 ID |
| `model` | `str` | 选中的模型 ID |
| `provider` | `str` | 模型提供商（`bailian` / `local` 等） |
| `confidence` | `float` | 分类置信度 |
| `source` | `str` | 决策来源 |
| `extra` | `dict` | 额外元数据 |

## 路由类别

路由内部将请求分为 R0 ~ R3，映射到 t0 ~ t3：

| 类别 | 层级 | 典型场景 |
|------|------|----------|
| R0 | t0 (fast) | "你好"、"谢谢"、简单问答 |
| R1 | t1 (standard) | 翻译、总结、一般性问答 |
| R2 | t2 (premium) | 编程、分析、调试、长文档处理 |
| R3 | t3 (premium-reasoning) | 架构设计、对比分析、深度推理 |

## 自定义模型层级

编辑 `tiers.json`：

```json
[
  {
    "tier": "t0",
    "models": [
      {"id": "Qwen3-27B-AWQ", "provider": "local"},
      {"id": "qwen3.5-plus", "provider": "bailian"}
    ],
    "description": "快速 & 低成本 — 简单问答、分类、寒暄"
  },
  {
    "tier": "t1",
    "models": [
      {"id": "MiniMax-M2.5", "provider": "bailian"}
    ],
    "description": "均衡 — 翻译、总结、常规编程任务",
    "threshold": 0.4
  },
  {
    "tier": "t2",
    "models": [
      {"id": "kimi-k2.5", "provider": "bailian"}
    ],
    "description": "最佳质量 — 复杂编程、代码分析、调试",
    "threshold": 0.6
  },
  {
    "tier": "t3",
    "models": [
      {"id": "qwen3-coder-plus", "provider": "bailian"}
    ],
    "description": "深度推理 — 架构设计、复杂推理、代码优化"
  }
]
```

**每模型独立配置 provider**：同一层级的模型可以来自不同厂商。
例如 t0 中 `Qwen3-27B-AWQ` 是本地部署（`local`），`qwen3.5-plus` 走百炼（`bailian`）。

改完立即生效。运行中重载：

```python
router.reload_tiers()
```

查看某层级的模型：
```python
router.get_tier_models("t2")
# → ["glm-5", "qwen3-max-2026-01-23"]
```

查看所有层级：
```python
router.get_available_tiers()
# → ["t0", "t1", "t2", "t3"]
```

## HTTP 服务端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查，返回服务状态和可用层级 |
| `/classify` | POST | 分类请求，返回 tier + model + provider |
| `/tiers` | GET | 列出所有层级 |
| `/tiers/reload` | POST | 重载层级配置 |
| `/health/status` | GET | 各 tier 下每个模型的健康状态和 provider |
| `/health/report` | POST | 报告模型失败（参数 `model_name`） |

### 健康检查示例

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

报告模型失败后，该模型在 300 秒内连续 3 次失败会被暂时排除，
路由器自动选择同层级下一个健康的模型。

## 指定模型

如果用户在消息中明确指定了模型（如 "使用模型 Qwen3-27B-AWQ 回答天气"），
路由器会直接使用该模型，跳过分类逻辑：

```python
router.classify("使用模型 Qwen3-27B-AWQ 回答成都今天天气")
# → ("Qwen3-27B-AWQ", 1.0, "user_specified", {"model": "Qwen3-27B-AWQ", "provider": "local", ...})
```

支持的指定格式：`使用模型 XXX`、`用模型 XXX`、`model: XXX`、`model=XXX`

## 工作原理（简介）

```
用户请求 → 特征提取(390维) → 三头集成预测 → 8步后处理 → 输出层级
```

390 维特征包含：手工特征(51) + TF-IDF(102) + 上下文(10) + 历史(16) + BGE嵌入(192) + 助手特征(12) + 延续/推理(7)

三头集成：LightGBM 主模型 + LightGBM 辅助模型 + ONNX MLP

8 步后处理保证决策安全：边界升级、R1 救援、低估安全网、标志覆盖等

---

## 安装选项

```bash
pip install -e .          # 基础 — 只跑 HTTP 服务，不需要 numpy
pip install -e ".[ml]"    # 完整 — 含 ML 推理（推荐）
pip install -e ".[ml,dev]" # 开发 — 含测试工具
```

| 分类 | 包 |
|------|-----|
| 核心 | pydantic, fastapi, uvicorn, pyyaml |
| ML | numpy, onnxruntime, lightgbm, scikit-learn, tokenizers |
| 开发 | pytest, httpx |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MODEL_ROUTER_MODELS_DIR` | `./models` | 模型文件目录 |
| `MODEL_ROUTER_TIERS_PATH` | `./tiers.json` | 层级配置路径 |
| `MODEL_ROUTER_PORT` | `8100` | HTTP 服务端口 |
| `MODEL_ROUTER_URL` | `http://localhost:8100` | OpenClaw 服务地址 |

## 项目结构

```
agent-model-router/
├── src/model_router/          # 核心包
│   ├── router.py              # ModelRouter 主入口
│   ├── engine/                # 推理引擎
│   ├── features.py            # 特征提取
│   ├── controller.py          # 思考模式/Prompt 策略
│   ├── flags.py               # 风险标志检测
│   ├── trajectory.py          # 对话轨迹分类
│   └── bge_onnx.py            # BGE ONNX 后端
├── server/service.py          # FastAPI HTTP 服务
├── scripts/download_models.py # 模型下载脚本
├── integrations/              # 框架集成
│   ├── hermes/plugin.py       # Hermes Agent 插件
│   └── openclaw/              # OpenClaw 插件
├── tiers.json                 # 层级配置
└── tests/                     # 测试
```

## 许可证

Apache-2.0
