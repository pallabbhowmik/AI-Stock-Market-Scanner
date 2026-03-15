"""
Model Versioning System
Tracks model versions with metadata, enables rollback, and manages
automatic deployment of best-performing models.
"""
import os
import json
import shutil
import logging
from datetime import datetime

from backend import config

logger = logging.getLogger(__name__)

VERSIONS_DIR = os.path.join(config.MODEL_DIR, "versions")
REGISTRY_PATH = os.path.join(config.MODEL_DIR, "model_registry.json")


def _ensure_dirs():
    os.makedirs(VERSIONS_DIR, exist_ok=True)
    os.makedirs(config.MODEL_DIR, exist_ok=True)


def _load_registry() -> dict:
    """Load the model registry from disk."""
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, "r") as f:
            return json.load(f)
    return {"current_version": None, "versions": []}


def _save_registry(registry: dict):
    _ensure_dirs()
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2, default=str)


def _production_model_files() -> list[str]:
    """List .pkl files that constitute the production model."""
    if not os.path.exists(config.MODEL_DIR):
        return []
    return [f for f in os.listdir(config.MODEL_DIR)
            if f.endswith(".pkl") and os.path.isfile(os.path.join(config.MODEL_DIR, f))]


# ─── Public API ──────────────────────────────────────────────────────────────

def save_version(metrics: dict, dataset_size: int = 0) -> str:
    """
    Snapshot current production model files into a versioned directory.
    Returns the new version id (e.g. "v12").
    """
    _ensure_dirs()
    registry = _load_registry()

    version_num = len(registry["versions"]) + 1
    version_id = f"v{version_num}"
    version_dir = os.path.join(VERSIONS_DIR, version_id)
    os.makedirs(version_dir, exist_ok=True)

    # Copy all .pkl files to version directory
    for fname in _production_model_files():
        src = os.path.join(config.MODEL_DIR, fname)
        shutil.copy2(src, os.path.join(version_dir, fname))

    entry = {
        "version_id": version_id,
        "training_date": datetime.now().isoformat(),
        "accuracy": metrics.get("accuracy", 0),
        "auc": metrics.get("auc", 0),
        "sharpe_ratio": metrics.get("sharpe_ratio", 0),
        "max_drawdown": metrics.get("max_drawdown", 0),
        "profit_factor": metrics.get("profit_factor", 0),
        "dataset_size": dataset_size,
        "models": list(metrics.get("per_model", {}).keys()),
        "deployed": False,
    }

    registry["versions"].append(entry)
    _save_registry(registry)
    logger.info("Saved model version %s", version_id)
    return version_id


def deploy_version(version_id: str) -> bool:
    """
    Copy a versioned model back into production (the main models/ directory).
    """
    version_dir = os.path.join(VERSIONS_DIR, version_id)
    if not os.path.isdir(version_dir):
        logger.error("Version %s not found", version_id)
        return False

    # Replace production .pkl files
    for fname in os.listdir(version_dir):
        if fname.endswith(".pkl"):
            shutil.copy2(
                os.path.join(version_dir, fname),
                os.path.join(config.MODEL_DIR, fname),
            )

    registry = _load_registry()
    for v in registry["versions"]:
        v["deployed"] = v["version_id"] == version_id
    registry["current_version"] = version_id
    _save_registry(registry)
    logger.info("Deployed model version %s to production", version_id)
    return True


def rollback(steps: int = 1) -> str | None:
    """Roll back to a previous version. Returns deployed version_id or None."""
    registry = _load_registry()
    versions = registry["versions"]
    if len(versions) < steps + 1:
        logger.warning("Not enough versions to roll back %d steps", steps)
        return None

    target = versions[-(steps + 1)]
    if deploy_version(target["version_id"]):
        return target["version_id"]
    return None


def get_current_version() -> dict | None:
    """Return metadata for the currently deployed model."""
    registry = _load_registry()
    vid = registry.get("current_version")
    if not vid:
        # No explicit deployment yet — return latest if exists
        if registry["versions"]:
            return registry["versions"][-1]
        return None
    for v in registry["versions"]:
        if v["version_id"] == vid:
            return v
    return None


def get_all_versions() -> list[dict]:
    """Return metadata for all stored model versions."""
    registry = _load_registry()
    return registry["versions"]


def should_deploy(new_metrics: dict, improvement_threshold: float = 0.01) -> bool:
    """
    Decide if a newly trained model should replace the current production model.
    Returns True if the new model's primary score exceeds the current by threshold.
    """
    current = get_current_version()
    if current is None:
        return True  # No production model yet — always deploy

    # Primary score: weighted combination of accuracy and AUC
    def _score(m: dict) -> float:
        return m.get("accuracy", 0) * 0.4 + m.get("auc", 0) * 0.6

    current_score = _score(current)
    new_score = _score(new_metrics)

    if new_score >= current_score + improvement_threshold:
        logger.info(
            "New model (%.4f) beats current (%.4f) by >= %.4f — deploying",
            new_score, current_score, improvement_threshold,
        )
        return True

    logger.info(
        "New model (%.4f) does not beat current (%.4f) — keeping current",
        new_score, current_score,
    )
    return False
