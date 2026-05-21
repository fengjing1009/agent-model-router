"""ModelRouter — main public API for LLM routing.

Adapted from OpenSquilla's V4Phase3Strategy for standalone use.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from model_router.controller import TIER_ORDER, select_localized_prompt_hint

_ROUTE_CLASS_TO_TIER: dict[str, str] = {
    "R0": "t0",
    "R1": "t1",
    "R2": "t2",
    "R3": "t3",
}


def default_bundle_dir() -> Path:
    """Return the repository-bundled V4 Phase 3 runtime asset directory."""
    return Path(__file__).resolve().parent.parent.parent / "models" / "v4.2_phase3_inference"


@contextmanager
def runtime_src_import_path(bundle_dir: Path) -> Iterator[None]:
    """Temporarily expose the copied bundle's import root."""
    old_path = list(sys.path)
    sys.path.insert(0, str(bundle_dir))
    try:
        yield
    finally:
        sys.path[:] = old_path


def _find_valid_tier(start_tier: str, valid_tiers: list[str]) -> str:
    if not valid_tiers:
        return "t1"
    start_idx = TIER_ORDER.index(start_tier) if start_tier in TIER_ORDER else 1
    for idx in range(start_idx, len(TIER_ORDER)):
        if TIER_ORDER[idx] in valid_tiers:
            return TIER_ORDER[idx]
    for tier in TIER_ORDER:
        if tier in valid_tiers:
            return tier
    return valid_tiers[0]


