#!/bin/bash
#
# Installation script for Validator Performance Analyzer Web Application
# Deploys the application as a systemd service
#
# Usage: sudo ./install.sh
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

echo "Configuration:"
echo "  App Directory: ${APP_DIR}"
echo "  Service User: ${SERVICE_USER}"
echo "  Service Port: ${SERVICE_PORT}"
echo ""

# Create service user if doesn't exist
if ! id "${SERVICE_USER}" &>/dev/null; then
    echo "Creating service user: ${SERVICE_USER}..."
    useradd --system --no-create-home --shell /bin/false ${SERVICE_USER}
else
    echo "✓ Service user already exists"
fi

# Create app directory
echo "Creating application directory: ${APP_DIR}..."
mkdir -p ${APP_DIR}
mkdir -p ${APP_DIR}/data
mkdir -p ${APP_DIR}/.cache

# Copy application files
echo "Copying application files..."
cp -r backend ${APP_DIR}/
cp -r frontend ${APP_DIR}/
cp -r .cache/* ${APP_DIR}/.cache/ 2>/dev/null || true  # Copy cache if exists

# Set ownership
echo "Setting file ownership..."
chown -R ${SERVICE_USER}:${SERVICE_USER} ${APP_DIR}

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
WorkingDirectory=${APP_DIR}/backend
Environment="PATH=${APP_DIR}/venv/bin"
ExecStart=${APP_DIR}/venv/bin/uvicorn main:app --host 0.0.0.0 --port ${SERVICE_PORT}
Restart=always
RestartSec=10

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${APP_DIR}/data ${APP_DIR}/.cache

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
    echo "  systemctl stop ${APP_NAME}     # Stop service"
    echo "  systemctl start ${APP_NAME}    # Start service"
    echo ""
else
    echo ""
    echo "⚠️  Service failed to start!"
    echo "Check logs: journalctl -u ${APP_NAME} -n 50"
    exit 1
fi
