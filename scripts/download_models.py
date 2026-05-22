"""Download model artifacts from OpenSquilla GitHub repository."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import ssl
import urllib.request
from pathlib import Path

# Use Gitee mirror for fast download in China
GITEE_OWNER = "peterpan10009"
GITEE_REPO = "agent-model-router"
BRANCH = "master"
MODEL_PATH = "models/v4.2_phase3_inference"

# Files to download directly from Gitee repo
REPO_FILES = [
    "bge_onnx/config.json",
    "bge_onnx/special_tokens_map.json",
    "bge_onnx/tokenizer.json",
    "bge_onnx/tokenizer_config.json",
    "bge_onnx/vocab.txt",
    "features/meta.json",
    "inference_manifest.json",
    "mlp/scaler.joblib",
    "router.runtime.yaml",
    "version.json",
    "bge_onnx/model.onnx",
    "features/bge_pca.joblib",
    "features/config.pkl",
    "features/svd.pkl",
    "features/tfidf.pkl",
    "lgbm_aux.bin",
    "lgbm_main.bin",
    "mlp/model.onnx",
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _gitee_url(file_path: str) -> str:
    return f"https://gitee.com/{GITEE_OWNER}/{GITEE_REPO}/raw/{BRANCH}/{MODEL_PATH}/{file_path}"


def download(output_dir: Path) -> bool:
    """Download model artifacts from Gitee repo.

    Returns True on success.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    ctx = ssl.create_default_context()
    total = len(REPO_FILES)
    errors = []

    for i, file_path in enumerate(REPO_FILES, 1):
        url = _gitee_url(file_path)
        dest = output_dir / file_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        print(f"[{i}/{total}] Downloading {file_path}...", end=" ")
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
                data = resp.read()

            dest.write_bytes(data)
            size_mb = dest.stat().st_size / (1024 * 1024)
            print(f"OK ({size_mb:.1f} MB)")
        except Exception as e:
            print(f"ERROR: {e}")
            if dest.exists():
                dest.unlink()
            errors.append(file_path)

    if errors:
        print(f"\nFailed to download {len(errors)} file(s):")
        for f in errors:
            print(f"  - {f}")
        return False

    total_size = sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())
    print(f"\nDone! Models downloaded to {output_dir} ({total_size / (1024*1024):.1f} MB)")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Download model artifacts from OpenSquilla for agent-model-router"
    )
    parser.add_argument(
        "--output", "-o",
        default=os.environ.get("MODEL_ROUTER_MODELS_DIR", "./models/v4.2_phase3_inference"),
        help="Output directory (default: ./models/v4.2_phase3_inference)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    if not download(output_dir):
        print("\nDownload failed. Please check your network and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
