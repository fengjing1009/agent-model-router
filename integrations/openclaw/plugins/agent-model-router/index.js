/**
 * agent-model-router OpenClaw Plugin
 *
 * PreRequest hook that calls the agent-model-router HTTP service
 * to classify the user prompt and select the optimal model tier.
 *
 * Configuration (in OpenClaw config):
 * {
 *   "plugins": {
 *     "agent-model-router": {
 *       "enabled": true,
 *       "serviceUrl": "http://localhost:8100"
 *     }
 *   }
 * }
 */

const SERVICE_URL = process.env.MODEL_ROUTER_URL || "http://localhost:8100";

/**
 * OpenClaw preRequest hook.
 * Called before each API request to potentially modify the model selection.
 *
 * @param {Object} context - Request context
 * @param {Array} context.messages - Conversation messages
 * @param {string} context.model - Currently selected model
 * @param {string} [context.sessionId] - Session identifier
 * @param {Object} context.config - Plugin configuration
 * @returns {Promise<Object>} Modified context
 */
async function preRequest(context) {
  const { messages, model, sessionId, config } = context;

  if (!messages || messages.length === 0) {
    return context;
  }

  // Extract user message and history
  let userMessage = "";
  const history = [];
  for (const msg of messages) {
    if (msg.role === "user") {
      userMessage = msg.content || "";
    }
    history.push(msg);
  }

  const serviceUrl = config?.serviceUrl || SERVICE_URL;

  try {
    const response = await fetch(`${serviceUrl}/classify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: userMessage,
        history: history.slice(0, -1), // Exclude current message from history
        session_id: sessionId,
      }),
      signal: AbortSignal.timeout(3000), // 3s timeout
    });

    if (!response.ok) {
      console.warn(
        `[agent-model-router] Service returned ${response.status}, using original model: ${model}`,
      );
      return context;
    }

    const data = await response.json();
    const { tier, confidence, source, extra } = data;

    // Log the routing decision
    console.log(
      `[agent-model-router] Routed to "${tier}" (confidence: ${confidence.toFixed(2)}, source: ${source})`,
    );

    // Set the model from the tier's first available model
    if (extra?.model) {
      context.model = extra.model;
    } else if (tier) {
      // Map tier to model name (fallback mapping — matches tiers.json)
      const tierModelMap = {
        t0: "qwen3.5-plus",
        t1: "kimi-k2.5",
        t2: "glm-5",
        t3: "qwen3-coder-plus",
      };
      context.model = tierModelMap[tier] || model;
    }

    // Attach metadata for downstream use
    context.routerMetadata = { tier, confidence, source, extra };

    return context;
  } catch (error) {
    if (error.name === "TimeoutError" || error.name === "AbortError") {
      console.warn("[agent-model-router] Service timeout, using original model");
    } else {
      console.warn(`[agent-model-router] Error: ${error.message}, using original model`);
    }
    return context;
  }
}

module.exports = {
  preRequest,
};
