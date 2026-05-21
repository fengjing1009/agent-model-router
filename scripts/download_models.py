"""Download model artifacts from OpenSquilla GitHub repository."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.request
import json
from pathlib import Path

GITHUB_REPO = "opensquilla/opensquilla"
BRANCH = "main"
MODEL_PATH = "src/opensquilla/squilla_router/models/v4.2_phase3_inference"

# Base URL that serves actual file content (including Git LFS files)
BASE_URL = f"https://media.githubusercontent.com/media/{GITHUB_REPO}/{BRANCH}/{MODEL_PATH}"

# Expected checksums from artifact_manifest.json (sha256)
EXPECTED = {
    "bge_onnx/config.json": "a7ef8b7733d4d54670d88617be0a426b56152296844e5ff603ef6fda92633da0",
    "bge_onnx/model.onnx": "87847793fac866d65b19cee2e73a6b2a2446a1262ab0911b1dbf9b3e9399ef9d",
    "bge_onnx/special_tokens_map.json": "5d5b662e421ea9fac075174bb0688ee0d9431699900b90662acd44b2a350503a",
    "bge_onnx/tokenizer.json": "48cea5d44424912a6fd1ea647bf4fe50b55ab8b1e5879c3275f80e339e8fae26",
    "bge_onnx/tokenizer_config.json": "470cff6e0353b08e2a6e9b4f61729ecdc47ccb3ced335fa5520e9ce334572d59",
    "bge_onnx/vocab.txt": "45bbac6b341c319adc98a532882e911a9cefc0329aa57bac9ae761c27b291c",
    "features/bge_pca.joblib": "9ee12bcd481a94516b074160e39f0b909c089393d73ffbf0167d3beba995fc23",
    "features/config.pkl": "9e1225d053527975dca018deab6e3ae3fea2070ded20cd01ef0e7eea711cce82",
    "features/meta.json": "fa7c412e32fee37088e03480494e3d0b8ed859e12222e37f22e33aec3778a3de",
    "features/svd.pkl": "5d2af9e78565e58e919fb83c7a01973e394436fd43cf6813c7cd2280aa140172",
    "features/tfidf.pkl": "bb90fb1af13ff1b15104d22b8d1dfc712ae32bf8d7db959ca56b3d7c92872293",
    "inference_manifest.json": "1addef2deddaac2a60800eb631c5878765a49ad100ede4d54022d2d3bf8e2df2",
    "lgbm_aux.bin": "e8749e412d2db861928cb9d8a9b39cdd134a4d71091430ffae014337d4b1aed4",
    "lgbm_main.bin": "5f312db09577bbaf30f87358941974eef6edce7f1424d0e9de21cbd38a646d53",
    "mlp/model.onnx": "e7358ac3f827e8f38a6384ba4f7c6f3227c18898ced95d145adb9272c72137d6",
    "mlp/scaler.joblib": "be1d8d961ac5d20d26b7287dae485f13804b22fdb42c3aea1e1a9186914b9ee",
    "router.runtime.yaml": "cc15d9571c89b59e57afc07d1c994fc45f183c750903996fc11caf301afa0f48",
    "version.json": "806a413d0a8caa5f6b566060c0131b38466e68efce0b09b2d4902f4aef8bfd1c",
}


def _download_url(file_path: str) -> str:
    return f"{BASE_URL}/{file_path}"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def download_from_opensquilla(output_dir: Path) -> Path | None:
    """Download model artifacts from OpenSquilla GitHub repository.

    Uses media.githubusercontent.com CDN which serves actual file content
    (including Git LFS files) without requiring git-lfs.

    Returns:
        Path to model directory, or None if download failed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    files = list(EXPECTED.keys())
    total = len(files)
    errors = []

    for i, file_path in enumerate(files, 1):
        url = _download_url(file_path)
        dest = output_dir / file_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Skip if already exists and checksum matches
        if dest.exists():
            actual = _sha256(dest)
            if actual == EXPECTED[file_path]:
                size_mb = dest.stat().st_size / (1024 * 1024)
                print(f"[{i}/{total}] {file_path} (already up-to-date, {size_mb:.1f} MB)")
                continue

        print(f"[{i}/{total}] Downloading {file_path}...")
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            dest.write_bytes(data)

            # Verify checksum
            actual = _sha256(dest)
            if actual != EXPECTED[file_path]:
                print(f"  WARNING: checksum mismatch (expected {EXPECTED[file_path][:16]}..., got {actual[:16]}...)")
                errors.append(file_path)
            else:
                size_mb = dest.stat().st_size / (1024 * 1024)
                print(f"  OK ({size_mb:.1f} MB)")
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            if dest.exists():
                dest.unlink()
            errors.append(file_path)

    if errors:
        print(f"\nFailed to download {len(errors)} file(s): {', '.join(errors)}")
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
    args = parser.parse_args()

    output_dir = Path(args.output)
    result = download_from_opensquilla(output_dir)
    if result is None:
        print("\nDownload failed. Please check your network and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
