#!/bin/bash
#
# Installation script for Validator Performance Analyzer Web Application
# Deploys the application as a systemd service
#
# Usage:
#   sudo git clone <repo> /opt/performance-analyzer
#   cd /opt/performance-analyzer
#   sudo ./install.sh
#

set -e

echo "================================================"
echo "Performance Analyzer - Installation Script"
echo "================================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script must be run as root (use sudo)"
    exit 1
fi

# Configuration
APP_NAME="performance-analyzer"
APP_DIR="/opt/${APP_NAME}"
SERVICE_USER="performance-analyzer"
SERVICE_PORT="8000"

# Detect if running from target directory or elsewhere
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Configuration:"
echo "  App Directory: ${APP_DIR}"
echo "  Service User: ${SERVICE_USER}"
echo "  Service Port: ${SERVICE_PORT}"
echo "  Script Location: ${SCRIPT_DIR}"
echo ""

# Create service user if doesn't exist
if ! id "${SERVICE_USER}" &>/dev/null; then
    echo "Creating service user: ${SERVICE_USER}..."
    useradd --system --no-create-home --shell /bin/false ${SERVICE_USER}
else
    echo "✓ Service user already exists"
fi

# Handle installation location
if [ "$SCRIPT_DIR" = "$APP_DIR" ]; then
    echo "✓ Running from target directory (git clone deployment)"
    # Create data directories
    mkdir -p ${APP_DIR}/data
    mkdir -p ${APP_DIR}/backend/.cache
else
    echo "Copying files to ${APP_DIR}..."
    mkdir -p ${APP_DIR}
    mkdir -p ${APP_DIR}/data
    mkdir -p ${APP_DIR}/backend/.cache
    cp -r backend ${APP_DIR}/
    cp -r frontend ${APP_DIR}/
    cp deploy.sh ${APP_DIR}/ 2>/dev/null || true
fi

# Set ownership - root owns code, service user owns data
echo "Setting file ownership..."
chown -R root:${SERVICE_USER} ${APP_DIR}
chmod -R g+r ${APP_DIR}
chmod g+x ${APP_DIR} ${APP_DIR}/backend ${APP_DIR}/frontend
chown -R ${SERVICE_USER}:${SERVICE_USER} ${APP_DIR}/data
chown -R ${SERVICE_USER}:${SERVICE_USER} ${APP_DIR}/backend/.cache

# Install Python and dependencies
echo "Installing Python dependencies..."
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv

# Create virtual environment
echo "Creating Python virtual environment..."
cd ${APP_DIR}
python3 -m venv venv
chown -R ${SERVICE_USER}:${SERVICE_USER} venv

# Install requirements
echo "Installing Python packages..."
su - ${SERVICE_USER} -s /bin/bash -c "cd ${APP_DIR} && source venv/bin/activate && pip install --upgrade pip && pip install -r backend/requirements.txt"

# Create systemd service file
echo "Creating systemd service..."
cat > /etc/systemd/system/${APP_NAME}.service << EOF
[Unit]
Description=Performance Analyzer Web Application
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${APP_DIR}
Environment="PATH=${APP_DIR}/venv/bin"
Environment="PYTHONPATH=${APP_DIR}/backend"
ExecStart=${APP_DIR}/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port ${SERVICE_PORT}
Restart=always
RestartSec=10

# Security settings
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
echo "Enabling and starting service..."
systemctl daemon-reload
systemctl enable ${APP_NAME}
systemctl restart ${APP_NAME}

# Wait a moment for service to start
sleep 2

# Check service status
if systemctl is-active --quiet ${APP_NAME}; then
    echo ""
    echo "================================================"
    echo "✓ Installation Complete!"
    echo "================================================"
    echo ""
    echo "Service Status: Running"
    echo "Service Port: ${SERVICE_PORT}"
    echo "Service Logs: journalctl -u ${APP_NAME} -f"
    echo ""
    echo "Access the application:"
    echo "  http://localhost:${SERVICE_PORT}"
    echo ""
    echo "Configure Nginx reverse proxy (optional):"
    echo "  See nginx.conf.example"
    echo ""
    echo "Useful commands:"
    echo "  systemctl status ${APP_NAME}   # Check status"
    echo "  systemctl restart ${APP_NAME}  # Restart service"
    echo "  journalctl -u ${APP_NAME} -f   # View logs"
    echo ""
    echo "To deploy updates:"
    echo "  cd ${APP_DIR} && sudo git pull && sudo systemctl restart ${APP_NAME}"
    echo ""
else
    echo ""
    echo "⚠️  Service failed to start!"
    echo "Check logs: journalctl -u ${APP_NAME} -n 50"
    exit 1
fi
