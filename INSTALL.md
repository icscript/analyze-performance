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

Or create a convenience script in your home directory:
```bash
#!/bin/bash
cd /opt/performance-analyzer
git pull
systemctl restart performance-analyzer
```

## Nginx Setup (Port 80)

After installation, set up nginx to serve on port 80:

```bash
# Install nginx
apt-get install -y nginx

# Create config (uses Option 1 from nginx.conf.example)
cat > /etc/nginx/sites-available/performance-analyzer << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 180s;
        proxy_send_timeout 180s;
        proxy_read_timeout 180s;
    }

    access_log /var/log/nginx/performance-analyzer-access.log;
    error_log /var/log/nginx/performance-analyzer-error.log;
}
EOF

# Enable site
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/performance-analyzer /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

For HTTPS setup, see `nginx.conf.example` Option 2.

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

- **80** - Nginx (public access)
- **8000** - Application (internal, proxied by nginx)

## Notes

- The repo should be cloned directly to `/opt/performance-analyzer`
- Do not clone elsewhere and copy files - use git pull for updates
- The service user `performance-analyzer` runs the app with read-only access to code
