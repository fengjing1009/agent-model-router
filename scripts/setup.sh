#!/bin/bash
# setup.sh - One-click install & start for agent-model-router
#
# Usage:
#   ./setup.sh              # Basic mode (rule-based routing, no models)
#   ./setup.sh --ml         # Full mode (ML inference + download models)
#   ./setup.sh --port 8200  # Custom port (default 8100)

set -e

cd "$(dirname "$0")/.."

MODE="basic"
PORT=8100

for arg in "$@"; do
    case "$arg" in
        --ml)    MODE="ml" ;;
        --port)  PORT="$2"; shift ;;
        --help|-h)
            echo "Usage: $0 [--ml] [--port PORT]"
            echo "  --ml       Install ML dependencies and download models (recommended)"
            echo "  --port     HTTP service port (default: 8100)"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg. Use --help for usage."
            exit 1
            ;;
    esac
done

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv"
SERVICE_NAME="agent-model-router"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "=============================="
echo " agent-model-router Setup"
echo " Mode: $MODE"
echo " Port: $PORT"
echo "=============================="

# Step 1: Create virtual environment
if [ ! -d "$VENV_DIR" ] || [ ! -x "$VENV_DIR/bin/python3" ]; then
    echo "[1/4] Creating virtual environment..."
    # Try to create venv; if python3-venv is missing, try installing it
    python3 -m venv "$VENV_DIR" 2>/dev/null || {
        echo "  python3-venv package not found, trying to install..."
        sudo apt-get install -y python3-venv >/dev/null 2>&1 || {
            echo "  Failed to install python3-venv. Using system Python directly."
            VENV_DIR="$PROJECT_DIR/.venv"
            mkdir -p "$VENV_DIR/bin"
            # Create symlinks to system Python
            ln -sf "$(which python3)" "$VENV_DIR/bin/python3"
            ln -sf "$(which python3)" "$VENV_DIR/bin/python"
            # Use pipx or system pip
            python3 -m pip install --user venv >/dev/null 2>&1 || true
        }
        python3 -m venv "$VENV_DIR"
    }
else
    echo "[1/4] Virtual environment already exists"
fi

# Step 2: Install package
PIP_CMD="$VENV_DIR/bin/pip"
# Try standard install first; if it fails (HTTPS blocked), use HTTP mirror
try_install() {
    $PIP_CMD install -q "$@" 2>/dev/null && return 0
    echo "  Standard pip install failed, trying HTTP mirror..."
    $PIP_CMD config set global.index-url http://mirrors.aliyun.com/pypi/simple/
    $PIP_CMD config set global.trusted-host mirrors.aliyun.com
    $PIP_CMD install -q "$@"
}

if [ "$MODE" = "ml" ]; then
    echo "[2/4] Installing with ML dependencies (numpy, lightgbm, onnxruntime, scikit-learn)..."
    try_install -e ".[ml]"
else
    echo "[2/4] Installing core package..."
    try_install -e .
fi

# Step 3: Download models (ML mode only)
if [ "$MODE" = "ml" ]; then
    if [ -f "${PROJECT_DIR}/models/v4.2_phase3_inference/lgbm_main.bin" ]; then
        echo "[3/4] Models already downloaded, skipping"
    else
        echo "[3/4] Downloading ML models (~84MB)..."
        "$VENV_DIR/bin/python" scripts/download_models.py
    fi
else
    echo "[3/4] Skipping model download (basic mode, run with --ml to enable ML routing)"
fi

# Step 4: Install & start systemd service
echo "[4/4] Installing systemd service..."
if [ -f "$SERVICE_FILE" ]; then
    echo "  Service already exists, reinstalling..."
    sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
fi

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Agent Model Router - LLM Intelligent Routing Engine
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_DIR}/bin/uvicorn server.service:app --host 0.0.0.0 --port ${PORT}
Restart=always
RestartSec=5
Environment=PATH=${VENV_DIR}/bin:/usr/bin
Environment=MODEL_ROUTER_PORT=${PORT}

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

# Wait for service to start
sleep 2

echo ""
echo "=============================="
echo " Setup Complete!"
echo "=============================="
echo ""
echo "Service status:"
sudo systemctl status "$SERVICE_NAME" --no-pager -l 2>/dev/null || systemctl status "$SERVICE_NAME" --no-pager -l 2>/dev/null || true
echo ""
echo "Useful commands:"
echo "  sudo systemctl status ${SERVICE_NAME}    # Check status"
echo "  sudo systemctl restart ${SERVICE_NAME}   # Restart"
echo "  sudo systemctl logs ${SERVICE_NAME}      # View logs"
echo "  sudo systemctl stop ${SERVICE_NAME}      # Stop"
echo ""
echo "Test:"
echo "  curl http://localhost:${PORT}/health"
echo "  curl -X POST http://localhost:${PORT}/classify -H 'Content-Type: application/json' -d '{\"message\": \"你好\"}'"
