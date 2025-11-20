"""
SQLite database handler for storing analysis results
Uses synchronous SQLite as recommended by original developer
"""
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import secrets


class AnalysisDatabase:
    """Simple SQLite database for storing and retrieving analysis results"""

    def __init__(self, db_path: str = "data/analyses.db"):
        """Initialize database connection

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            # Enable WAL mode for better concurrent read performance
            conn.execute("PRAGMA journal_mode=WAL")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    network TEXT NOT NULL,
                    address TEXT NOT NULL,
                    change_session INTEGER NOT NULL,
                    params_json TEXT NOT NULL,
                    results_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)

            # Index for looking up by validator and session
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_address_session
                ON analyses(address, change_session, network)
            """)

            # Index for timestamp-based queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON analyses(timestamp DESC)
            """)

            conn.commit()

    def _generate_short_id(self, data: Dict) -> str:
        """Generate a short, URL-friendly ID for an analysis

        Uses first 8 characters of hash for readability
        Includes random component to avoid collisions

        Args:
            data: Analysis data to hash

        Returns:
            Short ID string (8-12 characters)
        """
        # Create deterministic part from analysis parameters
        key_parts = [
            str(data.get('network', '')),
            str(data.get('address', '')),
            str(data.get('change_session', '')),
        ]
        key_string = '_'.join(key_parts)
        hash_part = hashlib.sha256(key_string.encode()).hexdigest()[:8]

        # Add random component to ensure uniqueness
        random_part = secrets.token_urlsafe(4)

        return f"{hash_part}{random_part}"

    def save_analysis(self, params: Dict, results: Dict) -> str:
        """Save analysis results to database

        Args:
            params: Analysis parameters (request data)
            results: Analysis results

        Returns:
            Analysis ID (short slug for URLs)
        """
        # Generate unique ID
        analysis_id = self._generate_short_id(params)

        # Check if ID already exists (very unlikely but handle it)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT id FROM analyses WHERE id = ?", (analysis_id,))
            if cursor.fetchone():
                # ID collision - add more random characters
                analysis_id = self._generate_short_id(params) + secrets.token_urlsafe(2)

        # Prepare data
        timestamp = datetime.utcnow().isoformat()
        created_at = datetime.utcnow().timestamp()

        # Convert to JSON
        params_json = json.dumps(params)
        results_json = json.dumps(results, default=str)  # default=str handles non-serializable types

        # Insert into database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO analyses
                (id, timestamp, network, address, change_session, params_json, results_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis_id,
                timestamp,
                params.get('network', 'kusama'),
                params.get('address', ''),
                params.get('change_session', 0),
                params_json,
                results_json,
                created_at
            ))
            conn.commit()

        return analysis_id

    def get_analysis(self, analysis_id: str) -> Optional[Dict]:
        """Retrieve analysis results by ID

        Args:
            analysis_id: Analysis ID

        Returns:
            Dict with params and results, or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT params_json, results_json, timestamp, network, address, change_session
                FROM analyses
                WHERE id = ?
            """, (analysis_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': analysis_id,
                'timestamp': row['timestamp'],
                'network': row['network'],
                'address': row['address'],
                'change_session': row['change_session'],
                'params': json.loads(row['params_json']),
                'results': json.loads(row['results_json'])
            }

    def find_recent_analysis(self, address: str, change_session: int, network: str,
                            max_age_hours: int = 24) -> Optional[str]:
        """Find a recent analysis for the same parameters

        This enables cache deduplication - if someone analyzed the same
        validator/session recently, return that analysis ID

        Args:
            address: Validator address
            change_session: Change session number
            network: Network name
            max_age_hours: Maximum age in hours (default: 24)

        Returns:
            Analysis ID if found, None otherwise
        """
        cutoff_timestamp = datetime.utcnow().timestamp() - (max_age_hours * 3600)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id
                FROM analyses
                WHERE address = ?
                AND change_session = ?
                AND network = ?
                AND created_at > ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (address, change_session, network, cutoff_timestamp))

            row = cursor.fetchone()
            return row[0] if row else None

    def get_stats(self) -> Dict:
        """Get database statistics

        Returns:
            Dict with database stats
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM analyses")
            total_analyses = cursor.fetchone()[0]

            cursor = conn.execute("""
                SELECT COUNT(DISTINCT address) FROM analyses
            """)
            unique_validators = cursor.fetchone()[0]

            cursor = conn.execute("""
                SELECT network, COUNT(*) as count
                FROM analyses
                GROUP BY network
            """)
            network_counts = dict(cursor.fetchall())

            # Database file size
            db_size_mb = self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0

            return {
                'total_analyses': total_analyses,
                'unique_validators': unique_validators,
                'by_network': network_counts,
                'db_size_mb': round(db_size_mb, 2)
            }

    def vacuum(self):
        """Vacuum database to reclaim space and optimize

        Should be run periodically (e.g., weekly via cron)
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("VACUUM")
            conn.commit()

    def get_improvements(self, network: Optional[str] = None,
                         sort_by: str = "date",
                         limit: int = 100,
                         offset: int = 0) -> Dict:
        """Get analyses that showed improvement and have comments

        Used for the community improvements page to showcase successful
        configuration changes.

        Args:
            network: Filter by network (kusama/polkadot), None for all
            sort_by: Sort order - "date" (newest first) or "improvement" (highest first)
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            Dict with items list and total count
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Build query conditions
            conditions = []
            params = []

            if network:
                conditions.append("network = ?")
                params.append(network)

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # Get total count first (before limit/offset)
            count_query = f"""
                SELECT COUNT(*) FROM analyses
                {where_clause}
            """
            cursor = conn.execute(count_query, params)
            total_in_db = cursor.fetchone()[0]

            # Determine sort order
            if sort_by == "improvement":
                order_clause = "ORDER BY created_at DESC"  # Will sort in Python after filtering
            else:  # date
                order_clause = "ORDER BY created_at DESC"

            # Get all matching records (we'll filter for improvement/comment in Python)
            query = f"""
                SELECT id, timestamp, network, address, change_session, results_json
                FROM analyses
                {where_clause}
                {order_clause}
            """

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            # Filter for improvement > 0 and non-empty comment
            items = []
            for row in rows:
                results = json.loads(row['results_json'])

                # Check if has improvement and comment
                improvement = results.get('improvement', 0)
                comment = results.get('comment', '')

                if improvement and improvement > 0 and comment and comment.strip():
                    # Extract session range info
                    before_sessions = results.get('before_sessions', [])
                    after_sessions = results.get('after_sessions', [])

                    first_before = min([s.get('session', 0) for s in before_sessions]) if before_sessions else None
                    last_after = max([s.get('session', 0) for s in after_sessions]) if after_sessions else None

                    items.append({
                        'id': row['id'],
                        'timestamp': row['timestamp'],
                        'network': row['network'],
                        'address': row['address'],
                        'change_session': row['change_session'],
                        'improvement_pct': results.get('improvement_pct', 0),
                        'comment': comment,
                        'first_before_session': first_before,
                        'last_after_session': last_after
                    })

            # Sort by improvement if requested
            if sort_by == "improvement":
                items.sort(key=lambda x: x['improvement_pct'], reverse=True)

            # Apply pagination
            total_improvements = len(items)
            paginated_items = items[offset:offset + limit]

            return {
                'items': paginated_items,
                'total': total_improvements,
                'limit': limit,
                'offset': offset
            }
