# Web Adaptation Plan

## Overview
Adapt the existing `ValidatorPerformanceAnalyzer` Python tool into a simple web-based service for the Polkadot/Kusama validator community.

## Design Philosophy
- **Simple & lightweight**: Low traffic expected, no complex infrastructure
- **No Docker**: Direct systemd service deployment on single server
- **No branding**: Just "Performance Analyzer"
- **Privacy-friendly**: No user accounts needed
- **Preserve core logic**: Wrap existing analyzer, don't rewrite

## Architecture

```
Frontend (HTML + Tailwind + Alpine.js)
    ↓ HTTP/REST
Backend (FastAPI + existing analyzer.py)
    ↓
Storage (SQLite + file cache)
```

### Backend: FastAPI
- **Framework**: FastAPI (modern, simple, auto-docs)
- **Core Logic**: Reuse existing `ValidatorPerformanceAnalyzer` class with minimal modifications
- **Endpoints**:
  - `POST /api/analyze` - Run new analysis
  - `GET /api/analysis/{id}` - Retrieve saved analysis
  - `GET /api/health` - Health check
- **Rate Limiting**: Simple in-memory rate limiter (10/min per IP)
- **Input Validation**: Validate addresses, session numbers, ranges

### Frontend: Single Page App
- **Tech**: Plain HTML with Tailwind CSS (CDN) and Alpine.js (CDN)
- **Zero build step**: No npm, webpack, or complex tooling
- **Form Fields**:
  - Network selector (Polkadot/Kusama radio buttons)
  - Validator address input
  - Change session number
  - Sessions before/after (with auto-detect option)
  - Checkboxes: network-normalized, detailed, exclude-latest
  - Optional comment field
- **Results Display**:
  - Summary card (before/after scores, improvement %, grades)
  - Session-by-session table (if detailed)
  - Component breakdown (MVR, BAR, PTS, PV)
  - Network ranking (if network-normalized)
  - Shareable URL for this analysis

### Storage
- **Analysis History**: SQLite database (`data/analyses.db`)
  - Table: `analyses(id, timestamp, network, address, params, results_json)`
  - Enables shareable links and history
- **Session Cache**: Existing `.cache/` directory structure
  - No changes needed to caching mechanism
  - Shared across all users (major performance benefit)

### Deployment
- **No Docker**: Direct installation on server
- **Process Manager**: systemd service
- **Reverse Proxy**: Nginx (optional but recommended for SSL)
- **Installation**: Single `install.sh` script that:
  - Creates Python virtual environment
  - Installs dependencies
  - Creates systemd service
  - Sets up directories and permissions
  - Optionally configures nginx

## Project Structure

```
performance-analyzer-web/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── analyzer.py          # Adapted ValidatorPerformanceAnalyzer
│   ├── models.py            # Pydantic models for API
│   ├── database.py          # SQLite operations
│   └── requirements.txt     # Python dependencies
├── frontend/
│   └── index.html           # Single-page app (HTML/Tailwind/Alpine)
├── .cache/                  # Session cache (git-ignored, auto-created)
├── data/
│   └── analyses.db          # SQLite database (git-ignored, auto-created)
├── install.sh               # Deployment script
├── performance-analyzer.service  # systemd service file
├── nginx.conf.example       # Example nginx configuration
└── README-WEB.md           # Deployment and usage documentation
```

## Key Features

### Phase 1: MVP
- [x] Web form with all current CLI options
- [x] Results display with shareable URLs
- [x] Server-side caching (existing mechanism)
- [x] Basic rate limiting
- [x] Simple deployment script

### Phase 2: Polish (Future)
- [ ] Visual charts (session score graph)
- [ ] Responsive mobile design
- [ ] Better error messages and loading states
- [ ] Peer comparison UI (leverage existing `--peers` logic)

### Phase 3: Community Features (Future)
- [ ] Analysis history page
- [ ] Popular validators dashboard
- [ ] API documentation for programmatic access

## Security & Abuse Prevention

1. **Rate Limiting**: 10 requests/minute per IP, 100/hour
2. **Input Validation**: SS58 address format, session bounds
3. **Cache Deduplication**: Same analysis request within 1 hour returns cached result
4. **No Sensitive Data**: Validator addresses are public blockchain data
5. **Logging**: Track requests for monitoring, no PII

## Changes to Existing Code

**Minimal modifications needed**:
1. Extract `ValidatorPerformanceAnalyzer` to importable module
2. Add async-compatible methods (FastAPI uses async)
3. Return structured data (dicts) instead of printing to console
4. Keep all existing logic intact (SS58 conversion, scoring, caching, etc.)

## Deployment Process

**On development machine (this repo)**:
1. Build web version
2. Test locally (`uvicorn main:app --reload`)
3. Package: `tar -czf performance-analyzer-web.tar.gz backend/ frontend/ install.sh ...`

**On production server**:
1. Upload tarball
2. Extract and run `./install.sh`
3. Configure nginx for HTTPS (optional)
4. Start service: `systemctl start performance-analyzer`

## Questions for Original Developer

1. **Code Structure**: Any concerns about extracting `ValidatorPerformanceAnalyzer` into a separate module for import by FastAPI?

2. **Caching Strategy**: The existing file-based cache works great. Should we add any TTL or size limits for public use?

3. **Error Handling**: Current code handles API errors gracefully. Any edge cases we should expose differently in web UI vs CLI?

4. **Peer Comparison**: The `--peers` feature exists. Should this be in v1 web UI or save for later?

5. **Network Normalization**: Default behavior for web users - should we enable `--network-normalized` by default (slower first run but exact dashboard match)?

6. **Session Auto-detection**: The `--last-change` logic - should we expose this in web UI or keep it simple with manual before/after counts?

7. **Additional Features**: Anything missing from this plan that would be valuable for the validator community?

## Timeline

**Estimated Development**: 2-3 days for MVP
- Day 1: Backend API + database
- Day 2: Frontend UI + integration
- Day 3: Testing + deployment scripts + documentation

## Success Criteria

- ✅ Web UI replicates all CLI functionality
- ✅ Results match CLI output exactly
- ✅ Shareable result URLs work
- ✅ Can deploy to server in < 15 minutes
- ✅ Handles concurrent users without issues
- ✅ Existing cache mechanism provides performance benefits to all users
