"""Download model artifacts from GitHub Releases."""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

GITHUB_REPO = "your-org/agent-model-router"
RELEASE_TAG = "v0.1.0"
ASSET_NAME = "model-bundle-v0.1.0.tar.gz"


def download_from_github(
    output_dir: Path,
    repo: str = GITHUB_REPO,
    tag: str = RELEASE_TAG,
    asset: str = ASSET_NAME,
) -> Path:
    """Download model bundle from GitHub Releases.

    Returns:
        Path to extracted model directory.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    download_url = f"https://github.com/{repo}/releases/download/{tag}/{asset}"
    archive_path = output_dir / asset

    print(f"Downloading {asset} from GitHub Releases...")
    print(f"  URL: {download_url}")
    print(f"  To: {archive_path}")

    try:
        urllib.request.urlretrieve(download_url, str(archive_path))
        print(f"  Downloaded {archive_path.stat().st_size / (1024*1024):.1f} MB")
    except Exception as e:
        print(f"  ERROR: Failed to download: {e}", file=sys.stderr)
        print()
        print(f"Manual download: https://github.com/{repo}/releases/download/{tag}/{asset}")
        print(f"Then place the file at: {archive_path}")
        sys.exit(1)

    # Extract
    print(f"Extracting to {output_dir}...")
    import tarfile
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(path=str(output_dir))

    # Clean up archive
    archive_path.unlink()

    print("Done! Model artifacts are ready.")
    return output_dir


def main():
    parser = argparse.ArgumentParser(description="Download model artifacts for agent-model-router")
    parser.add_argument(
        "--output", "-o",
        default=os.environ.get("MODEL_ROUTER_MODELS_DIR", "./models"),
        help="Output directory (default: ./models)",
    )
    parser.add_argument(
        "--url", "-u",
        default=None,
        help="Direct download URL (overrides GitHub Releases)",
    )
    parser.add_argument(
        "--repo",
        default=GITHUB_REPO,
        help=f"GitHub repo (default: {GITHUB_REPO})",
    )
    parser.add_argument(
        "--tag",
        default=RELEASE_TAG,
        help=f"Release tag (default: {RELEASE_TAG})",
    )
    args = parser.parse_args()

    if args.url:
        # Direct URL download
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        archive_path = output_dir / "model-bundle.tar.gz"
        print(f"Downloading from {args.url}...")
        urllib.request.urlretrieve(args.url, str(archive_path))
        print(f"Extracting to {output_dir}...")
        import tarfile
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=str(output_dir))
        archive_path.unlink()
        print("Done!")
    else:
        download_from_github(
            output_dir=Path(args.output),
            repo=args.repo,
            tag=args.tag,
        )


if __name__ == "__main__":
    main()
