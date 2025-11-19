"""
FastAPI application for Validator Performance Analyzer
Web interface for analyzing Polkadot/Kusama validator performance

Follows original developer's guidance:
- Keep it synchronous (FastAPI handles sync functions in thread pool)
- Network-normalized mode as default
- Preserve all scoring logic from CLI tool
"""
import io
import sys
import time
from contextlib import redirect_stderr
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from analyzer import ValidatorPerformanceAnalyzer
from database import AnalysisDatabase
from models import AnalyzeRequest, AnalyzeResponse, ErrorResponse, HealthResponse, PeriodStats, SessionInfo

# Initialize FastAPI app
app = FastAPI(
    title="Validator Performance Analyzer",
    description="Analyze Polkadot and Kusama validator performance before/after configuration changes",
    version="1.0.0"
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware (if needed for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
db = AnalysisDatabase()

# Track startup time for uptime
startup_time = time.time()


def calculate_sessions_before(last_change_session: int, change_session: int) -> int:
    """Calculate sessions_before from last_change_session

    Implements the --last-change logic from CLI

    Args:
        last_change_session: Previous change session
        change_session: Current change session

    Returns:
        Number of sessions between changes
    """
    if last_change_session >= change_session:
        raise ValueError(f"last_change_session ({last_change_session}) must be before change_session ({change_session})")

    # Calculate: from (last_change + 1) to (change_session - 1)
    sessions_before = change_session - last_change_session - 1

    if sessions_before < 1:
        raise ValueError(f"Only {sessions_before} session(s) between changes (need at least 1)")

    return sessions_before


@app.post("/api/analyze", response_model=AnalyzeResponse)
@limiter.limit("10/minute")
def analyze_performance(request: Request, params: AnalyzeRequest):
    """Analyze validator performance before and after a configuration change

    Args:
        request: FastAPI request (for rate limiting)
        params: Analysis parameters

    Returns:
        Analysis results with scores, grades, and comparisons
    """
    try:
        # Calculate sessions_before from last_change_session if provided
        sessions_before = params.sessions_before
        if params.last_change_session is not None:
            sessions_before = calculate_sessions_before(params.last_change_session, params.change_session)

        # Check for recent analysis with same parameters (cache deduplication)
        existing_id = db.find_recent_analysis(
            address=params.address,
            change_session=params.change_session,
            network=params.network,
            max_age_hours=1  # Return cached result if < 1 hour old
        )

        if existing_id:
            # Return existing analysis
            cached = db.get_analysis(existing_id)
            if cached:
                result = cached['results']
                result['analysis_id'] = existing_id
                result['cached'] = True
                return result

        # Initialize analyzer (synchronous as recommended)
        analyzer = ValidatorPerformanceAnalyzer(
            network=params.network,
            use_network_normalization=params.network_normalized
        )

        # Capture stderr output (API queries, progress messages)
        stderr_capture = io.StringIO()

        with redirect_stderr(stderr_capture):
            # Run analysis (blocking call - FastAPI runs in thread pool)
            results = analyzer.analyze_sessions(
                address=params.address,
                change_session=params.change_session,
                sessions_before=sessions_before,
                sessions_after=params.sessions_after,
                exclude_current=params.exclude_latest
            )

        # Add comment if provided
        if params.comment:
            results['comment'] = params.comment

        # Calculate improvement metrics
        improvement = results.get('improvement')
        improvement_pct = None
        direction = None

        if improvement is not None:
            before_score = results['before_stats'].get('aggregated_score', 0)
            if before_score > 0:
                improvement_pct = (improvement / before_score) * 100

            if improvement > 0.01:
                direction = "improvement"
            elif improvement < -0.01:
                direction = "decline"
            else:
                direction = "no_change"

        # Save to database
        analysis_id = db.save_analysis(
            params=params.model_dump(),
            results=results
        )

        # Convert to response model
        response = AnalyzeResponse(
            validator=results['validator'],
            network=results['network'],
            change_session=results['change_session'],
            current_session=results['current_session'],
            excluded_current=results['excluded_current'],
            comment=results.get('comment'),
            before_sessions=[SessionInfo(**s) for s in results['before_sessions']],
            after_sessions=[SessionInfo(**s) for s in results['after_sessions']],
            before_stats=PeriodStats(**results['before_stats']),
            after_stats=PeriodStats(**results['after_stats']),
            improvement=improvement,
            improvement_pct=improvement_pct,
            direction=direction,
            overall_grade=results['overall_grade'],
            overall_auth_inclusion=results['overall_auth_inclusion'],
            overall_para_inclusion=results['overall_para_inclusion'],
            analysis_id=analysis_id,
        )

        return response

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log error for debugging
        print(f"Analysis error: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/analysis/{analysis_id}", response_model=AnalyzeResponse)
@limiter.limit("50/minute")  # More lenient for cached lookups
def get_analysis(request: Request, analysis_id: str):
    """Retrieve a previously run analysis by ID

    Args:
        request: FastAPI request (for rate limiting)
        analysis_id: Short analysis ID from URL

    Returns:
        Analysis results
    """
    analysis = db.get_analysis(analysis_id)

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Reconstruct response from stored results
    results = analysis['results']

    # Calculate improvement metrics if not stored
    improvement = results.get('improvement')
    improvement_pct = None
    direction = None

    if improvement is not None:
        before_score = results['before_stats'].get('aggregated_score', 0)
        if before_score > 0:
            improvement_pct = (improvement / before_score) * 100

        if improvement > 0.01:
            direction = "improvement"
        elif improvement < -0.01:
            direction = "decline"
        else:
            direction = "no_change"

    response = AnalyzeResponse(
        validator=results['validator'],
        network=results['network'],
        change_session=results['change_session'],
        current_session=results['current_session'],
        excluded_current=results['excluded_current'],
        comment=results.get('comment'),
        before_sessions=[SessionInfo(**s) for s in results['before_sessions']],
        after_sessions=[SessionInfo(**s) for s in results['after_sessions']],
        before_stats=PeriodStats(**results['before_stats']),
        after_stats=PeriodStats(**results['after_stats']),
        improvement=improvement,
        improvement_pct=improvement_pct,
        direction=direction,
        overall_grade=results['overall_grade'],
        overall_auth_inclusion=results['overall_auth_inclusion'],
        overall_para_inclusion=results['overall_para_inclusion'],
        analysis_id=analysis_id,
    )

    return response


@app.get("/api/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint

    Returns:
        Health status, uptime, cache stats
    """
    # Get cache statistics
    cache_dir = Path(".cache")
    cache_stats = {}

    if cache_dir.exists():
        cache_files = list(cache_dir.glob("*.json"))
        total_size_mb = sum(f.stat().st_size for f in cache_files) / (1024 * 1024)

        cache_stats = {
            'cached_sessions': len(cache_files),
            'total_size_mb': round(total_size_mb, 2),
            'cache_path': str(cache_dir.absolute())
        }

    # Get database statistics
    db_stats = db.get_stats()

    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        cache_stats={
            'session_cache': cache_stats,
            'analysis_database': db_stats
        },
        uptime_seconds=round(time.time() - startup_time, 2)
    )


# Serve frontend static files
frontend_dir = Path(__file__).parent.parent / "frontend"

@app.get("/")
def serve_frontend():
    """Serve the main frontend page"""
    index_file = frontend_dir / "index.html"
    if not index_file.exists():
        return JSONResponse(
            status_code=503,
            content={"message": "Frontend not yet deployed. API is available at /api/*"}
        )
    return FileResponse(index_file)


# Mount static files if frontend directory exists
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Remove in production
        log_level="info"
    )
