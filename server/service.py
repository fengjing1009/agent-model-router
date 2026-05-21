"""FastAPI HTTP service for agent-model-router."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from model_router import ModelRouter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize router on startup."""
    app.state.router = ModelRouter(
        bundle_dir=os.environ.get("MODEL_ROUTER_MODELS_DIR", "./models"),
        tiers_path=os.environ.get("MODEL_ROUTER_TIERS_PATH", "./tiers.json"),
    )
    yield


app = FastAPI(title="agent-model-router", version="0.1.0", lifespan=lifespan)


class ClassifyRequest(BaseModel):
    message: str
    history: list[dict] | None = None
    session_id: str | None = None


class ClassifyResponse(BaseModel):
    tier: str
    model: str
    provider: str
    confidence: float
    source: str
    extra: dict


@app.get("/health")
def health():
    """Health check endpoint."""
    router: ModelRouter = app.state.router
    return {"status": "ok", "model_loaded": router._core is not None, "tiers": router.get_available_tiers()}


@app.post("/classify", response_model=ClassifyResponse)
def classify(request: ClassifyRequest):
    """Classify a prompt and return the optimal model with provider."""
    router: ModelRouter = app.state.router
    tier, confidence, source, extra = router.classify(
        message=request.message,
        history=request.history,
        session_id=request.session_id,
    )
    model = extra.pop("model", "")
    provider = extra.pop("provider", "")
    return ClassifyResponse(
        tier=tier,
        model=model,
        provider=provider,
        confidence=confidence,
        source=source,
        extra=extra,
    )


@app.post("/health/report")
def report_failure(model_name: str):
    """Report a model failure so it is temporarily excluded from routing."""
    router: ModelRouter = app.state.router
    router.report_failure(model_name)
    return {"status": "ok", "reported_failure": model_name}


@app.get("/health/status")
def health_status():
    """Get current health status of all tier models."""
    router: ModelRouter = app.state.router
    result = {}
    for tier_name in router.get_available_tiers():
        models = router.get_tier_models(tier_name)
        result[tier_name] = {
            "models": {
                m: {
                    "healthy": router._health.is_healthy(m),
                    "provider": router.get_model_provider(m),
                }
                for m in models
            }
        }
    return result


@app.get("/tiers")
def get_tiers():
    """List available model tiers."""
    router: ModelRouter = app.state.router
    return {
        "tiers": [
            {
                "tier": t.tier,
                "models": t.models,
                "description": t.description,
                "threshold": t.threshold,
            }
            for t in router.tiers
        ]
    }


@app.post("/tiers/reload")
def reload_tiers():
    """Reload tier configuration from disk."""
    router: ModelRouter = app.state.router
    router.reload_tiers()
    return {"status": "ok", "tiers": router.get_available_tiers()}


def main():
    """CLI entry point to run the server."""
    import uvicorn
    port = int(os.environ.get("MODEL_ROUTER_PORT", 8100))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
