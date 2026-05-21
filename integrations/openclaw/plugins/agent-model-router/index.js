/**
 * agent-model-router OpenClaw Plugin
 *
 * Registers a before_model_resolve hook that calls the agent-model-router HTTP
 * service to classify the user prompt and select the optimal model tier.
 *
 * The service returns { model, provider } — the plugin uses these directly.
 * Fallback to hardcoded map only when the service doesn't return them.
 */

const DEFAULT_SERVICE_URL = process.env.MODEL_ROUTER_URL || "http://localhost:8100";

// Fallback: used only when service doesn't return model/provider
const TIER_MODEL_MAP = {
  t0: "Qwen3-27B-AWQ",
  t1: "MiniMax-M2.5",
  t2: "kimi-k2.5",
  t3: "qwen3-coder-plus",
};

function register(api) {
  api.on("before_model_resolve", async (event, ctx) => {
    const userMessage = event?.prompt;
    if (!userMessage) return;

    const config = api.pluginConfig || {};
    const serviceUrl = config.serviceUrl || DEFAULT_SERVICE_URL;
    const currentModel = ctx?.modelId;

    try {
      const response = await fetch(`${serviceUrl}/classify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          session_id: ctx?.sessionId,
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
      const { tier, model, provider, confidence, source, extra } = data;

      const newModel = model || extra?.model || TIER_MODEL_MAP[tier];
      const newProvider = provider || extra?.provider;

      api.logger?.info?.(
        `[agent-model-router] Routed to "${tier}" model="${newModel}" provider="${newProvider || "default"}" (confidence: ${confidence.toFixed(2)}, source: ${source})`,
      );

      if (newModel && newModel !== currentModel) {
        const override = { modelOverride: newModel };
        if (newProvider) {
          override.providerOverride = newProvider;
        }
        api.logger?.info?.(
          `[agent-model-router] Model changed: ${currentModel} -> ${newModel} (provider: ${newProvider})`,
        );
        return override;
      }
    } catch (error) {
      if (error.name === "TimeoutError" || error.name === "AbortError") {
        api.logger?.warn?.("[agent-model-router] Service timeout, using original model");
      } else {
        api.logger?.warn?.(`[agent-model-router] Error: ${error.message}, using original model`);
      }
    }
  }, { name: "agent-model-router" });
}

module.exports = { register };
