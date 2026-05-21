"""Smoke tests for ModelRouter."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_tiers():
    """Create a temporary tiers.json for testing."""
    tiers = [
        {"tier": "t0", "models": ["qwen3.5-plus"]},
        {"tier": "t1", "models": ["kimi-k2.5"]},
        {"tier": "t2", "models": ["glm-5", "qwen3-max-2026-01-23"]},
        {"tier": "t3", "models": ["qwen3-coder-plus"]},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(tiers, f)
        f.flush()
        yield f.name


@pytest.fixture
def temp_models_dir():
    """Create a temporary models directory."""
    d = tempfile.mkdtemp()
    yield Path(d)


def test_import():
    """Test that ModelRouter can be imported."""
    from model_router import ModelRouter
    assert ModelRouter is not None


def test_router_init(temp_tiers, temp_models_dir):
    """Test router initialization with custom paths."""
    from model_router import ModelRouter
    router = ModelRouter(
        bundle_dir=str(temp_models_dir),
        tiers_path=temp_tiers,
    )
    assert router.get_available_tiers() == ["t0", "t1", "t2", "t3"]


def test_router_default_tiers():
    """Test router falls back to default tiers when no config file."""
    from model_router import ModelRouter
    router = ModelRouter(tiers_path="/nonexistent/path/tiers.json")
    assert len(router.get_available_tiers()) == 4


def test_get_tier_models(temp_tiers, temp_models_dir):
    """Test retrieving models for a tier."""
    from model_router import ModelRouter
    router = ModelRouter(
        bundle_dir=str(temp_models_dir),
        tiers_path=temp_tiers,
    )
    models = router.get_tier_models("t2")
    assert "glm-5" in models


def test_reload_tiers(temp_tiers, temp_models_dir):
    """Test tier reloading."""
    from model_router import ModelRouter
    router = ModelRouter(
        bundle_dir=str(temp_models_dir),
        tiers_path=temp_tiers,
    )
    # Modify tiers file
    tiers = json.loads(Path(temp_tiers).read_text())
    tiers.append({"tier": "t4", "models": ["qwen3-coder-next"]})
    Path(temp_tiers).write_text(json.dumps(tiers))
    # get_available_tiers loads from file each call
    assert "t4" in router.get_available_tiers()


def test_classify_returns_tuple(temp_tiers, temp_models_dir):
    """Test that classify returns a 4-tuple (falls back when no model artifacts)."""
    from model_router import ModelRouter
    router = ModelRouter(
        bundle_dir=str(temp_models_dir),
        tiers_path=temp_tiers,
    )
    # Without model artifacts, returns fallback result
    tier, confidence, source, extra = router.classify(
        message="Hello, how are you?",
    )
    assert isinstance(tier, str)
    assert isinstance(confidence, float)
    assert isinstance(source, str)
    assert isinstance(extra, dict)
    assert source == "v4_unavailable"


def test_trajectory_detection():
    """Test trajectory classification."""
    from model_router.trajectory import classify, Trajectory

    assert classify([]) == Trajectory.COLD_START

    from types import SimpleNamespace
    h1 = [
        SimpleNamespace(route_class="R0", difficulty=0.1, margin=0.9),
        SimpleNamespace(route_class="R0", difficulty=0.2, margin=0.8),
        SimpleNamespace(route_class="R1", difficulty=0.15, margin=0.7),
    ]
    assert classify(h1) == Trajectory.STABLE_LOW

    h2 = [
        SimpleNamespace(route_class="R2", difficulty=2.0, margin=0.5),
        SimpleNamespace(route_class="R3", difficulty=2.5, margin=0.6),
    ]
    assert classify(h2) == Trajectory.STABLE_HIGH


def test_flag_detection():
    """Test risk flag computation."""
    from model_router.flags import compute_flags, RoutingFlags

    # Empty config → all flags false
    flags = compute_flags("Hello world", {})
    assert isinstance(flags, RoutingFlags)
    assert not flags.high_risk
    assert not flags.debug


def test_controller():
    """Test controller functions."""
    from model_router.controller import (
        TIER_ORDER,
        derive_thinking_mode,
        derive_prompt_policy,
    )

    assert TIER_ORDER == ["t0", "t1", "t2", "t3"]

    # Derive thinking mode from probs
    mode = derive_thinking_mode([0.9, 0.05, 0.03, 0.02])
    assert mode == "T0"

    mode = derive_thinking_mode([0.02, 0.03, 0.05, 0.9])
    assert mode == "T3"

    # Derive prompt policy
    policy = derive_prompt_policy([0.9, 0.05, 0.03, 0.02])
    assert policy == "P0"


def test_artifacts_validation(temp_models_dir):
    """Test InferenceArtifacts manifest validation."""
    from model_router.engine.artifacts import InferenceArtifacts

    # Valid manifest
    manifest = {
        "feature_dim": 390,
        "mlp_input_dim": 1536,
        "temperature": 1.5,
        "per_class_alpha": [0.3, 0.3, 0.2, 0.2],
    }
    manifest_path = temp_models_dir / "inference_manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    artifacts = InferenceArtifacts.load(str(temp_models_dir))
    assert artifacts.manifest["feature_dim"] == 390

    # Invalid manifest
    bad_manifest = {"feature_dim": 100, "mlp_input_dim": 1536, "temperature": 1.5, "per_class_alpha": [0.3, 0.3, 0.2, 0.2]}
    (temp_models_dir / "inference_manifest.json").write_text(json.dumps(bad_manifest))
    with pytest.raises(ValueError, match="feature_dim mismatch"):
        InferenceArtifacts.load(str(temp_models_dir))