class ModelRouter:
    """Main entry point for LLM intelligent routing.

    History-aware strategy wrapping the V4 Phase 3 inference core.

    Usage:
        router = ModelRouter(bundle_dir="./models")
        tier, confidence, source, extra = router.classify(
            message="Write a Python script for Dijkstra's algorithm",
            history=[...],
        )
    """

    requires_history = True
    source = "v4_phase3"

    def __init__(
        self,
        bundle_dir: str | Path | None = None,
        tiers_path: str | Path | None = None,
        confidence_threshold: float = 0.5,
        require_router_runtime: bool = False,
        use_aux_head: bool | None = None,
    ) -> None:
        """Initialize the router.

        Args:
            bundle_dir: Path to directory containing model artifacts.
            tiers_path: Path to tiers.json configuration (used for available tier list).
            confidence_threshold: Minimum confidence for tier assignment.
            require_router_runtime: If True, raise on init failure instead of falling back.
            use_aux_head: Enable auxiliary LGBM head for upgrade/downgrade decisions.
        """
        self.bundle_dir = Path(bundle_dir) if bundle_dir else default_bundle_dir()
        self.tiers_path = Path(tiers_path) if tiers_path else Path(__file__).resolve().parent.parent.parent / "tiers.json"
        self._threshold = confidence_threshold
        self._require_router_runtime = require_router_runtime
        self._core: Any | None = None
        self._request_type: Any | None = None
        self._config: dict[str, Any] = {}
        self._model_version = "unknown"
        self._available = False

        try:
            self._init_runtime(use_aux_head=use_aux_head)
        except Exception as exc:
            if require_router_runtime:
                raise RuntimeError(f"failed to initialize V4 Phase 3 router: {exc}") from exc

    def _init_runtime(self, use_aux_head: bool | None) -> None:
        import yaml

        self._validate_bundle()
        self._config = (
            yaml.safe_load((self.bundle_dir / "router.runtime.yaml").read_text(encoding="utf-8"))
            or {}
        )
        self._model_version = self._read_model_version()

        with runtime_src_import_path(self.bundle_dir):
            from model_router.engine.core import InferenceCore
            from model_router.engine.types import InferenceRequest

            resolved_aux_head = (
                bool(self._config.get("v4", {}).get("aux_head_inference", False))
                if use_aux_head is None
                else use_aux_head
            )
            self._request_type = InferenceRequest
            self._core = InferenceCore.from_model_dir(
                str(self.bundle_dir),
                self._config,
                use_aux_head=resolved_aux_head,
            )
        self._available = True

    def _validate_bundle(self) -> None:
        required = ("inference_manifest.json",)
        missing = [name for name in required if not (self.bundle_dir / name).exists()]
        if missing:
            raise FileNotFoundError(f"missing V4 bundle files: {missing}")

    def _read_model_version(self) -> str:
        for name in ("version.json", "inference_manifest.json"):
            path = self.bundle_dir / name
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for key in ("version", "model_version", "bundle_version"):
                value = data.get(key)
                if value:
                    return str(value)
        return "unknown"

    def classify(
        self,
        message: str,
        history: list[dict] | None = None,
        session_id: str | None = None,
    ) -> tuple[str, float, str, dict]:
        """Classify a turn into tier format.

        Args:
            message: The user's message to classify.
            history: Optional conversation history (list of {role, content}).
            session_id: Optional session identifier.

        Returns:
            Tuple of (tier, confidence, source, extra).
        """
        valid_tiers = self.get_available_tiers()

        if not self._available or self._core is None or self._request_type is None:
            return self._unavailable_classify(valid_tiers)

        try:
            request = self._build_request(
                message,
                history or [],
                flags_text_override=None,
            )
            result = self._core.predict(request)
            return self._map_result(result, valid_tiers, message)
        except Exception:
            if self._require_router_runtime:
                raise
            return self._unavailable_classify(valid_tiers)

    def _unavailable_classify(
        self,
        valid_tiers: list[str],
    ) -> tuple[str, float, str, dict]:
        tier = _find_valid_tier("t1", valid_tiers)
        route_class = next(
            (key for key, value in _ROUTE_CLASS_TO_TIER.items() if value == tier),
            "R1",
        )
        return tier, 0.0, "v4_unavailable", {
            "route_class": route_class,
            "top1_label": route_class,
            "thinking_mode": "T1",
            "prompt_policy": "P1",
            "model_version": self._model_version,
        }

    def _build_request(
        self,
        message: str,
        routing_history: list[dict],
        *,
        flags_text_override: str | None = None,
    ) -> Any:
        history_texts = [str(entry.get("content", "")) for entry in routing_history if entry.get("content")]
        prev_assistant_text = None
        prev_assistant_usage = None
        for entry in reversed(routing_history):
            if entry.get("role") == "assistant":
                prev_assistant_text = entry.get("content")
                break

        context_tokens_est = max(
            0,
            (
                len(message)
                + sum(len(text) for text in history_texts)
                + len(prev_assistant_text or "")
            )
            // 4,
        )
        decisions: list[Any] = []
        for entry in routing_history:
            route_class = entry.get("final_route_class") or entry.get("route_class")
            if route_class:
                decisions.append(
                    SimpleNamespace(
                        route_class=str(route_class),
                        difficulty=float(
                            entry.get("difficulty_score", entry.get("difficulty", 0.0)) or 0.0
                        ),
                        margin=float(entry.get("margin", 0.0) or 0.0),
                    )
                )

        request_type = self._request_type
        if request_type is None:
            raise RuntimeError("V4 Phase 3 router request type is not initialized")

        return request_type(
            current_user_text=message,
            history_user_texts=history_texts,
            prev_assistant_text=prev_assistant_text,
            prev_assistant_usage=prev_assistant_usage,
            prev_route_decisions=decisions,
            flags_text_override=flags_text_override,
            context_metadata={
                "turn_index": len(routing_history),
                "history_user_turn_count": len(history_texts),
                "context_tokens_est": context_tokens_est,
                "has_code_block": "```" in message,
                "has_prev_assistant": bool(prev_assistant_text),
            },
        )

    def _map_result(
        self,
        result: Any,
        valid_tiers: list[str],
        message: str,
    ) -> tuple[str, float, str, dict]:
        decision = result.decision
        route_class = str(getattr(decision, "route_class", "R1"))
        tier = _ROUTE_CLASS_TO_TIER.get(route_class, "t1")
        if tier not in valid_tiers:
            tier = _find_valid_tier(tier, valid_tiers)

        probabilities = dict(getattr(result, "probabilities", {}) or {})
        confidence = float(probabilities.get(route_class, 0.0))
        thinking_mode = getattr(decision, "thinking_mode", None)
        prompt_policy = getattr(decision, "prompt_policy", None)
        if thinking_mode is None:
            thinking_mode = "T0"
        if prompt_policy is None:
            prompt_policy = "P0"

        difficulty = float(getattr(decision, "difficulty_score", 0.0))
        intermediates = dict(getattr(result, "intermediates", {}) or {})
        extra: dict[str, Any] = {
            "route_class": route_class,
            "top1_label": route_class,
            "probabilities": probabilities,
            "difficulty": difficulty,
            "difficulty_score": difficulty,
            "margin": float(getattr(decision, "margin", 0.0)),
            "thinking_mode": str(thinking_mode),
            "prompt_policy": str(prompt_policy),
            "flags": dict(getattr(decision, "flags", {}) or {}),
            "aux_decision_probs": getattr(result, "aux_decision_probs", None),
            "aux_downgrade_applied": bool(getattr(decision, "aux_downgrade_applied", False)),
            "sticky_applied": bool(getattr(decision, "sticky_applied", False)),
            "selected_model": getattr(decision, "selected_model", None),
            "model_version": self._model_version,
        }
        prompt_hint = self._prompt_hint(str(prompt_policy), message) or intermediates.get(
            "prompt_hint"
        )
        if prompt_hint:
            extra["prompt_hint"] = str(prompt_hint)
        return tier, confidence, self.source, extra

    def _prompt_hint(self, prompt_policy: str, message: str | None = None) -> str | None:
        policy_cfg = self._config.get("prompt_policies", {}).get(prompt_policy, {})
        return select_localized_prompt_hint(policy_cfg, message)

    def get_tier_models(self, tier: str) -> list[str]:
        """Get the list of model IDs for a given tier."""
        tiers = self._load_tiers()
        for t in tiers:
            if t["tier"] == tier:
                return t.get("models", [])
        return []

    def reload_tiers(self) -> None:
        """Reload tier configuration from disk."""
        # Runtime config is reloaded on next classify
        pass

    def get_available_tiers(self) -> list[str]:
        """Get list of all available tier names."""
        tiers = self._load_tiers()
        return [t["tier"] for t in tiers]

    def _load_tiers(self) -> list[dict]:
        """Load tier configuration from JSON file."""
        if not self.tiers_path.exists():
            return [
                {"tier": "t0", "models": ["claude-haiku-4-5-20251001"]},
                {"tier": "t1", "models": ["claude-sonnet-4-20250514"]},
                {"tier": "t2", "models": ["claude-sonnet-4-5-20250514"]},
                {"tier": "t3", "models": ["claude-opus-4-6"]},
            ]
        text = self.tiers_path.read_text()
        lines = [l for l in text.splitlines() if not l.strip().startswith('#')]
        return json.loads('\n'.join(lines))
