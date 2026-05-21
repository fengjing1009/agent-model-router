#!/bin/bash
# setup.sh - One-click install & start for agent-model-router
#
# Usage:
#   ./setup.sh              # Basic mode (rule-based routing, no models needed)
#   ./setup.sh --ml         # Full mode (ML inference + download models)
#   ./setup.sh --server     # Basic + start HTTP service
#   ./setup.sh --ml --server # Full + start HTTP service

set -e

cd "$(dirname "$0")/.."

MODE="basic"
SERVER=false

for arg in "$@"; do
    case "$arg" in
        --ml)    MODE="ml" ;;
        --server) SERVER=true ;;
        --help|-h)
            echo "Usage: $0 [--ml] [--server]"
            echo "  --ml       Install ML dependencies and download models (recommended)"
            echo "  --server   Start HTTP service after installation"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg. Use --help for usage."
            exit 1
            ;;
    esac
done

echo "=============================="
echo " agent-model-router Setup"
echo " Mode: $MODE"
echo " Start server: $SERVER"
echo "=============================="

# Step 1: Create virtual environment
if [ ! -d ".venv" ]; then
    echo "[1/4] Creating virtual environment..."
    python3 -m venv .venv
else
    echo "[1/4] Virtual environment already exists"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# Step 2: Install package
if [ "$MODE" = "ml" ]; then
    echo "[2/4] Installing with ML dependencies (numpy, lightgbm, onnxruntime, scikit-learn)..."
    pip install -e ".[ml]" -q
else
    echo "[2/4] Installing core package..."
    pip install -e . -q
fi

# Step 3: Download models (ML mode only)
if [ "$MODE" = "ml" ]; then
    if [ -f "models/v4.2_phase3_inference/lgbm_main.bin" ]; then
        echo "[3/4] Models already downloaded, skipping"
    else
        echo "[3/4] Downloading ML models (~84MB)..."
        python scripts/download_models.py
    fi
else
    echo "[3/4] Skipping model download (basic mode, run with --ml to enable ML routing)"
fi

# Step 4: Start HTTP service (if requested)
if [ "$SERVER" = true ]; then
    echo "[4/4] Starting HTTP service on port 8100..."
    echo ""
    echo "Test it in another terminal:"
    echo "  curl -X POST http://localhost:8100/classify -H 'Content-Type: application/json' -d '{\"message\": \"你好\"}'"
    echo ""
    uvicorn server.service:app --host 0.0.0.0 --port 8100
else
    echo "[4/4] Done!"
    echo ""
    echo "Usage:"
    echo "  # Python direct import / Python 直接调用:"
    echo "  source .venv/bin/activate"
    echo '  python -c "from model_router import ModelRouter; print(ModelRouter().classify('\''你好'\''))"'
    echo ""
    echo "  # Start HTTP service / 启动 HTTP 服务:"
    echo "  $0 $([ "$MODE" = ml ] && echo --ml )--server"
    echo "  # or manually:"
    echo "  source .venv/bin/activate && uvicorn server.service:app --host 0.0.0.0 --port 8100"
fi
