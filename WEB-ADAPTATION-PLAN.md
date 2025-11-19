# Web Adaptation Plan

## Overview

Adapt the existing `ValidatorPerformanceAnalyzer` Python tool into a simple web-based service for the Polkadot/Kusama validator community.

---

## 🔴 Critical Insights from Original Developer

**After reviewing this plan with context from the actual CLI implementation, these are the key modifications:**

1. **Network-normalized mode MUST be default** - It's not just a nice-to-have:

   - ✅ Unlimited sessions (no 192 limit)
   - ✅ Exact Turboflakes dashboard match
   - ✅ Superior caching (one user's query benefits all)
   - ✅ Includes network rankings

2. **Aggregated scoring is sacred** - Do NOT modify the scoring logic:

   - CLI tool took weeks to perfect and matches dashboard exactly
   - Must aggregate THEN score (not score THEN average)
   - Inactive para sessions MUST be included

3. **Caching is perfect as-is** for multi-user web:

   - Sessions are immutable (no TTL needed)
   - Keyed by session, not validator (cross-validator reuse)
   - Pre-warm cache nightly for instant results

4. **Include auto-detect in MVP** (`--last-change` logic):

   - Already implemented and critical for UX
   - Users should not have to calculate session ranges manually

5. **Peer comparison = Phase 2** (too complex for MVP)

6. **Keep it synchronous** - No need for async complexity
   - FastAPI handles sync functions fine (thread pool)
   - CLI uses `requests` (blocking) not async

**Read the "Original Developer Feedback" section below for full details.**

---

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

### Dependencies

**Current CLI (minimal):**

```
requests>=2.28.0
```

**Web version additions:**

```
# Backend
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6  # for form data
pydantic>=2.0.0  # for request/response models

# Optional but recommended
slowapi>=0.1.9  # for rate limiting
aiosqlite>=0.19.0  # async SQLite (if going async route)
```

**Note:** The CLI tool uses only standard library + requests. It does NOT currently use `ss58` library - address validation would need to be added for web version (or validate via regex for basic format checking).

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

### Phase 1: MVP (Essential for Launch)

- [ ] Web form with core options:
  - Network selector (Polkadot/Kusama)
  - Validator address input with format validation
  - Change session input
  - **Auto-detect mode** (last-change logic) - critical UX feature
  - Manual mode (sessions before/after)
  - Network-normalized checkbox (default: enabled)
  - Optional comment field
- [ ] Results display with:
  - **Aggregated scores** (before/after comparison)
  - Grade changes with visual indicators (↑/↓/→)
  - Para participation rate and changes
  - Session breakdown table (detailed view)
  - Session type indicators ([PARA]/[PARA-INACTIVE]/[AUTH])
  - Network rankings (if network-normalized)
- [ ] **Shareable URLs** with short slugs (critical for community use)
- [ ] Server-side caching (reuse existing mechanism)
- [ ] Basic rate limiting (cache-aware: lenient for cached, strict for fresh)
- [ ] Simple deployment script (one command installation)
- [ ] Loading states with progress indication ("Fetching session 52300...")
- [ ] Error handling with user-friendly messages

### Phase 2: Polish (High Value)

- [ ] Responsive mobile design (many validators check on phones)
- [ ] Visual charts:
  - Session score timeline graph
  - Para vs auth-only session distribution
  - Ranking percentile visualization
- [ ] Peer comparison UI:
  - Multi-validator form or peer list upload
  - Comparison matrix/table
  - Relative performance ranking
- [ ] Recent analyses history (last 10 for this validator)
- [ ] Export results (JSON/CSV)

### Phase 3: Community Features (Nice to Have)

- [ ] Public analysis history dashboard
- [ ] Popular validators leaderboard (most analyzed)
- [ ] Validator identity resolution (on-chain names via Subscan)
- [ ] Email notifications (subscribe to validator updates)
- [ ] API documentation for programmatic access
- [ ] Embed code (iframe for validator dashboards)

## Security & Abuse Prevention

1. **Rate Limiting**: 10 requests/minute per IP, 100/hour
2. **Input Validation**: SS58 address format, session bounds
3. **Cache Deduplication**: Same analysis request within 1 hour returns cached result
4. **No Sensitive Data**: Validator addresses are public blockchain data
5. **Logging**: Track requests for monitoring, no PII

## Changes to Existing Code

**Minimal modifications approach**:

### Option A: Non-invasive wrapper (Recommended)

1. **NO changes** to `compare-performance.py`
2. FastAPI imports the class directly: `from compare_performance import ValidatorPerformanceAnalyzer`
3. Backend wrapper calls methods and captures/parses console output
4. Add new methods that return dicts (e.g., `get_results_dict()`) without modifying existing print methods

### Option B: Refactor for dual use

1. Add `return_data=False` parameter to key methods
2. When `return_data=True`, return dict instead of printing
3. Keeps CLI working exactly as-is
4. Web backend calls with `return_data=True`

**Recommendation:** Start with Option A (zero code changes), migrate to Option B if output parsing becomes problematic.

**No async needed:** The analyzer uses synchronous `requests` library. FastAPI can handle sync functions fine - it runs them in a thread pool automatically. Don't add unnecessary async complexity.

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

## Original Developer Feedback & Implementation Notes

### 1. **Code Structure** ✅

The `ValidatorPerformanceAnalyzer` class is already well-structured and self-contained (1800+ lines, single class). Key adaptations needed:

**Current state:**

- All logic in `compare-performance.py` with a single class
- Prints results directly to console via `print_results()`, `print_peer_comparison()`, etc.
- Main function handles argparse and orchestrates the flow

**Web adaptation strategy:**

- **DO**: Import the class as-is, add wrapper methods that return dicts instead of printing
- **DON'T**: Rewrite the core logic - it's battle-tested and matches Turboflakes exactly
- Consider: Add `to_dict()` methods to return structured results without modifying existing print methods
- FastAPI can remain synchronous (easier) - the analyzer uses `requests` (blocking I/O) not async

### 2. **Caching Strategy** ✅ Already Optimized

The existing cache is **extremely effective** for public web use:

**Current implementation:**

- Network-normalized mode caches entire session data for all validators (`.cache/kusama/session-52300.json`)
- Cache is keyed by session number, not validator address
- **One user's query populates cache for ALL validators in that session**
- Subsequent queries for ANY validator in cached sessions = instant response
- No TTL needed - session data is immutable once finalized

**Recommendation for web:**

- **DO**: Use existing cache as-is - it's perfect for multi-user scenarios
- **DO**: Pre-warm cache for recent sessions (cron job running queries nightly)
- **DON'T**: Add TTL - old session data never changes
- **Consider**: Size limit based on disk space (e.g., keep last 500 sessions per network = ~500MB)

### 3. **Error Handling** ✅ Robust

Current error handling is already production-ready:

**What's implemented:**

- HTTP error catching with informative messages (404, 400, etc.)
- API limitation detection (192-session limit in non-normalized mode)
- Missing validator warnings (validator not found in requested sessions)
- Network data completeness checks
- Auth-only session detection and exclusion from para statistics

**Web UI additions needed:**

- Return error codes in JSON response (e.g., `{"error": "validator_not_found", "message": "..."}`)
- Distinguish between user errors (bad address) vs API errors (timeout)
- Consider retry logic for transient API failures (already has basic retry for rate limits)

### 4. **Peer Comparison** - Save for Phase 2

**Current implementation:**

- Reads `peers.ini` file with format: `NAME = ADDRESS`
- Supports peer name resolution (e.g., `IC01KSM` → full address)
- Filters peers by network automatically
- Ranks target validator among peers for before/after periods
- Output shows relative performance vs peer average

**Web adaptation complexity:**

- Requires user to upload/paste peer list or build multi-validator form
- Significantly more complex UI (table of peers, comparison matrix)
- Backend already handles it well, but UX is challenging

**Recommendation:** Phase 2. Start with single-validator analysis, add peer comparison when there's demand.

### 5. **Network Normalization** ⚠️ Critical Decision

**This is the PRIMARY mode and should be the default for web users.**

**Why network-normalized mode is superior:**

- ✅ **Unlimited sessions** - bypasses 192-session API limit
- ✅ **Exact dashboard match** - uses same scoring methodology as Turboflakes
- ✅ **Better caching** - query-by-session enables cross-validator cache reuse
- ✅ **Rankings included** - shows validator's rank among all paravalidators
- ✅ **More accurate** - network-wide normalization vs self-normalization

**Trade-off:**

- First query for new sessions: slower (parallel fetching of session data)
- Subsequent queries: **instant** (cached)

**Recommendation:**

- Default: `network-normalized=true` (checkbox checked by default)
- UI note: "First analysis may take 30-60 seconds, subsequent queries instant"
- Consider: Hide the non-normalized option entirely for simplicity

### 6. **Session Auto-detection** (`--last-change`) - Include in MVP

**Current implementation:**

- `--last-change SESSION_NUM` auto-calculates `-b` (sessions before)
- Automatically excludes the change session itself
- Respects API limits (caps at 192 in non-normalized, unlimited in normalized)

**Web UI design:**

```
○ Manual mode:
  Sessions before: [____] Sessions after: [____]

● Auto-detect mode:
  Last change at session: [____]
  Current analysis session: [____] (auto-detected)
  [Calculate optimal range]
```

**Recommendation:** Include in MVP - it's already implemented and makes the tool more user-friendly.

### 7. **Additional Implementation Insights**

#### SS58 Address Handling ⚠️

**Current state:**

- CLI tool accepts validator addresses as-is (no validation)
- Assumes user provides valid SS58 address
- Turboflakes API handles different address formats gracefully

**Web version needs:**

- Client-side validation (regex for SS58 format: starts with letter, 47-48 chars)
- Better error messages if API rejects invalid address
- Consider: Link to Polkadot.js.org for address format conversion
- **DO NOT** attempt on-chain address conversion (adds complexity, not needed)

#### Aggregated Scoring ✅ **CRITICAL - DO NOT MODIFY**

The CLI tool implements Turboflakes' exact scoring methodology after extensive testing:

**Aggregated scoring (primary score):**

1. Sum all para stats across sessions: `total_votes`, `total_missed_votes`, `total_bitfields`, etc.
2. Calculate single MVR/BAR/PTS from the totals
3. Apply ONE-T formula once to aggregated stats
4. This matches Turboflakes dashboard exactly

**Per-session scoring (for detailed view):**

1. Calculate score for each individual session
2. Used for session-by-session table and analysis
3. Average of per-session scores ≠ aggregated score (this is expected)

**Implementation location in CLI:**

- `calculate_aggregated_score()` method - returns the primary score
- `analyze_sessions()` method - calculates per-session scores
- Both are used in output, but aggregated is the headline number

**DO NOT:**

- Average per-session scores and call it the "overall score"
- Normalize before aggregating (normalize the aggregated points)
- Exclude inactive para sessions from the data (they must be included)

This logic took weeks to perfect. Preserve it exactly.

#### Session Type Detection ✅

- `[PARA]` - Active paravalidator session with work
- `[PARA-INACTIVE]` - Selected as para but no work assigned (0 backing points)
- `[AUTH]` - Auth-only session (not selected as paravalidator)
- Web UI should use visual indicators (badges/colors) for these

#### Debug Mode

- `-d` flag shows all API queries
- Web version should have admin/debug endpoint (not public-facing)

#### API Specifics

- Kusama: ~700 paravalidators per session, ~998 total authorities
- Polkadot: ~600 paravalidators per session, ~600 total authorities
- Turboflakes API is stable and well-maintained (recent data completeness fix confirmed)

### 8. **Missing from Original Plan**

#### Result Sharing Improvements

- Generate short URL slugs (not full analysis IDs)
- Include metadata in share: network, validator name (if known), date analyzed
- Consider: Comparison links (compare two analysis results side-by-side)

#### Validator Name Resolution

- Many validators have on-chain identities
- Consider: Query identity from chain or use external service (Subscan API)
- Display: "IC02KSM (Identity: Unknown)" vs "IC02KSM (Identity: InfraCap)"

#### Performance Indicators

- Visual indicators for grade changes (↑ improved, ↓ degraded, → unchanged)
- Color-coding for grades (green A+/A/A-, yellow B+/B/B-, orange C+/C)
- Session distribution chart (para vs auth-only ratio)

#### Mobile Responsiveness

- Consider mobile users checking validator performance on the go
- Tables should be scrollable/collapsible on small screens
- Form should be thumb-friendly

#### Rate Limiting Refinement

- Consider: Separate limits for cached vs non-cached queries
- Cached queries are free (instant), non-cached are expensive (API calls)
- Maybe: 50 cached/min, 5 non-cached/min per IP

## Timeline

**Estimated Development**: 2-3 days for MVP

- Day 1: Backend API + database
- Day 2: Frontend UI + integration
- Day 3: Testing + deployment scripts + documentation

## Success Criteria & Validation

### Functional Requirements

- ✅ Web UI supports all core CLI options:
  - Network selection (Kusama/Polkadot)
  - Change session specification
  - Sessions before/after (manual + auto-detect via last-change)
  - Network-normalized mode (default enabled)
  - Optional comment field
- ✅ **Score accuracy**: Web results match CLI output exactly (±0.0001 score difference)
- ✅ **Performance**: Cached queries return in < 1 second
- ✅ **Sharing**: Shareable URLs work, results persist in database
- ✅ **Concurrent users**: Handle 10+ simultaneous queries without degradation
- ✅ **Cache sharing**: One user's query benefits all subsequent users for those sessions

### Validation Test Cases

1. **Exact match test**: Run same analysis via CLI and web, compare JSON output
2. **Cache effectiveness**:
   - Query validator A, sessions 52000-52050 (fresh cache)
   - Query validator B, sessions 52025-52075 (50% cached) - should be 2x faster
   - Query validator C, sessions 52000-52050 (100% cached) - should be instant
3. **Edge cases**:
   - Validator with many auth-only sessions
   - Validator not found in requested range (should error gracefully)
   - Very old sessions (may not exist in API)
   - Change session = current session (should auto-adjust)
4. **Cross-network validation**:
   - Kusama validator with 70% para participation
   - Polkadot validator with 95% para participation
   - Verify para/auth session counting is correct
5. **Score methodology**:
   - Compare aggregated score with Turboflakes dashboard (manual spot check)
   - Verify per-session scores match when queried individually
   - Confirm inactive para sessions are handled correctly (0 backing points)

### Deployment Validation

- ✅ Install script completes in < 15 minutes on fresh Ubuntu/Debian server
- ✅ Service starts automatically on boot
- ✅ Nginx reverse proxy works with SSL (Let's Encrypt)
- ✅ Log rotation configured
- ✅ Cache directory has correct permissions

### Monitoring & Health

- ✅ `/api/health` endpoint returns cache stats, uptime, API connectivity
- ✅ Request logging includes: IP, endpoint, execution time, cache hit/miss
- ✅ Error logging captures full stack traces for debugging

---

## Potential Pitfalls & Lessons Learned

Based on extensive CLI development and testing, watch out for these issues:

### 1. **Session Range Calculations** ⚠️

Off-by-one errors are common when calculating session ranges:

- `sessions_before=30` should include exactly 30 sessions BEFORE the change session
- The change session itself should be excluded (config changes may have happened mid-session)
- Range calculation: `[change_session - sessions_before, change_session - 1]` for "before"
- Always validate: actual count should match requested count

### 2. **Inactive Para Sessions** ⚠️

These are legitimate and common:

- Validator selected as paravalidator (`is_para: true`)
- No parachains in their assigned group had work
- Result: `backing_points = 0`, `para_summary` may be minimal
- **Don't treat as errors** - include in aggregated stats (impacts score)
- Label clearly in UI as `[PARA-INACTIVE]` vs `[PARA]`

### 3. **Cache Consistency** ⚠️

- Session data is immutable once finalized, BUT:
- The "current session" is still in progress - don't cache it
- Consider: Only cache sessions that are at least 2-3 sessions old
- Example: Current session = 52380, only cache ≤ 52377
- The `exclude_latest` flag helps with this

### 4. **API Rate Limiting** ⚠️

Turboflakes API is generous but not unlimited:

- Network-normalized queries hit API hard for first run (parallel requests)
- Consider: Max 10 concurrent API requests (use semaphore/queue)
- Current CLI uses ThreadPoolExecutor with default workers
- Web version should limit concurrent analyses per user

### 5. **Address Format Confusion** ⚠️

SS58 addresses can be confusing:

- Same validator has different addresses on different networks
- Generic format 42 works everywhere (what Turboflakes uses internally)
- Web UI should accept any format, convert internally
- Display the user's input format, not the converted one

### 6. **Score Discrepancies** ⚠️

If web scores don't match Turboflakes dashboard:

- **MUST use aggregated scoring** (not per-session average)
- **MUST use network-normalized mode**
- **MUST exclude auth-only sessions from para statistics**
- **MUST handle inactive para sessions correctly** (include in aggregation)
- The CLI tool now matches dashboard scores exactly - preserve this logic

### 7. **Very Old Sessions** ⚠️

Turboflakes doesn't retain all historical data:

- Sessions older than ~6 months may return 404
- Handle gracefully: "Data not available for sessions before X"
- Consider: Pre-check current session and limit lookback

### 8. **Network-Specific Differences** ⚠️

Kusama and Polkadot behave differently:

- Kusama: 700 paras, 998 total auths, more auth-only sessions
- Polkadot: 600 paras, 600 total auths, fewer auth-only sessions
- Para participation rate varies significantly by network
- Don't assume 70% is "good" universally - it's network-dependent

### 9. **Parallel API Calls** ⚠️

ThreadPoolExecutor is great for performance but:

- Error handling gets complex (one thread fails, others continue)
- Progress indication is harder
- Resource usage spikes
- Consider: Show "Fetching session X/Y..." progress in web UI
- The CLI tool uses concurrent.futures well - study that pattern

### 10. **Database Considerations** 💾

For SQLite in production:

- Use WAL mode: `PRAGMA journal_mode=WAL`
- Read-heavy workload is perfect for SQLite
- Writes (new analyses) are infrequent
- No need for connection pooling
- Consider: Periodic VACUUM to prevent bloat

---

## Final Recommendations

### Definitely Include

1. ✅ Network-normalized mode as default
2. ✅ Session auto-detection (`--last-change` logic)
3. ✅ Exclude latest session by default (it's incomplete)
4. ✅ Clear visual distinction for [PARA] / [PARA-INACTIVE] / [AUTH]
5. ✅ Shareable URLs with short slugs
6. ✅ Cache hit/miss indication in response metadata

### Consider for Phase 2

1. Peer comparison UI
2. Historical analysis (saved analyses over time)
3. Validator identity resolution (on-chain names)
4. Session score graphs/charts
5. Email notifications for performance degradation
6. Export to CSV/JSON

### Skip Entirely

1. User accounts (unnecessary complexity)
2. Payment/premium features (keep it free)
3. Custom alerting (outside scope)
4. Multi-network comparison (different networks aren't comparable)

---

## Contact & Support

For questions about the original CLI implementation or scoring methodology:

- CLI tool: `/Users/chris/cursor/projects/orc/turboflakes/compare-performance.py`
- Documentation: All `*.md` files in `turboflakes/` directory
- API reference: `TURBOFLAKES-API-NOTES.md` (comprehensive API documentation)
- Validation: `VALIDATION-GUIDE.md` (how to verify score accuracy)

The CLI tool has been extensively tested and validated. Trust its implementation, don't reinvent it.
