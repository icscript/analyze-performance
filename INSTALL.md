# Installation Guide

## Fresh Server Deployment

```bash
# 1. Clone directly to /opt/performance-analyzer
sudo git clone https://github.com/icscript/analyze-performance.git /opt/performance-analyzer
cd /opt/performance-analyzer

# 2. Checkout your branch (if not using main)
sudo git checkout claude/public-web-tool-adaptation-01TuCS13139JDkGFgY5bzHCZ

# 3. Run install script
sudo ./install.sh

# 4. Verify
curl http://localhost:8000/api/health
```

## Deploying Updates

```bash
cd /opt/performance-analyzer
sudo git pull
sudo systemctl restart performance-analyzer
```

Or use the deploy script:
```bash
sudo /opt/performance-analyzer/deploy.sh
```

## Service Management

```bash
systemctl status performance-analyzer   # Check status
systemctl restart performance-analyzer  # Restart
journalctl -u performance-analyzer -f   # View logs
```

## Requirements

- Ubuntu 20.04+ or Debian 11+
- Python 3.9+
- Root/sudo access

## Ports

- **8000** - Application (configure firewall/nginx as needed)
