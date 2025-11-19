# Deployment Notes

## Changes Made for Web Service Compatibility

### 1. Backend Error Handling (backend/analyzer.py)

**Problem**: The analyzer was originally designed as a CLI tool and used `sys.exit(1)` for error handling. When used as a library by the FastAPI web service, these calls would crash the entire service.

**Solution**: Replaced all `sys.exit(1)` calls with appropriate exception raises:
- `RuntimeError()` for API/network errors
- `ValueError()` for validation errors
- `FileNotFoundError()` for missing files

**Changed lines**:
- Line 160: `sys.exit(1)` → `raise RuntimeError(f"Error fetching current session: {e}")`
- Line 187: `sys.exit(1)` → `raise RuntimeError(f"Error fetching data: {e}")`
- Line 854: `sys.exit(1)` → `raise ValueError("Change session too recent...")`
- Line 908: `sys.exit(1)` → `raise ValueError("Validator not found...")`
- Line 954: `sys.exit(1)` → `raise ValueError("No session data available")`
- Line 1366-1368: `sys.exit(1)` → `raise FileNotFoundError(...)` and `raise RuntimeError(...)`

These exceptions are properly caught by FastAPI's error handling in `backend/main.py` and returned as HTTP error responses.

### 2. Systemd Service Configuration (performance-analyzer.service)

**Problem**: Original configuration had incorrect paths and overly restrictive security settings that prevented cache creation.

**Changes**:
- **WorkingDirectory**: Changed from `/opt/performance-analyzer/backend` to `/opt/performance-analyzer`
  - This allows the service to access both backend and data directories
- **PYTHONPATH**: Added `Environment="PYTHONPATH=/opt/performance-analyzer/backend"`
  - Enables Python to find the backend modules when running from parent directory
- **ExecStart**: Changed from `main:app` to `backend.main:app`
  - Matches the new working directory structure
- **Security Settings**: Simplified to only `NoNewPrivileges=true`
  - Removed `ProtectSystem=strict`, `ProtectHome=true`, `PrivateTmp=true`, and `ReadWritePaths`
  - These were preventing cache directory creation in `/opt/performance-analyzer/backend/.cache`
  - The service user is non-privileged and only has access to `/opt/performance-analyzer/` anyway

## Installation Process

The `install.sh` script handles the complete installation:

1. Creates a dedicated system user `performance-analyzer`
2. Copies files to `/opt/performance-analyzer/`
3. Creates required directories (`data/`, `.cache/`)
4. Sets up Python virtual environment
5. Installs dependencies
6. Creates and enables systemd service
7. Starts the service

## Directory Structure

```
/opt/performance-analyzer/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── analyzer.py          # Core analysis logic (CLI-compatible)
│   ├── models.py            # Pydantic models
│   ├── database.py          # SQLite handler
│   ├── requirements.txt
│   └── .cache/              # Session cache (created at runtime)
├── frontend/
│   └── index.html           # Web UI
├── data/
│   └── analyses.db          # SQLite database (created at runtime)
└── venv/                    # Python virtual environment
```

## Testing the Deployment

After installation, verify the service is working:

```bash
# Check service status
systemctl status performance-analyzer

# Check logs
journalctl -u performance-analyzer -f

# Test health endpoint
curl http://localhost:8000/api/health

# Test analysis endpoint (use a recent session number)
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "address": "JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ",
    "change_session": 52350,
    "network": "kusama",
    "sessions_before": 5,
    "sessions_after": 5,
    "network_normalized": true
  }'
```

## Common Issues and Solutions

### Service fails to start

**Check logs**: `journalctl -u performance-analyzer -n 50`

Common causes:
- Port 8000 already in use: `lsof -i :8000`
- Missing Python dependencies: Check venv installation
- Permission issues: Verify ownership of `/opt/performance-analyzer/`

### "Validator not found" errors

This is expected behavior when:
- The validator wasn't active in the requested sessions
- Session numbers are too old and data is no longer available
- Wrong network specified (kusama vs polkadot)

Use the Turboflakes API to find a recent session:
```bash
curl "https://kusama-onet-api.turboflakes.io/api/v1/validators/YOUR_ADDRESS/grade?number_last_sessions=1"
```

### Cache permission errors

If you see "Read-only file system" errors:
- Ensure the systemd service file has the simplified security settings
- Verify directory ownership: `ls -la /opt/performance-analyzer/`

## Production Recommendations

1. **Use Nginx reverse proxy** for HTTPS (see `nginx.conf.example`)
2. **Set up firewall**: Only expose Nginx port, not 8000 directly
3. **Monitor cache size**: Session cache grows ~150KB per session
4. **Database maintenance**: Run `VACUUM` monthly via cron
5. **Log rotation**: Configure journald or syslog rotation

## Compatibility

This deployment maintains full CLI compatibility:
- The `compare-performance.py` script still works as before
- The `backend/analyzer.py` can be used as both CLI and library
- All original features are preserved
