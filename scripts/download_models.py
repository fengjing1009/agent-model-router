"""Download model artifacts from OpenSquilla GitHub repository."""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

GITHUB_REPO = "opensquilla/opensquilla"
BRANCH = "main"
MODEL_PATH = "src/opensquilla/squilla_router/models/v4.2_phase3_inference"

# All files needed from the V4 Phase 3 inference bundle
FILES = [
    # Root files (binaries are Git LFS, configs are plain text)
    "inference_manifest.json",
    "router.runtime.yaml",
    "version.json",
    "lgbm_main.bin",       # ~38 MB (LFS)
    "lgbm_aux.bin",         # ~3.3 MB (LFS)
    "PROVENANCE.md",
    "artifact_manifest.json",
    # BGE ONNX model
    "bge_onnx/config.json",
    "bge_onnx/model.onnx",        # ~23 MB (LFS)
    "bge_onnx/tokenizer.json",    # ~429 KB
    "bge_onnx/tokenizer_config.json",
    "bge_onnx/special_tokens_map.json",
    "bge_onnx/vocab.txt",         # ~107 KB
    # Feature extractors (pickle files)
    "features/bge_pca.joblib",
    "features/config.pkl",
    "features/meta.json",
    "features/svd.pkl",
    "features/tfidf.pkl",
    # MLP model
    "mlp/model.onnx",             # ~2.3 MB (LFS)
    "mlp/scaler.joblib",          # ~37 KB
]


def _raw_url(repo: str, branch: str, file_path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{MODEL_PATH}/{file_path}"


def download_from_opensquilla(
    output_dir: Path,
    repo: str = GITHUB_REPO,
    branch: str = BRANCH,
) -> Path | None:
    """Download model artifacts directly from OpenSquilla GitHub repository.

    Returns:
        Path to model directory, or None if LFS download failed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    total = len(FILES)
    failed = False
    for i, file_path in enumerate(FILES, 1):
        url = _raw_url(repo, branch, file_path)
        dest = output_dir / file_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        print(f"[{i}/{total}] Downloading {file_path}...")
        try:
            urllib.request.urlretrieve(url, str(dest))
            size = dest.stat().st_size
            if size < 200:
                content = dest.read_text(errors="ignore")
                if content.startswith("version https://git-lfs.github.com/"):
                    print(f"  Git LFS file ({size} bytes pointer)")
                    dest.unlink()
                    failed = True
                    continue
            size_mb = size / (1024 * 1024)
            print(f"  OK ({size_mb:.1f} MB)" if size_mb >= 0.1 else f"  OK ({size:,} bytes)")
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            if dest.exists():
                dest.unlink()
            failed = True

    if failed:
        return None

    total_size = sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())
    print(f"\nDone! Model artifacts downloaded to {output_dir} ({total_size / (1024*1024):.1f} MB)")
    return output_dir


def main():
    parser = argparse.ArgumentParser(
        description="Download model artifacts from OpenSquilla for agent-model-router"
    )
    parser.add_argument(
        "--output", "-o",
        default=os.environ.get("MODEL_ROUTER_MODELS_DIR", "./models/v4.2_phase3_inference"),
        help="Output directory (default: ./models/v4.2_phase3_inference)",
    )
    parser.add_argument(
        "--repo",
        default=GITHUB_REPO,
        help=f"GitHub repo (default: {GITHUB_REPO})",
    )
    parser.add_argument(
        "--branch",
        default=BRANCH,
        help=f"Git branch (default: {BRANCH})",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    result = download_from_opensquilla(
        output_dir=output_dir,
        repo=args.repo,
        branch=args.branch,
    )
    if result is None:
        print("\nFailed: Some files use Git LFS and cannot be downloaded directly.")
        print("Solution: Install git-lfs and clone the OpenSquilla repository:")
        print(f"  git clone https://github.com/{args.repo}.git")
        print(f"  cp -r opensquilla/{MODEL_PATH}/ ./models/v4.2_phase3_inference/")
        sys.exit(1)


if __name__ == "__main__":
    main()
