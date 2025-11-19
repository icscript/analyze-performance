# Performance Analyzer - Web Application

Web-based interface for analyzing Polkadot and Kusama validator performance before and after configuration changes.

## Features

- **Simple Web Interface**: No CLI knowledge required
- **Network-normalized Scoring**: Exact Turboflakes dashboard match (default)
- **Shareable Results**: Each analysis gets a unique URL
- **Automatic Caching**: Subsequent analyses are instant
- **Auto-detect Mode**: Automatically calculate optimal session ranges
- **Detailed Breakdowns**: Optional session-by-session analysis

## Quick Start

### Local Testing

```bash
# Install dependencies
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the server
python main.py

# Access the application
# Open http://localhost:8000 in your browser
```

### Production Deployment

```bash
# On your server (requires root/sudo)
sudo ./install.sh

# The service will be available at http://your-server:8000
# Configure nginx for HTTPS (recommended)
```

## Architecture

```
┌─────────────────────────────────────┐
│  Frontend (HTML/Tailwind/Alpine.js) │
│  - Simple form interface            │
│  - Results visualization            │
│  - No build step required           │
└──────────────┬──────────────────────┘
               │ HTTP/REST API
┌──────────────▼──────────────────────┐
│  Backend (FastAPI)                  │
│  - ValidatorPerformanceAnalyzer     │
│  - Rate limiting                    │
│  - Analysis caching                 │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Storage                            │
│  - SQLite (analyses.db)             │
│  - File cache (.cache/)             │
└─────────────────────────────────────┘
```

## API Endpoints

### `POST /api/analyze`

Analyze validator performance.

**Request:**
```json
{
  "address": "validator_address",
  "change_session": 52300,
  "network": "kusama",
  "sessions_before": 10,
  "sessions_after": null,
  "exclude_latest": true,
  "network_normalized": true,
  "detailed": false,
  "comment": "Optional description"
}
```

**Response:**
```json
{
  "analysis_id": "abc123xyz",
  "validator": "...",
  "network": "kusama",
  "change_session": 52300,
  "before_stats": {...},
  "after_stats": {...},
  "improvement": 0.0234,
  "improvement_pct": 2.5,
  "direction": "improvement"
}
```

### `GET /api/analysis/{id}`

Retrieve a saved analysis by ID.

### `GET /api/health`

Health check and system stats.

## Deployment Details

### System Requirements

- **OS**: Ubuntu 20.04+ or Debian 11+
- **Python**: 3.9+
- **RAM**: 512MB minimum, 1GB recommended
- **Disk**: 10GB+ (for cache growth)
- **Network**: Outbound HTTPS to Turboflakes API

### Installation Process

The `install.sh` script:

1. Creates a dedicated service user
2. Installs Python dependencies in virtual environment
3. Sets up systemd service
4. Configures file permissions
5. Starts the service

### File Structure (Production)

```
/opt/performance-analyzer/
├── backend/
│   ├── main.py           # FastAPI app
│   ├── analyzer.py       # Core logic
│   ├── models.py         # Pydantic models
│   ├── database.py       # SQLite handler
│   └── requirements.txt
├── frontend/
│   └── index.html        # Web UI
├── data/
│   └── analyses.db       # SQLite database
├── .cache/               # Session cache
└── venv/                 # Python virtual environment
```

### Service Management

```bash
# Check status
systemctl status performance-analyzer

# View logs
journalctl -u performance-analyzer -f

# Restart
systemctl restart performance-analyzer

# Stop
systemctl stop performance-analyzer

# Start
systemctl start performance-analyzer
```

### Nginx Setup (HTTPS)

1. Install nginx and certbot:
   ```bash
   apt-get install nginx certbot python3-certbot-nginx
   ```

2. Copy nginx configuration:
   ```bash
   cp nginx.conf.example /etc/nginx/sites-available/performance-analyzer
   # Edit the file to set your domain
   nano /etc/nginx/sites-available/performance-analyzer
   ```

3. Enable the site:
   ```bash
   ln -s /etc/nginx/sites-available/performance-analyzer /etc/nginx/sites-enabled/
   nginx -t  # Test configuration
   systemctl reload nginx
   ```

4. Get SSL certificate:
   ```bash
   certbot --nginx -d your-domain.com -d www.your-domain.com
   ```

## Caching Strategy

### Session Cache

- **Location**: `.cache/` directory
- **Format**: `{network}_session_{session}.json`
- **Size**: ~150KB per session
- **Retention**: Indefinite (sessions are immutable)

**Benefits:**
- One user's query caches data for ALL validators in those sessions
- Subsequent analyses are instant (< 1 second)
- Shared across all users

**Management:**
```bash
# Check cache size
du -sh /opt/performance-analyzer/.cache

# Clean old cache (optional - only if disk space needed)
find /opt/performance-analyzer/.cache -name "*.json" -mtime +180 -delete
```

### Analysis Database

- **Location**: `data/analyses.db`
- **Purpose**: Store completed analyses for sharing
- **Deduplication**: Same validator+session within 1 hour returns cached result

**Maintenance:**
```bash
# Vacuum database (run monthly via cron)
sqlite3 /opt/performance-analyzer/data/analyses.db "VACUUM;"
```

## Pre-warming Cache (Optional)

For instant results, pre-warm the cache with recent sessions:

```bash
# Create a cron job to run nightly
# /etc/cron.daily/prewarm-cache

#!/bin/bash
cd /opt/performance-analyzer
source venv/bin/activate
python -c "
from backend.analyzer import ValidatorPerformanceAnalyzer
analyzer = ValidatorPerformanceAnalyzer(network='kusama', use_network_normalization=True)
current = analyzer.get_current_session('any_address')
# Fetch last 50 sessions
for session in range(current - 50, current):
    analyzer.fetch_network_session_data(session)
"
```

## Security Considerations

1. **Rate Limiting**: Implemented via `slowapi`
   - 10 requests/minute per IP for `/api/analyze`
   - 50 requests/minute per IP for `/api/analysis/{id}`

2. **Input Validation**: All inputs validated via Pydantic models

3. **No User Accounts**: Privacy-friendly, no PII collected

4. **HTTPS**: Strongly recommended via Nginx + Let's Encrypt

5. **Service Isolation**: Runs as dedicated user with restricted permissions

## Monitoring

### Health Check

```bash
curl http://localhost:8000/api/health
```

Returns:
- Service status
- Uptime
- Cache statistics
- Database statistics

### Logs

```bash
# Application logs
journalctl -u performance-analyzer -f

# Nginx access logs
tail -f /var/log/nginx/performance-analyzer-access.log

# Nginx error logs
tail -f /var/log/nginx/performance-analyzer-error.log
```

## Troubleshooting

### Service won't start

```bash
# Check logs
journalctl -u performance-analyzer -n 50

# Common issues:
# - Port 8000 already in use
# - Missing Python dependencies
# - Permission issues with cache/data directories
```

### Slow first analysis

This is normal! Network-normalized mode fetches data for all validators in each session:
- First run: 30-60 seconds (fetching from Turboflakes API)
- Subsequent runs: < 1 second (cached)

### Out of disk space

```bash
# Check cache size
du -sh /opt/performance-analyzer/.cache

# Remove old sessions (keeps last 500 sessions)
cd /opt/performance-analyzer/.cache
ls -t *.json | tail -n +500 | xargs rm
```

## Upgrading

```bash
# Stop service
systemctl stop performance-analyzer

# Backup database
cp /opt/performance-analyzer/data/analyses.db ~/analyses-backup.db

# Update code
cd /opt/performance-analyzer
# ... update files ...

# Reinstall dependencies
source venv/bin/activate
pip install -r backend/requirements.txt

# Restart service
systemctl start performance-analyzer
```

## Support

For issues related to:
- **Scoring accuracy**: See original CLI validation docs
- **API errors**: Check Turboflakes API status
- **Deployment**: Check system logs and permissions
- **Feature requests**: Contact repository maintainer

## Credits

- Built on top of the validated CLI analyzer
- Uses official Turboflakes ONE-T formula
- Network data from Turboflakes API
