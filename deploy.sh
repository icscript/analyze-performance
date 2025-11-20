#!/bin/bash
#
# Deploy script for Performance Analyzer
# Usage: sudo ./deploy.sh
#

set -e

APP_DIR="/opt/performance-analyzer"
SERVICE_NAME="performance-analyzer"

echo "Deploying Performance Analyzer..."

# Pull latest changes
cd "$APP_DIR"
echo "Pulling latest changes..."
git pull

# Fix permissions (service user needs read access)
echo "Setting permissions..."
chown -R root:performance-analyzer "$APP_DIR"
chmod -R g+r "$APP_DIR"
chmod g+x "$APP_DIR" "$APP_DIR/backend" "$APP_DIR/frontend"

# Ensure data directories are writable by service user
chown -R performance-analyzer:performance-analyzer "$APP_DIR/data" 2>/dev/null || mkdir -p "$APP_DIR/data" && chown performance-analyzer:performance-analyzer "$APP_DIR/data"
chown -R performance-analyzer:performance-analyzer "$APP_DIR/backend/.cache" 2>/dev/null || true

# Restart service
echo "Restarting service..."
systemctl restart "$SERVICE_NAME"

# Verify
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✓ Deployment successful! Service is running."
else
    echo "✗ Service failed to start. Check: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi
