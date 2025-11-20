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

        # Note: We don't use cache deduplication here because different parameters
        # (sessions_before, sessions_after, comment, etc.) should produce different results.
        # The session data itself is already efficiently cached in .cache/ directory,
        # so re-running with different parameters is fast.

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


@app.get("/share/{analysis_id}")
@limiter.limit("50/minute")
def view_shared_analysis(request: Request, analysis_id: str):
    """View a shared analysis in HTML format

    This provides a user-friendly view of saved analyses when accessed via browser.
    The /api/analysis/{id} endpoint returns JSON for API consumers.

    Args:
        request: FastAPI request (for rate limiting)
        analysis_id: Short analysis ID from URL

    Returns:
        HTML page with analysis results
    """
    from fastapi.responses import HTMLResponse

    analysis = db.get_analysis(analysis_id)

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Get the analysis data
    results = analysis['results']

    # Calculate improvement metrics
    improvement = results.get('improvement', 0)
    improvement_pct = 0
    direction = 'no_change'

    if improvement is not None:
        before_score = results['before_stats'].get('aggregated_score', 0)
        if before_score > 0:
            improvement_pct = (improvement / before_score) * 100

        if improvement > 0.01:
            direction = "improvement"
        elif improvement < -0.01:
            direction = "decline"

    # Generate HTML
    before_stats = results['before_stats']
    after_stats = results['after_stats']

    # Direction arrow and color
    arrow = "↑" if direction == "improvement" else "↓" if direction == "decline" else "→"
    color = "green" if direction == "improvement" else "red" if direction == "decline" else "gray"

    # Interpretation text
    if abs(improvement) < 0.01:
        interpretation = "✓ No significant change in performance"
        interp_color = "gray"
    elif improvement > 0.05:
        interpretation = "✓✓ SIGNIFICANT IMPROVEMENT - Configuration change appears beneficial"
        interp_color = "green"
    elif improvement > 0.02:
        interpretation = "✓ Moderate improvement - Configuration change likely beneficial"
        interp_color = "green"
    elif improvement > 0:
        interpretation = "≈ Slight improvement - More data may be needed"
        interp_color = "gray"
    elif improvement > -0.02:
        interpretation = "≈ Slight decline - More data may be needed"
        interp_color = "gray"
    elif improvement > -0.05:
        interpretation = "✗ Moderate decline - Configuration change may be detrimental"
        interp_color = "orange"
    else:
        interpretation = "✗✗ SIGNIFICANT DECLINE - Consider reverting configuration change"
        interp_color = "red"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Analysis Results - Performance Analyzer</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            .grade-a {{ color: #16a34a; }}
            .grade-b {{ color: #ca8a04; }}
            .grade-c {{ color: #ea580c; }}
            .grade-d, .grade-f {{ color: #dc2626; }}
        </style>
    </head>
    <body class="bg-gray-50">
        <div class="min-h-screen py-8 px-4">
            <div class="max-w-4xl mx-auto">
                <div class="mb-6">
                    <h1 class="text-3xl font-bold text-gray-900">Shared Analysis Results</h1>
                    <p class="text-gray-600 mt-2">View-only link • <a href="/" class="text-blue-600 hover:underline">Create your own analysis</a></p>
                </div>

                <div class="bg-white rounded-lg shadow-md p-6 mb-6">
                    <h2 class="text-2xl font-bold text-gray-900 mb-4">Analysis Results</h2>

                    <div class="grid grid-cols-2 gap-4 mb-6 text-sm">
                        <div>
                            <p class="text-gray-600">Network</p>
                            <p class="font-medium capitalize">{results['network']}</p>
                        </div>
                        <div>
                            <p class="text-gray-600">Change Session</p>
                            <p class="font-medium">{results['change_session']}</p>
                        </div>
                        <div class="col-span-2">
                            <p class="text-gray-600">Validator Address</p>
                            <p class="font-mono text-xs break-all">{results['validator']}</p>
                        </div>
                        {'<div class="col-span-2"><p class="text-gray-600">Comment</p><p class="font-medium">' + str(results.get('comment', '')) + '</p></div>' if results.get('comment') else ''}
                    </div>

                    <div class="border-t pt-6">
                        <h3 class="text-lg font-bold mb-4">Score Comparison</h3>

                        <div class="grid grid-cols-3 gap-4 mb-4">
                            <div class="text-center p-4 bg-gray-50 rounded-lg">
                                <p class="text-sm text-gray-600 mb-1">Before</p>
                                <p class="text-3xl font-bold">{before_stats['aggregated_score']:.4f}</p>
                                <p class="text-xl font-medium mt-1 grade-{before_stats['aggregated_grade'][0].lower()}">{before_stats['aggregated_grade']}</p>
                                <p class="text-sm text-gray-600 mt-2">{before_stats['para_count']} para sessions</p>
                            </div>

                            <div class="flex flex-col items-center justify-center">
                                <span class="text-4xl text-{color}-600">{arrow}</span>
                                <p class="font-medium mt-2 text-{color}-600">{improvement_pct:+.2f}%</p>
                            </div>

                            <div class="text-center p-4 bg-gray-50 rounded-lg">
                                <p class="text-sm text-gray-600 mb-1">After</p>
                                <p class="text-3xl font-bold">{after_stats['aggregated_score']:.4f}</p>
                                <p class="text-xl font-medium mt-1 grade-{after_stats['aggregated_grade'][0].lower()}">{after_stats['aggregated_grade']}</p>
                                <p class="text-sm text-gray-600 mt-2">{after_stats['para_count']} para sessions</p>
                            </div>
                        </div>

                        <div class="mt-4 p-4 rounded-lg bg-{interp_color}-50 border border-{interp_color}-200">
                            <p class="font-medium text-{interp_color}-800">{interpretation}</p>
                        </div>
                    </div>

                    <div class="mt-6 pt-6 border-t">
                        <p class="text-sm text-gray-600 mb-2">Analysis ID: <span class="font-mono">{analysis_id}</span></p>
                        <p class="text-sm text-gray-600">Analyzed: {analysis['timestamp']}</p>
                    </div>
                </div>

                <div class="text-center text-sm text-gray-500">
                    <p>Powered by the official Turboflakes ONE-T Performance Score formula</p>
                    <p class="mt-1"><a href="/" class="text-blue-600 hover:underline">Analyze your own validator</a></p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


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
