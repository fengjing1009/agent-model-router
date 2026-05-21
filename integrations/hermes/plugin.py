"""Hermes Agent plugin — pre_api_request hook for model routing."""

from __future__ import annotations

import os
from pathlib import Path


class ModelRouterPlugin:
    """Hermes Agent plugin that routes requests to optimal model tiers.

    Usage in Hermes:
        1. Add to agent's plugin list
        2. The plugin intercepts pre_api_request and selects the model

    The plugin uses the `pre_api_request` hook to analyze the user's
    prompt and select the optimal model tier before the API call is made.
    """

    def __init__(
        self,
        bundle_dir: str | None = None,
        tiers_path: str | None = None,
        auto_route: bool = True,
    ):
        """Initialize the Hermes plugin.

        Args:
            bundle_dir: Path to model artifacts directory.
            tiers_path: Path to tiers.json configuration.
            auto_route: If True, automatically set model in request context.
        """
        from model_router import ModelRouter

        self.bundle_dir = bundle_dir or os.environ.get("MODEL_ROUTER_MODELS_DIR", "./models")
        self.tiers_path = tiers_path or os.environ.get("MODEL_ROUTER_TIERS_PATH", "./tiers.json")
        self.auto_route = auto_route

        self.router = ModelRouter(
            bundle_dir=self.bundle_dir,
            tiers_path=self.tiers_path,
        )

    def pre_api_request(self, context: dict) -> dict:
        """Hermes pre_api_request hook.

        Analyzes the prompt and selects the optimal model tier.

        Args:
            context: Hermes request context containing:
                - messages: List of conversation messages
                - model: Currently selected model (will be overridden)
                - session_id: Optional session identifier

        Returns:
            Modified context with optimal model selected.
        """
        messages = context.get("messages", [])
        session_id = context.get("session_id")

        # Extract the latest user message
        user_message = ""
        history = []
        for msg in messages:
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
            history.append(msg)

        # Classify
        tier, confidence, source, extra = self.router.classify(
            message=user_message,
            history=history[:-1] if history else [],
            session_id=session_id,
        )

        # Get models for this tier
        tier_models = self.router.get_tier_models(tier)
        selected_model = tier_models[0] if tier_models else context.get("model", "default")

        # Apply routing
        if self.auto_route:
            context["model"] = selected_model

        # Add metadata to context
        context["router_metadata"] = {
            "tier": tier,
            "confidence": confidence,
            "source": source,
            "selected_model": selected_model,
            "extra": extra,
        }

        return context

    def get_router_info(self) -> dict:
        """Get router status and configuration."""
        return {
            "available_tiers": self.router.get_available_tiers(),
            "bundle_dir": str(self.bundle_dir),
            "tiers_path": str(self.tiers_path),
        }
