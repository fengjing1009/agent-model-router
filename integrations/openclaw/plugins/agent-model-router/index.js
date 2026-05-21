/**
 * agent-model-router OpenClaw Plugin
 *
 * Registers a before_model_resolve hook that calls the agent-model-router HTTP
 * service to classify the user prompt and select the optimal model tier.
 *
 * Configuration (in OpenClaw config):
 * {
 *   "plugins": {
 *     "entries": {
 *       "agent-model-router": {
 *         "enabled": true,
 *         "serviceUrl": "http://localhost:8100"
 *       }
 *     }
 *   }
 * }
 */

const DEFAULT_SERVICE_URL = process.env.MODEL_ROUTER_URL || "http://localhost:8100";

/**
 * Core routing logic — calls the HTTP service and modifies the model.
 */
async function routeModel(api, ctx) {
  const config = api.pluginConfig || {};
  const serviceUrl = config.serviceUrl || DEFAULT_SERVICE_URL;

  // Extract messages from conversation context
  const messages = ctx.conversation?.messages || ctx.messages || [];
  const sessionId = ctx.sessionId || ctx.session?.id;
  const currentModel = ctx.model;

  if (!messages || messages.length === 0) {
    return;
  }

  // Extract last user message and history
  let userMessage = "";
  const history = [];
  for (const msg of messages) {
    if (msg.role === "user") {
      userMessage = msg.content || "";
    }
    history.push(msg);
  }

  if (!userMessage) return;

  try {
    const response = await fetch(`${serviceUrl}/classify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: userMessage,
        history: history.slice(0, -1),
        session_id: sessionId,
      }),
      signal: AbortSignal.timeout(3000),
    });

    if (!response.ok) {
      api.logger?.warn?.(
        `[agent-model-router] Service returned ${response.status}, using original model: ${currentModel}`,
      );
      return;
    }

    const data = await response.json();
    const { tier, confidence, source, extra } = data;

    // Log the routing decision
    api.logger?.info?.(
      `[agent-model-router] Routed to "${tier}" (confidence: ${confidence.toFixed(2)}, source: ${source})`,
    );

    // Map tier to model name (matches tiers.json)
    const tierModelMap = {
      t0: "qwen3.5-plus",
      t1: "kimi-k2.5",
      t2: "glm-5",
      t3: "qwen3-coder-plus",
    };

    const newModel = extra?.model || tierModelMap[tier];
    if (newModel && newModel !== currentModel) {
      api.logger?.info?.(
        `[agent-model-router] Model changed: ${currentModel} → ${newModel}`,
      );
      // Set the model — OpenClaw reads ctx.model
      ctx.model = newModel;
      if (ctx.options) ctx.options.model = newModel;
    }

    // Attach metadata
    ctx.routerMetadata = { tier, confidence, source, extra };
  } catch (error) {
    if (error.name === "TimeoutError" || error.name === "AbortError") {
      api.logger?.warn?.("[agent-model-router] Service timeout, using original model");
    } else {
      api.logger?.warn?.(`[agent-model-router] Error: ${error.message}, using original model`);
    }
  }
}

/**
 * OpenClaw plugin register function.
 */
export function register(api) {
  api.registerHook("before_model_resolve", async (ctx) => {
    await routeModel(api, ctx);
    return ctx;
  }, { name: "agent-model-router" });
}

export default { register };
