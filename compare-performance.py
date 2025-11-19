#!/usr/bin/env python3
"""
Turboflakes Validator Performance Comparison Script
Compares validator scores before and after configuration changes

Uses the official Turboflakes ONE-T Performance Score formula:
https://github.com/turboflakes/one-t/blob/main/SCORES.md

Performance Score = (1 - MVR) * 0.50 + BAR * 0.25 +
                    ((avg_pts - min_pts) / (max_pts - min_pts)) * 0.18 +
                    (pv_sessions / total_sessions) * 0.07

Where:
- MVR = Missed Votes Ratio
- BAR = Bitfield Availability Ratio
- avg_pts = Average paravalidator points (normalized)
- pv_sessions/total_sessions = Paravalidator participation ratio
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Optional, Tuple

import requests


class ValidatorPerformanceAnalyzer:
    """Analyze validator performance using Turboflakes API"""

    # Network API endpoints
    NETWORKS = {
        'kusama': 'https://kusama-onet-api.turboflakes.io',
        'polkadot': 'https://polkadot-onet-api.turboflakes.io',
    }

    # Grade thresholds (based on Turboflakes scoring)
    GRADE_THRESHOLDS = [
        ('A+', 0.99),
        ('A', 0.95),
        ('A-', 0.90),
        ('B+', 0.85),
        ('B', 0.80),
        ('B-', 0.75),
        ('C+', 0.70),
        ('C', 0.60),
        ('C-', 0.50),
        ('D', 0.40),
        ('F', 0.0),
    ]

    def __init__(self, network: str = 'kusama', use_network_normalization: bool = False):
        """Initialize the analyzer

        Args:
            network: Network name ('kusama' or 'polkadot')
            use_network_normalization: If True, normalize against network-wide stats
        """
        if network.lower() not in self.NETWORKS:
            raise ValueError(f"Network must be one of: {', '.join(self.NETWORKS.keys())}")

        self.network = network.lower()
        self.api_base = self.NETWORKS[self.network]
        self.use_network_normalization = use_network_normalization

        # Setup cache directory
        self.cache_dir = Path(__file__).parent / '.cache'
        if use_network_normalization:
            self.cache_dir.mkdir(exist_ok=True)

        # Cache for address conversions (avoid repeated API calls)
        self._address_cache = {}

    def convert_to_generic_ss58(self, address: str) -> str:
        """Convert address to generic SS58 format (prefix 42)

        CRITICAL: Turboflakes stores all addresses in generic SS58 format (starting with '5'),
        regardless of the network-specific format used in queries.

        For example:
        - Polkadot format: 12Qq3fn9xnFZ37Ltcj6BH8NSpAQjEMp2oKnEALa7bbuguU4L (prefix 0)
        - Generic SS58:   5DUXuLX66zz5baLNf63B8yYHxYR5Y4Ftiq3k13am3WtAipuL (prefix 42)

        Without this conversion, validators won't be found in network-wide queries!

        Args:
            address: Validator address in any SS58 format

        Returns:
            Address in generic SS58 format (prefix 42)
        """
        # Check cache first (avoid repeated API calls)
        if address in self._address_cache:
            return self._address_cache[address]

        # Query the API with the address - it will return the generic SS58 format
        url = f"{self.api_base}/api/v1/validators/{address}/grade"
        params = {
            'number_last_sessions': 1,
        }

        try:
            # Build full URL with parameters for display
            param_str = '&'.join(f"{k}={v}" for k, v in params.items())
            full_url = f"{url}?{param_str}"
            print(f"API Query: {full_url}", file=sys.stderr)
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            generic_address = data.get('address')
            if generic_address:
                # Cache the result
                self._address_cache[address] = generic_address
                return generic_address
            # Fallback: if no conversion available, return original
            self._address_cache[address] = address
            return address
        except Exception as e:
            print(f"Warning: Could not convert address format, using original: {e}", file=sys.stderr)
            # Cache the original address as fallback
            self._address_cache[address] = address
            return address

    def get_current_session(self, address: str) -> int:
        """Get the latest available session number from Turboflakes API

        Args:
            address: Validator address

        Returns:
            Latest session number returned by the API
        """
        url = f"{self.api_base}/api/v1/validators/{address}/grade"
        params = {
            'number_last_sessions': 1,
            'show_summary': 'true'
        }

        try:
            # Build full URL with parameters for display
            param_str = '&'.join(f"{k}={v}" for k, v in params.items())
            full_url = f"{url}?{param_str}"
            print(f"API Query: {full_url}", file=sys.stderr)
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            sessions = data.get('sessions', [])
            if sessions:
                return sessions[0]
            # Fallback to sessions_data if available
            sessions_data = data.get('sessions_data', [])
            if sessions_data:
                return sessions_data[0].get('session')
            raise ValueError("No session data available")
        except Exception as e:
            print(f"Error fetching current session: {e}", file=sys.stderr)
            sys.exit(1)

    def fetch_validator_data(self, address: str, num_sessions: int = 30) -> Dict:
        """Fetch validator grade data from Turboflakes API

        Args:
            address: Validator address
            num_sessions: Number of recent sessions to fetch

        Returns:
            Dict containing validator data
        """
        url = f"{self.api_base}/api/v1/validators/{address}/grade"
        params = {
            'number_last_sessions': num_sessions,
            'show_summary': 'true'
        }

        try:
            # Build full URL with parameters for display
            param_str = '&'.join(f"{k}={v}" for k, v in params.items())
            full_url = f"{url}?{param_str}"
            print(f"API Query: {full_url}", file=sys.stderr)
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}", file=sys.stderr)
            sys.exit(1)

    def _get_cache_path(self, session: int) -> Path:
        """Get cache file path for a session

        Args:
            session: Session number

        Returns:
            Path to cache file
        """
        return self.cache_dir / f"{self.network}_session_{session}.json"

    def fetch_network_session_data(self, session: int, use_cache: bool = True) -> Optional[Dict]:
        """Fetch network-wide validator data for a specific session

        Args:
            session: Session number to fetch
            use_cache: Whether to use cached data if available

        Returns:
            Dict with network statistics and all validator scores, or None if error
        """
        cache_path = self._get_cache_path(session)

        # Try to load from cache
        if use_cache and cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    cached_data = json.load(f)
                    # Verify it's the right session
                    if cached_data.get('session') == session:
                        return cached_data
            except (json.JSONDecodeError, IOError):
                pass  # Cache corrupted, fetch fresh

        # Fetch from API
        url = f"{self.api_base}/api/v1/validators"
        params = {
            'role': 'authority',  # Gets all authorities (both para and auth-only)
            'session': session,
            'show_summary': 'true'
        }

        try:
            # Build full URL with parameters for display
            param_str = '&'.join(f"{k}={v}" for k, v in params.items())
            full_url = f"{url}?{param_str}"
            print(f"API Query: {full_url}", file=sys.stderr)
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()

            # Process data: Store ALL validators (para + auth-only), calculate scores for paravalidators
            all_validators = []  # Store all validator data
            validators_with_scores = []  # Store scored paravalidators for ranking
            para_points_list = []

            # First pass: collect all para points for normalization
            # Note: backing points = pt - (authored_blocks * 20)
            # Validators get 20 bonus points per block they author, but this
            # should NOT be included in backing points normalization
            for validator in data.get('data', []):
                if validator.get('is_para') and validator.get('para_summary'):
                    pt = validator['para_summary'].get('pt')
                    ab = validator['para_summary'].get('ab', 0)  # authored blocks
                    # Include validators even with 0 or null points
                    # (they were selected as paravalidators but had no activity)
                    if pt is not None:
                        # Calculate pure backing points (excluding authored block bonus)
                        backing_points = pt - (ab * 20)
                        para_points_list.append(backing_points)
                    else:
                        # No activity = 0 backing points
                        para_points_list.append(0)

            if not para_points_list:
                return None  # No paravalidator data for this session

            # Calculate network-wide min/max for backing points normalization
            network_min = min(para_points_list)
            network_max = max(para_points_list)

            # Second pass: Store all validators, calculate scores only for paravalidators
            for validator in data.get('data', []):
                # Store all validators (both para and auth-only) so we can find any validator
                # But only calculate scores for paravalidators

                if validator.get('is_para'):
                    # Handle two cases:
                    # 1. Normal para session: para_summary exists with vote/point data
                    # 2. Inactive para session: is_para=true but para_summary=null
                    #    (validator was selected but had no para work - only bitfields)

                    if validator.get('para_summary'):
                        # Normal para session with backing points
                        pt = validator['para_summary'].get('pt', 0)
                        ab = validator['para_summary'].get('ab', 0)
                        pure_backing_points = pt - (ab * 20)

                        score_data = self._calculate_validator_score_from_network_data(
                            validator, network_min, network_max
                        )
                    else:
                        # Inactive para session: para_summary is null
                        # This happens when validator is selected as paravalidator but had no work
                        # They may have bitfields but no votes or backing points
                        pure_backing_points = 0

                        # Calculate score with zero para activity
                        # MVR=0 (no votes to miss), BAR from bitfields (if any), PTS=0, PV=0.07
                        para_obj = validator.get('para', {})
                        bitfields = para_obj.get('bitfields', {})
                        ba = bitfields.get('ba', 0)
                        bu = bitfields.get('bu', 0)
                        total_bitfields = ba + bu

                        if total_bitfields > 0:
                            bar = ba / total_bitfields
                        else:
                            bar = 1.0  # No bitfields recorded, assume perfect

                        # Score components for inactive para session
                        mvr_component = 1.0 * 0.50  # No votes = perfect MVR
                        bar_component = bar * 0.25
                        pts_component = 0.0 * 0.18  # No backing points
                        pv_component = 1.0 * 0.07   # Was selected as para

                        score = mvr_component + bar_component + pts_component + pv_component

                        score_data = {
                            'score': score,
                        'backing_points': 0,
                        'mvr': 0.0,
                        'bar': bar,
                        'missed_votes': 0,
                        'total_votes': 0,
                    }

                    if score_data:
                        validators_with_scores.append({
                            'address': validator['address'],
                            'score': score_data['score'],
                            'backing_points': pure_backing_points,
                            'mvr': score_data['mvr'],
                            'bar': score_data['bar'],
                            'missed_votes': score_data['missed_votes'],
                            'total_votes': score_data['total_votes'],
                            'inactive': validator.get('para_summary') is None,  # Flag inactive para sessions
                        })

                # Store ALL validators (para and auth-only) with their raw data
                all_validators.append(validator)

            # Sort scored validators by score (descending)
            validators_with_scores.sort(key=lambda x: x['score'], reverse=True)

            # Create cache data
            cache_data = {
                'session': session,
                'network': self.network,
                'timestamp': datetime.utcnow().isoformat(),
                'backing_points_stats': {
                    'min': network_min,
                    'max': network_max,
                    'avg': sum(para_points_list) // len(para_points_list),
                    'median': sorted(para_points_list)[len(para_points_list) // 2],
                    'count': len(para_points_list)
                },
                'validators': all_validators,  # ALL validators (para + auth-only)
                'scored_validators': validators_with_scores  # Scored paravalidators for ranking
            }

            # Save to cache
            if use_cache:
                try:
                    with open(cache_path, 'w') as f:
                        json.dump(cache_data, f, indent=2)
                except IOError as e:
                    print(f"Warning: Could not write cache: {e}", file=sys.stderr)

            return cache_data

        except requests.exceptions.RequestException as e:
            print(f"Warning: Could not fetch network data for session {session}: {e}", file=sys.stderr)
            return None

    def _calculate_validator_score_from_network_data(self, validator_data: Dict,
                                                      network_min: int, network_max: int) -> Optional[Dict]:
        """Calculate score for a validator using network-wide normalization

        Args:
            validator_data: Single validator's data from network query
            network_min: Network-wide minimum backing points
            network_max: Network-wide maximum backing points

        Returns:
            Dict with score components or None
        """
        if not validator_data.get('is_para') or not validator_data.get('para_summary'):
            return None

        para_summary = validator_data['para_summary']

        # Component 1: Missed Vote Ratio (50% weight)
        ev = para_summary.get('ev', 0)
        iv = para_summary.get('iv', 0)
        mv = para_summary.get('mv', 0)
        total_votes = ev + iv + mv

        if total_votes == 0:
            mvr = 0
        else:
            mvr = mv / total_votes

        mvr_component = (1 - mvr) * 0.50

        # Component 2: Bitfield Availability Ratio (25% weight)
        para = validator_data.get('para', {})
        bitfields = para.get('bitfields', {})
        ba = bitfields.get('ba', 0)
        bu = bitfields.get('bu', 0)

        total_bitfields = ba + bu
        if total_bitfields > 0:
            bar = ba / total_bitfields
        else:
            bar = 1.0

        bar_component = bar * 0.25

        # Component 3: Normalized backing points (18% weight) - NETWORK-WIDE
        # Note: backing points = pt - (authored_blocks * 20)
        pt = para_summary.get('pt', 0)
        ab = para_summary.get('ab', 0)
        current_backing_points = pt - (ab * 20)

        if network_max > network_min:
            normalized_pts = (current_backing_points - network_min) / (network_max - network_min)
        else:
            normalized_pts = 0  # All validators have same points

        pts_component = normalized_pts * 0.18

        # Component 4: Paravalidator session ratio (7% weight)
        pv_ratio_component = 1.0 * 0.07  # Single session, they are para

        # Calculate total performance score
        performance_score = mvr_component + bar_component + pts_component + pv_ratio_component

        return {
            'score': performance_score,
            'backing_points': current_backing_points,  # Pure backing points (no authored block bonus)
            'mvr': mvr,
            'bar': bar,
            'missed_votes': mv,
            'total_votes': total_votes,
        }

    def fetch_multiple_network_sessions(self, sessions: List[int], max_workers: int = 5) -> Dict[int, Dict]:
        """Fetch network data for multiple sessions in parallel

        Args:
            sessions: List of session numbers to fetch
            max_workers: Number of parallel workers

        Returns:
            Dict mapping session number to network data
        """
        results = {}

        print(f"Fetching network-wide data for {len(sessions)} sessions...", file=sys.stderr)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_session = {
                executor.submit(self.fetch_network_session_data, session): session
                for session in sessions
            }

            for future in as_completed(future_to_session):
                session = future_to_session[future]
                try:
                    data = future.result()
                    if data:
                        results[session] = data
                        para_count = sum(1 for v in data['validators'] if v.get('is_para'))
                        total_count = len(data['validators'])
                        print(f"  ✓ Session {session} ({para_count}/{total_count} para/auth)", file=sys.stderr)
                    else:
                        print(f"  ✗ Session {session} (API returned no validator data - session may not exist or be too old)", file=sys.stderr)
                except Exception as e:
                    print(f"  ✗ Session {session} error: {e}", file=sys.stderr)

        print(f"Network data fetch complete: {len(results)}/{len(sessions)} sessions", file=sys.stderr)
        return results

    def get_validator_ranking(self, address: str, session: int, network_data: Dict) -> Optional[Dict]:
        """Get validator's ranking within the network for a session

        Args:
            address: Validator address (any SS58 format)
            session: Session number
            network_data: Network data from fetch_network_session_data

        Returns:
            Dict with ranking information or None
        """
        if not network_data or network_data.get('session') != session:
            return None

        # Use scored_validators for ranking (contains scores, sorted by score)
        scored_validators = network_data.get('scored_validators', [])
        if not scored_validators:
            return None

        # Convert address to generic SS58 format for comparison
        # (network data uses generic SS58 format)
        generic_address = self.convert_to_generic_ss58(address)

        # Find validator in scored list (sorted by score)
        for rank, val in enumerate(scored_validators, 1):
            if val['address'] == generic_address:
                total = len(scored_validators)
                percentile = int(100 - ((rank / total) * 100))

                # Calculate vs average
                scores = [v['score'] for v in scored_validators]
                avg_score = sum(scores) / len(scores)
                vs_avg_pct = int(((val['score'] - avg_score) / avg_score) * 100)

                return {
                    'rank': rank,
                    'total': total,
                    'percentile': percentile,
                    'score': val['score'],
                    'avg_score': avg_score,
                    'vs_avg_pct': vs_avg_pct,
                    'backing_points': val['backing_points'],
                    'total_votes': val.get('total_votes', 0),  # For detecting inactive para sessions
                    'missed_votes': val.get('missed_votes', 0),
                    'network_backing_stats': network_data['backing_points_stats'],
                    'approximate': False  # Found in network data
                }

        # Validator not found in scored list
        # Check if they're in the full validators list (auth-only)
        validators = network_data.get('validators', [])
        for val in validators:
            if val['address'] == generic_address:
                # Found validator - check why they're not in scored list
                is_para = val.get('is_para')
                if is_para is False or is_para is None:
                    # Auth-only session - not selected as paravalidator
                    is_para_status = "false" if is_para is False else "absent (field not present in API response)"
                    print(f"ℹ️  Session {session}: is_para: {is_para_status}, no paravalidator score. Auth-only, no para work", file=sys.stderr)
                    return None  # No para score for auth-only sessions

        # Validator not found at all in this session (shouldn't happen in network-normalized mode)
        print(f"⚠️  Session {session}: Validator {address} not found in session data at all", file=sys.stderr)
        return None


    def calculate_aggregated_score(self, sessions_data: List[Dict]) -> Optional[Dict]:
        """Calculate aggregated performance score using Turboflakes method

        Aggregates all statistics across sessions first, then calculates ONE score.
        This matches how Turboflakes calculates scores and is more statistically sound
        than averaging per-session scores.

        Args:
            sessions_data: List of session data dicts (only para sessions)

        Returns:
            Dict with aggregated score and components
        """
        if not sessions_data:
            return None

        # Filter to only paravalidator sessions
        para_sessions = [s for s in sessions_data if s.get('is_para', False)]
        if not para_sessions:
            return None

        # Count active vs inactive para sessions
        # Active = has backing work (backing_points > 0)
        # Inactive = para_summary is null OR backing_points == 0
        active_para = 0
        inactive_para = 0
        for s in para_sessions:
            para_summary = s.get('para_summary')
            if para_summary:
                pt = para_summary.get('pt', 0)
                ab = para_summary.get('ab', 0)
                backing_points = pt - (ab * 20)
                if backing_points > 0:
                    active_para += 1
                else:
                    inactive_para += 1
            else:
                inactive_para += 1

        # Aggregate votes across all sessions
        total_ev = 0
        total_iv = 0
        total_mv = 0

        # Aggregate bitfields across all sessions
        total_ba = 0
        total_bu = 0

        # Collect backing points for normalization
        all_backing_points = []

        for session in para_sessions:
            para_summary = session.get('para_summary')
            if para_summary:
                # Votes
                total_ev += para_summary.get('ev', 0)
                total_iv += para_summary.get('iv', 0)
                total_mv += para_summary.get('mv', 0)

                # Backing points
                pt = para_summary.get('pt', 0)
                ab = para_summary.get('ab', 0)
                backing_points = pt - (ab * 20)
                all_backing_points.append(backing_points)

            # Bitfields (available even for inactive para)
            para = session.get('para', {})
            bitfields = para.get('bitfields', {})
            total_ba += bitfields.get('ba', 0)
            total_bu += bitfields.get('bu', 0)

        # Component 1: MVR (50% weight)
        total_votes = total_ev + total_iv + total_mv
        if total_votes > 0:
            mvr = total_mv / total_votes
        else:
            mvr = 0.0
        mvr_component = (1 - mvr) * 0.50

        # Component 2: BAR (25% weight)
        total_bitfields = total_ba + total_bu
        if total_bitfields > 0:
            bar = total_ba / total_bitfields
        else:
            bar = 1.0
        bar_component = bar * 0.25

        # Component 3: Normalized backing points (18% weight)
        if all_backing_points:
            min_pts = min(all_backing_points)
            max_pts = max(all_backing_points)
            avg_pts = sum(all_backing_points) / len(all_backing_points)

            if max_pts > min_pts:
                pts_normalized = (avg_pts - min_pts) / (max_pts - min_pts)
            else:
                pts_normalized = 1.0 if avg_pts > 0 else 0.0
        else:
            pts_normalized = 0.0
        pts_component = pts_normalized * 0.18

        # Component 4: PV ratio (7% weight)
        # This is always 1.0 for para-only sessions
        pv_component = 1.0 * 0.07

        # Calculate final score
        score = mvr_component + bar_component + pts_component + pv_component

        return {
            'score': score,
            'grade': self.grade_from_score(score),
            'mvr': mvr,
            'bar': bar,
            'pts_normalized': pts_normalized,
            'total_votes': total_votes,
            'missed_votes': total_mv,
            'explicit_votes': total_ev,
            'implicit_votes': total_iv,
            'total_bitfields': total_bitfields,
            'available_bitfields': total_ba,
            'unavailable_bitfields': total_bu,
            'backing_points': all_backing_points,
            'avg_backing_points': sum(all_backing_points) / len(all_backing_points) if all_backing_points else 0,
            'total_sessions': len(para_sessions),
            'active_para': active_para,
            'inactive_para': inactive_para,
        }

    def calculate_session_score(self, session_data: Dict, sessions_data: List[Dict]) -> Optional[Dict]:
        """Calculate performance score for a single session using Turboflakes formula

        Turboflakes ONE-T Performance Score Formula:
        performance_score = (1 - mvr) * 0.50 + bar * 0.25 +
                           ((avg_pts - min_avg_pts) / (max_avg_pts - min_avg_pts)) * 0.18 +
                           (pv_sessions / total_sessions) * 0.07

        Where:
        - mvr = missed votes ratio
        - bar = bitfield availability ratio
        - avg_pts = average paravalidator points
        - pv_sessions/total_sessions = paravalidator participation ratio

        Args:
            session_data: Session data from API
            sessions_data: All sessions data (needed for normalization)

        Returns:
            Dict with score components or None if not applicable
        """
        # Only calculate score if validator was an authority
        if not session_data.get('is_auth', False):
            return None

        # If paravalidator, calculate full score
        if session_data.get('is_para', False):
            para_summary = session_data.get('para_summary', {})

            # Component 1: Missed Vote Ratio (50% weight)
            ev = para_summary.get('ev', 0)  # Explicit votes
            iv = para_summary.get('iv', 0)  # Implicit votes
            mv = para_summary.get('mv', 0)  # Missed votes

            total_votes = ev + iv + mv
            if total_votes == 0:
                mvr = 0  # No votes = no missed votes
            else:
                mvr = mv / total_votes

            mvr_component = (1 - mvr) * 0.50

            # Component 2: Bitfield Availability Ratio (25% weight)
            para = session_data.get('para', {})
            bitfields = para.get('bitfields', {})
            ba = bitfields.get('ba', 0)  # Available
            bu = bitfields.get('bu', 0)  # Unavailable

            total_bitfields = ba + bu
            if total_bitfields > 0:
                bar = ba / total_bitfields
            else:
                bar = 1.0  # No bitfields = assume 100% availability

            bar_component = bar * 0.25

            # Component 3: Normalized paravalidator points (18% weight)
            # Calculate min/max from all para sessions in the dataset
            # Note: Use backing points (pt - ab*20), not raw pt
            pv_points = []
            for s in sessions_data:
                if s.get('is_para', False):
                    ps = s.get('para_summary', {})
                    pt = ps.get('pt', 0)
                    ab = ps.get('ab', 0)
                    backing_points = pt - (ab * 20)
                    if backing_points > 0:  # Only include sessions with points
                        pv_points.append(backing_points)

            # Calculate backing points for current session
            current_pt = para_summary.get('pt', 0)
            current_ab = para_summary.get('ab', 0)
            current_backing_points = current_pt - (current_ab * 20)

            if pv_points and len(pv_points) > 1 and current_backing_points > 0:
                min_pts = min(pv_points)
                max_pts = max(pv_points)
                if max_pts > min_pts:
                    normalized_pts = (current_backing_points - min_pts) / (max_pts - min_pts)
                else:
                    normalized_pts = 1.0
                pts_component = normalized_pts * 0.18
            else:
                pts_component = 0.0  # Can't calculate without range

            # Component 4: Paravalidator session ratio (7% weight)
            # For single session analysis, this is 1.0 if para, 0.0 if not
            pv_ratio_component = 1.0 * 0.07

            # Calculate total performance score
            performance_score = mvr_component + bar_component + pts_component + pv_ratio_component

            return {
                'score': performance_score,
                'mvr': mvr,
                'bar': bar,
                'mvr_component': mvr_component,
                'bar_component': bar_component,
                'pts_component': pts_component,
                'pv_ratio_component': pv_ratio_component,
                'total_votes': total_votes,
                'missed_votes': mv,
                'para_points': current_backing_points,  # Pure backing points (no authored block bonus)
            }
        else:
            # For authority-only (non-para) sessions
            # These don't contribute to Turboflakes score the same way
            # Return a basic score based on presence
            auth = session_data.get('auth', {})
            ep = auth.get('ep', 0)  # Era points

            # Authority-only sessions: simplified score
            # mvr component = 0.50 (no votes to miss)
            # bar component = 0.25 (no bitfields)
            # pts component = 0 (no para points)
            # pv_ratio = 0 (not a para session)
            base_score = 0.50 + 0.25  # = 0.75

            return {
                'score': base_score,
                'mvr': 0.0,
                'bar': 1.0,
                'mvr_component': 0.50,
                'bar_component': 0.25,
                'pts_component': 0.0,
                'pv_ratio_component': 0.0,
                'total_votes': 0,
                'missed_votes': 0,
                'para_points': 0,
            }

    def grade_from_score(self, score: float) -> str:
        """Convert numeric score to letter grade

        Args:
            score: Performance score (0.0-1.0)

        Returns:
            Letter grade (A+ to F)
        """
        for grade, threshold in self.GRADE_THRESHOLDS:
            if score >= threshold:
                return grade
        return 'F'

    def analyze_sessions(
        self,
        address: str,
        change_session: int,
        sessions_before: int = 10,
        sessions_after: Optional[int] = None,
        exclude_current: bool = False
    ) -> Dict:
        """Analyze validator performance before and after a change

        Args:
            address: Validator address
            change_session: Session number when change was made
            sessions_before: Number of sessions before change to include
            sessions_after: Number of sessions after change (None = auto-detect to latest)
            exclude_current: Whether to exclude the latest returned session (default: False)

        Returns:
            Dict containing analysis results
        """
        # Get latest session to determine range
        current_session = self.get_current_session(address)

        # Calculate how many sessions we need
        if sessions_after is None:
            # Auto-calculate: from change_session to latest (excluding if requested)
            sessions_after_change = current_session - change_session
            if exclude_current:
                sessions_after_change -= 1  # Exclude the latest session if requested

            # Make sure we have at least 1 session after
            if sessions_after_change < 1:
                print(f"Warning: Change session {change_session} is too recent.", file=sys.stderr)
                print(f"Current session is {current_session}. Need at least one completed session after the change.", file=sys.stderr)
                sys.exit(1)

            sessions_after = sessions_after_change

        # ========================================================================
        # NETWORK-NORMALIZED MODE: Query individual sessions (no 192-session limit!)
        # ========================================================================
        if self.use_network_normalization:
            # Convert address to generic SS58 for matching in network data
            generic_address = self.convert_to_generic_ss58(address)

            # Calculate session range
            # Before: (change - before) to (change - 1)
            # After: (change + 1) to (change + after)
            # Combined: (change - before) to (change + after), excluding change itself
            if sessions_before > 0:
                first_session = change_session - sessions_before
            else:
                first_session = change_session + 1  # Start after change if no "before" sessions

            last_session = change_session + sessions_after
            if exclude_current:
                last_session = min(last_session, current_session - 1)

            # Generate all session numbers we need (excluding change_session itself)
            all_session_numbers = [s for s in range(first_session, last_session + 1) if s != change_session]

            print(f"Analyzing {len(all_session_numbers)} sessions ({first_session}-{last_session}) in network-normalized mode", file=sys.stderr)

            # Fetch network data for all sessions (cached, unlimited)
            network_session_data = self.fetch_multiple_network_sessions(all_session_numbers)

            # Build sessions_data by finding our validator in each network session
            sessions_data = []
            for session_num in all_session_numbers:
                if session_num not in network_session_data:
                    print(f"⚠️  Warning: No network-wide data available for session {session_num} (session skipped)", file=sys.stderr)
                    continue

                # Find our validator in this session's data
                net_data = network_session_data[session_num]
                validator_data = None
                for val in net_data.get('validators', []):
                    if val.get('address') == generic_address:
                        validator_data = val
                        break

                if validator_data:
                    # Add session number to the data
                    validator_data['session'] = session_num
                    sessions_data.append(validator_data)
                # If validator not found in session, they weren't active - skip it

            if not sessions_data:
                print("Error: Validator not found in any of the requested sessions", file=sys.stderr)
                sys.exit(1)

            # Calculate inclusion stats from collected sessions
            auth_sessions = sum(1 for s in sessions_data if s.get('is_auth'))
            para_sessions = sum(1 for s in sessions_data if s.get('is_para'))
            authority_inclusion = auth_sessions / len(all_session_numbers) if all_session_numbers else 0.0
            para_authority_inclusion = para_sessions / len(all_session_numbers) if all_session_numbers else 0.0

            # Mock the data structure expected by rest of code
            data = {
                'address': generic_address,
                'grade': '-',  # We calculate our own scores
                'authority_inclusion': authority_inclusion,
                'para_authority_inclusion': para_authority_inclusion,
                'sessions_data': sessions_data
            }

            current_session_actual = current_session

        # ========================================================================
        # REGULAR MODE: Use bulk /grade fetch (192-session limit applies)
        # ========================================================================
        else:
            # Fetch enough sessions to cover before and after
            total_sessions = sessions_before + sessions_after + 5  # +5 buffer

            # Check API limit for /grade endpoint (only applies to regular mode)
            API_HARD_LIMIT = 192
            if total_sessions > API_HARD_LIMIT:
                original_total = total_sessions
                original_sessions_before = sessions_before

                # Cap total_sessions and adjust sessions_before accordingly
                total_sessions = API_HARD_LIMIT
                sessions_before = API_HARD_LIMIT - sessions_after - 5  # Keep the buffer

                print(f"⚠️  API LIMIT: Requested {original_total} sessions exceeds API limit ({API_HARD_LIMIT})", file=sys.stderr)
                print(f"    Adjusted -b from {original_sessions_before} to {sessions_before} to stay within limit", file=sys.stderr)
                print(f"    Analysis will cover sessions {change_session - sessions_before} to {change_session - 1} (before)", file=sys.stderr)

            data = self.fetch_validator_data(address, total_sessions)

            current_session_actual = current_session

            sessions_data = data.get('sessions_data', [])
            if not sessions_data:
                print("Error: No session data available", file=sys.stderr)
                sys.exit(1)

            # Filter out current session if requested
            if exclude_current:
                sessions_data = [s for s in sessions_data if s.get('session') != current_session_actual]

            network_session_data = {}

        # ========================================================================
        # COMMON PATH: Process sessions (works for both modes)
        # ========================================================================

        # Organize sessions
        before_sessions = []
        after_sessions = []

        # In network-normalized mode, we already have network_session_data populated
        # In regular mode, we need to fetch it now
        if self.use_network_normalization:
            # Already fetched above - network_session_data is populated
            pass
        else:
            # Fetch network data if needed for regular mode
            network_session_data = {}
            # (Regular mode doesn't use network normalization)

        for session in sessions_data:
            session_num = session.get('session')

            # Try network-normalized scoring first if enabled
            if self.use_network_normalization and session_num in network_session_data:
                # Get ranking and score from network data
                ranking = self.get_validator_ranking(address, session_num, network_session_data[session_num])
            else:
                ranking = None

            # If we have ranking data from network, use it; otherwise use standard calculation
            if ranking is not None:
                # Network-normalized with ranking
                score = ranking['score']
                session_info = {
                    'session': session_num,
                    'score': score,
                    'grade': self.grade_from_score(score),
                    'is_para': session.get('is_para', True),  # Preserve original value
                    'is_auth': session.get('is_auth', True),
                    'para_summary': session.get('para_summary'),  # PRESERVE for aggregated scoring
                    'para': session.get('para', {}),  # PRESERVE for bitfields
                    'era_points': session.get('auth', {}).get('ep', 0),
                    'mvr': session.get('para_summary', {}).get('mv', 0) / max(1, session.get('para_summary', {}).get('ev', 0) + session.get('para_summary', {}).get('iv', 0) + session.get('para_summary', {}).get('mv', 0)) if session.get('para_summary') else 0.0,
                    'bar': 0.0,  # Not stored in network data, would need to recalculate
                    'missed_votes': session.get('para_summary', {}).get('mv', 0) if session.get('para_summary') else 0,
                    'total_votes': session.get('para_summary', {}).get('ev', 0) + session.get('para_summary', {}).get('iv', 0) + session.get('para_summary', {}).get('mv', 0) if session.get('para_summary') else 0,
                    'para_points': ranking['backing_points'],
                    'ranking': ranking,  # Add ranking info
                    'network_stats': network_session_data[session_num]['backing_points_stats'],
                    'components': {
                        'mvr': 0.0,  # Not separated in network mode
                        'bar': 0.0,
                        'pts': 0.0,
                        'pv_ratio': 0.0,
                    }
                }
            else:
                # Standard single-validator normalization
                score_data = self.calculate_session_score(session, sessions_data)

                if score_data is None:
                    continue  # Skip sessions where validator wasn't active

                score = score_data['score']

                session_info = {
                    'session': session_num,
                    'score': score,
                    'grade': self.grade_from_score(score),
                    'is_para': session.get('is_para', False),
                    'era_points': session.get('auth', {}).get('ep', 0),
                    'mvr': score_data['mvr'],
                    'bar': score_data['bar'],
                    'missed_votes': score_data['missed_votes'],
                    'total_votes': score_data['total_votes'],
                    'para_points': score_data['para_points'],
                    'components': {
                        'mvr': score_data['mvr_component'],
                        'bar': score_data['bar_component'],
                        'pts': score_data['pts_component'],
                        'pv_ratio': score_data['pv_ratio_component'],
                    }
                }

            if session_num < change_session:
                before_sessions.append(session_info)
            elif session_num > change_session:
                after_sessions.append(session_info)

        # Sort by session number
        before_sessions.sort(key=lambda x: x['session'])
        after_sessions.sort(key=lambda x: x['session'])

        # Limit to requested number of sessions
        before_sessions = before_sessions[-sessions_before:]
        if sessions_after is not None:
            after_sessions = after_sessions[:sessions_after]

        # Calculate statistics using aggregated scoring (Turboflakes method)
        def calc_stats(sessions: List[Dict]) -> Dict:
            if not sessions:
                return {
                    'total_count': 0,
                    'para_count': 0,
                    'active_para': 0,
                    'inactive_para': 0,
                    'auth_only_count': 0,
                    'para_percentage': 0.0,
                    'aggregated_score': 0.0,
                    'aggregated_grade': '-',
                    'median_score': 0.0,
                    'min_score': 0.0,
                    'max_score': 0.0,
                }

            # Separate paravalidator sessions from AUTH-only sessions
            para_sessions = [s for s in sessions if s['is_para']]
            auth_only_sessions = [s for s in sessions if not s['is_para']]

            total_count = len(sessions)
            para_count = len(para_sessions)
            auth_only_count = len(auth_only_sessions)
            para_percentage = (para_count / total_count * 100) if total_count > 0 else 0.0

            # Calculate aggregated score using Turboflakes method
            # This aggregates ALL para session data first, then calculates ONE score
            if not para_sessions:
                return {
                    'total_count': total_count,
                    'para_count': para_count,
                    'active_para': 0,
                    'inactive_para': 0,
                    'auth_only_count': auth_only_count,
                    'para_percentage': para_percentage,
                    'aggregated_score': 0.0,
                    'aggregated_grade': '-',
                    'median_score': 0.0,
                    'min_score': 0.0,
                    'max_score': 0.0,
                }

            # Calculate aggregated score (primary metric)
            agg_result = self.calculate_aggregated_score(para_sessions)

            # Also get per-session scores for median/range display
            scores = [s['score'] for s in para_sessions if 'score' in s]

            return {
                'total_count': total_count,
                'para_count': para_count,
                'active_para': agg_result['active_para'] if agg_result else 0,
                'inactive_para': agg_result['inactive_para'] if agg_result else 0,
                'auth_only_count': auth_only_count,
                'para_percentage': para_percentage,
                'aggregated_score': agg_result['score'] if agg_result else 0.0,
                'aggregated_grade': agg_result['grade'] if agg_result else '-',
                'median_score': median(scores) if scores else 0.0,
                'min_score': min(scores) if scores else 0.0,
                'max_score': max(scores) if scores else 0.0,
                'aggregated_details': agg_result,  # For detailed output
            }

        before_stats = calc_stats(before_sessions)
        after_stats = calc_stats(after_sessions)

        # Calculate improvement using aggregated scores
        improvement = None
        if before_stats['para_count'] > 0 and after_stats['para_count'] > 0:
            improvement = after_stats['aggregated_score'] - before_stats['aggregated_score']

        return {
            'validator': address,
            'network': self.network,
            'change_session': change_session,
            'current_session': current_session_actual,
            'excluded_current': exclude_current,
            'before_sessions': before_sessions,
            'after_sessions': after_sessions,
            'before_stats': before_stats,
            'after_stats': after_stats,
            'improvement': improvement,
            'overall_grade': data.get('grade', '-'),
            'overall_auth_inclusion': data.get('authority_inclusion', 0.0),
            'overall_para_inclusion': data.get('para_authority_inclusion', 0.0),
        }

    def print_analysis(self, results: Dict, detailed: bool = False):
        """Print analysis results in a readable format

        Args:
            results: Analysis results from analyze_sessions()
            detailed: Whether to show detailed session-by-session data
        """
        print("=" * 80)
        print(f"VALIDATOR PERFORMANCE ANALYSIS")
        print("=" * 80)
        print(f"Network:          {results['network'].upper()}")
        print(f"Validator:        {results['validator']}")
        print(f"Change Session:   {results['change_session']}")
        print(f"Latest Session:   {results['current_session']}{' (excluded)' if results['excluded_current'] else ''}")
        print(f"Overall Grade:    {results['overall_grade']}")
        print(f"Auth Inclusion:   {results['overall_auth_inclusion']:.2%}")
        print(f"Para Inclusion:   {results['overall_para_inclusion']:.2%}")
        if 'comment' in results and results['comment']:
            print(f"Comment:          {results['comment']}")
        print()

        # Before statistics
        print("-" * 80)
        # Show session range if sessions exist
        before_range = ""
        if results['before_sessions']:
            first_session = results['before_sessions'][0]['session']
            last_session = results['before_sessions'][-1]['session']
            before_range = f"Sessions {first_session}-{last_session}: "
        # Build para count description
        para_desc = f"{results['before_stats']['para_count']} paravalidator"
        if results['before_stats']['inactive_para'] > 0:
            para_desc = f"{results['before_stats']['para_count']} para ({results['before_stats']['active_para']} active, {results['before_stats']['inactive_para']} inactive)"
        print(f"BEFORE CHANGE ({before_range}{results['before_stats']['total_count']} sessions, {para_desc})")
        print("-" * 80)
        if results['before_stats']['para_count'] > 0:
            print(f"Para Rate:        {results['before_stats']['para_percentage']:.1f}%")
            print(f"Score:            {results['before_stats']['aggregated_score']:.4f} ({results['before_stats']['aggregated_grade']})")
            print(f"Session Median:   {results['before_stats']['median_score']:.4f}")
            print(f"Session Range:    {results['before_stats']['min_score']:.4f} - {results['before_stats']['max_score']:.4f}")
            if results['before_stats']['auth_only_count'] > 0:
                print(f"Note:             {results['before_stats']['auth_only_count']} AUTH-only session(s) excluded from statistics")

            if detailed and results['before_sessions']:
                print("\nSession Details:")
                if results['before_sessions'][0].get('ranking'):
                    print("  (Network-normalized scores with ranking)")
                else:
                    print("  (Score = MVR*0.50 + BAR*0.25 + PTS*0.18 + PV*0.07)")

                for s in results['before_sessions']:
                    para_flag = "PARA" if s['is_para'] else "AUTH"
                    # Check if this is an inactive para session (no para work done)
                    # These have backing_points=0 and total_votes=0 in the ranking data
                    if s['is_para'] and s.get('ranking'):
                        rank = s['ranking']
                        if rank.get('backing_points') == 0 and rank.get('total_votes') == 0:
                            para_flag = "PARA-INACTIVE"
                    print(f"  Session {s['session']:6d}: {s['score']:.4f} ({s['grade']}) [{para_flag}]")

                    if s['is_para']:
                        # Show ranking if available (network-normalized mode)
                        if 'ranking' in s and s['ranking']:
                            rank = s['ranking']
                            # Check if this is approximate (validator fetched separately)
                            if rank.get('approximate', False):
                                print(f"    Rank by Score: Not ranked (validator outside API's {rank['total']} returned, {rank['vs_avg_pct']:+d}% vs network avg)")
                                print(f"    Backing Points: {rank['backing_points']} (network min-max: {rank['network_backing_stats']['min']}-{rank['network_backing_stats']['max']}, avg: {rank['network_backing_stats']['avg']})")
                                print(f"    Note: Score calculated using network-wide normalization")
                            else:
                                print(f"    Rank by Score: #{rank['rank']} of {rank['total']} paravalidators (Top {100-rank['percentile']}%, {rank['vs_avg_pct']:+d}% vs avg)")
                                print(f"    Backing Points: {rank['backing_points']} (network: {rank['network_backing_stats']['min']}-{rank['network_backing_stats']['max']}, avg: {rank['network_backing_stats']['avg']})")
                        else:
                            # Standard single-validator mode details
                            c = s['components']
                            print(f"    MVR: {s['mvr']:.3f} ({s['missed_votes']}/{s['total_votes']}) = {c['mvr']:.4f}")
                            print(f"    BAR: {s['bar']:.3f} = {c['bar']:.4f}")
                            print(f"    Backing Points: {s['para_points']:4d} pts = {c['pts']:.4f}")
                            print(f"    PV:  = {c['pv_ratio']:.4f}")
        else:
            print("No data available")
        print()

        # After statistics
        print("-" * 80)
        # Show session range if sessions exist
        after_range = ""
        if results['after_sessions']:
            first_session = results['after_sessions'][0]['session']
            last_session = results['after_sessions'][-1]['session']
            after_range = f"Sessions {first_session}-{last_session}: "
        # Build para count description
        para_desc = f"{results['after_stats']['para_count']} paravalidator"
        if results['after_stats']['inactive_para'] > 0:
            para_desc = f"{results['after_stats']['para_count']} para ({results['after_stats']['active_para']} active, {results['after_stats']['inactive_para']} inactive)"
        print(f"AFTER CHANGE ({after_range}{results['after_stats']['total_count']} sessions, {para_desc})")
        print("-" * 80)
        if results['after_stats']['para_count'] > 0:
            print(f"Para Rate:        {results['after_stats']['para_percentage']:.1f}%")
            print(f"Score:            {results['after_stats']['aggregated_score']:.4f} ({results['after_stats']['aggregated_grade']})")
            print(f"Session Median:   {results['after_stats']['median_score']:.4f}")
            print(f"Session Range:    {results['after_stats']['min_score']:.4f} - {results['after_stats']['max_score']:.4f}")
            if results['after_stats']['auth_only_count'] > 0:
                print(f"Note:             {results['after_stats']['auth_only_count']} AUTH-only session(s) excluded from statistics")

            if detailed and results['after_sessions']:
                print("\nSession Details:")
                if results['after_sessions'][0].get('ranking'):
                    print("  (Network-normalized scores with ranking)")
                else:
                    print("  (Score = MVR*0.50 + BAR*0.25 + PTS*0.18 + PV*0.07)")

                for s in results['after_sessions']:
                    para_flag = "PARA" if s['is_para'] else "AUTH"
                    # Check if this is an inactive para session (no para work done)
                    # These have backing_points=0 and total_votes=0 in the ranking data
                    if s['is_para'] and s.get('ranking'):
                        rank = s['ranking']
                        if rank.get('backing_points') == 0 and rank.get('total_votes') == 0:
                            para_flag = "PARA-INACTIVE"
                    print(f"  Session {s['session']:6d}: {s['score']:.4f} ({s['grade']}) [{para_flag}]")

                    if s['is_para']:
                        # Show ranking if available (network-normalized mode)
                        if 'ranking' in s and s['ranking']:
                            rank = s['ranking']
                            # Check if this is approximate (validator fetched separately)
                            if rank.get('approximate', False):
                                print(f"    Rank by Score: Not ranked (validator outside API's {rank['total']} returned, {rank['vs_avg_pct']:+d}% vs network avg)")
                                print(f"    Backing Points: {rank['backing_points']} (network min-max: {rank['network_backing_stats']['min']}-{rank['network_backing_stats']['max']}, avg: {rank['network_backing_stats']['avg']})")
                                print(f"    Note: Score calculated using network-wide normalization")
                            else:
                                print(f"    Rank by Score: #{rank['rank']} of {rank['total']} paravalidators (Top {100-rank['percentile']}%, {rank['vs_avg_pct']:+d}% vs avg)")
                                print(f"    Backing Points: {rank['backing_points']} (network: {rank['network_backing_stats']['min']}-{rank['network_backing_stats']['max']}, avg: {rank['network_backing_stats']['avg']})")
                        else:
                            # Standard single-validator mode details
                            c = s['components']
                            print(f"    MVR: {s['mvr']:.3f} ({s['missed_votes']}/{s['total_votes']}) = {c['mvr']:.4f}")
                            print(f"    BAR: {s['bar']:.3f} = {c['bar']:.4f}")
                            print(f"    Backing Points: {s['para_points']:4d} pts = {c['pts']:.4f}")
                            print(f"    PV:  = {c['pv_ratio']:.4f}")
        else:
            print("No data available")
        print()

        # Comparison
        print("-" * 80)
        print("COMPARISON")
        print("-" * 80)
        if results['improvement'] is not None:
            # Calculate percentage change relative to baseline (before) score
            if results['before_stats']['aggregated_score'] > 0:
                improvement_pct = (results['improvement'] / results['before_stats']['aggregated_score']) * 100
            else:
                improvement_pct = 0
            direction = "↑ IMPROVEMENT" if results['improvement'] > 0 else "↓ DECLINE" if results['improvement'] < 0 else "→ NO CHANGE"

            print(f"Score Change:     {results['improvement']:+.4f} ({improvement_pct:+.2f}%) {direction}")
            print(f"Grade Change:     {results['before_stats']['aggregated_grade']} → {results['after_stats']['aggregated_grade']}")

            # Para rate comparison
            para_rate_change = results['after_stats']['para_percentage'] - results['before_stats']['para_percentage']
            if abs(para_rate_change) > 0.1:  # Only show if >0.1% change
                para_direction = "↑" if para_rate_change > 0 else "↓"
                print(f"Para Rate Change: {results['before_stats']['para_percentage']:.1f}% → {results['after_stats']['para_percentage']:.1f}% ({para_direction}{abs(para_rate_change):.1f}%)")

            # Interpretation
            print("\nInterpretation:")
            if abs(results['improvement']) < 0.01:
                print("  ✓ No significant change in performance")
            elif results['improvement'] > 0.05:
                print("  ✓✓ SIGNIFICANT IMPROVEMENT - Configuration change appears beneficial")
            elif results['improvement'] > 0.02:
                print("  ✓ Moderate improvement - Configuration change likely beneficial")
            elif results['improvement'] > 0:
                print("  ≈ Slight improvement - More data may be needed")
            elif results['improvement'] > -0.02:
                print("  ≈ Slight decline - More data may be needed")
            elif results['improvement'] > -0.05:
                print("  ✗ Moderate decline - Configuration change may be detrimental")
            else:
                print("  ✗✗ SIGNIFICANT DECLINE - Consider reverting configuration change")
        else:
            print("Insufficient data for comparison")

        print("=" * 80)


def load_peers(peers_file: str) -> Dict[str, str]:
    """Load peer validators from INI-style config file

    Format:
        # Polkadot Validators
        IC01DOT = 15zH8tbFxyBgvkAdF3UWSfykAXADbS32vJuYRHTkZJ15Y4jd
        IC02DOT = 12Qq3fn9xnFZ37Ltcj6BH8NSpAQjEMp2oKnEALa7bbuguU4L

        # Kusama Validators
        IC01KSM = D5aAp1y8XfkrmtPqsGFZtCjJrPZqKrsG2ceSha846jy6RMU

    Args:
        peers_file: Path to peers configuration file

    Returns:
        Dict mapping peer names to addresses
    """
    peers = {}
    try:
        with open(peers_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                # Parse "NAME = ADDRESS" format
                if '=' in line:
                    name, address = line.split('=', 1)
                    peers[name.strip()] = address.strip()
        return peers
    except FileNotFoundError:
        print(f"Error: Peers file not found: {peers_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error loading peers file: {e}", file=sys.stderr)
        sys.exit(1)


def analyze_peer_comparison(analyzer: 'ValidatorPerformanceAnalyzer',
                           peers: Dict[str, str],
                           target_address: str,
                           change_session: int,
                           sessions_before: int,
                           sessions_after: Optional[int],
                           exclude_current: bool,
                           network: str) -> Dict:
    """Analyze performance for all peers and compare rankings

    Args:
        analyzer: ValidatorPerformanceAnalyzer instance
        peers: Dict mapping peer names to addresses
        target_address: The primary validator being analyzed
        change_session: Session when change was made
        sessions_before: Sessions to analyze before change
        sessions_after: Sessions to analyze after change (None = auto)
        exclude_current: Whether to exclude current session
        network: Network name (kusama/polkadot)

    Returns:
        Dict with peer comparison results
    """
    # Filter peers to only include validators from the target network
    # Polkadot addresses start with "1", Kusama addresses start with other letters
    filtered_peers = {}
    skipped_peers = []

    for name, address in peers.items():
        # Simple network detection: Polkadot addresses start with "1"
        is_polkadot = address.startswith('1')
        is_kusama = not is_polkadot

        if (network == 'polkadot' and is_polkadot) or (network == 'kusama' and is_kusama):
            filtered_peers[name] = address
        else:
            skipped_peers.append(f"{name} ({'Polkadot' if is_polkadot else 'Kusama'})")

    if skipped_peers:
        print(f"\nℹ️  Skipped {len(skipped_peers)} peer(s) from different network: {', '.join(skipped_peers)}", file=sys.stderr)

    if not filtered_peers:
        print(f"⚠️  No peers found for {network} network!", file=sys.stderr)
        return {
            'peers': {},
            'before_ranked': [],
            'after_ranked': [],
            'target_name': None,
            'target_before_rank': None,
            'target_after_rank': None,
            'network': network,
        }

    print(f"🔍 Analyzing {len(filtered_peers)} {network} peer validator(s)...", file=sys.stderr)

    peer_results = {}
    target_name = None

    for name, address in filtered_peers.items():
        # Check if this is the target validator
        if address == target_address or analyzer.convert_to_generic_ss58(address) == analyzer.convert_to_generic_ss58(target_address):
            target_name = name

        print(f"  Analyzing {name}...", file=sys.stderr)
        try:
            results = analyzer.analyze_sessions(
                address=address,
                change_session=change_session,
                sessions_before=sessions_before,
                sessions_after=sessions_after,
                exclude_current=exclude_current
            )
            peer_results[name] = {
                'address': address,
                'before_score': results['before_stats'].get('aggregated_score'),
                'after_score': results['after_stats'].get('aggregated_score'),
                'before_grade': results['before_stats'].get('aggregated_grade', '-'),
                'after_grade': results['after_stats'].get('aggregated_grade', '-'),
                'before_para_rate': results['before_stats'].get('para_rate', 0),
                'after_para_rate': results['after_stats'].get('para_rate', 0),
            }
        except Exception as e:
            print(f"    ⚠️  Failed to analyze {name}: {e}", file=sys.stderr)
            peer_results[name] = {
                'address': address,
                'before_score': None,
                'after_score': None,
                'before_grade': '-',
                'after_grade': '-',
                'before_para_rate': 0,
                'after_para_rate': 0,
                'error': str(e)
            }

    # Rank peers for before and after periods
    before_ranked = []
    after_ranked = []

    for name, data in peer_results.items():
        if data.get('before_score') is not None:
            before_ranked.append((name, data))
        if data.get('after_score') is not None:
            after_ranked.append((name, data))

    # Sort by score (descending)
    before_ranked.sort(key=lambda x: x[1]['before_score'], reverse=True)
    after_ranked.sort(key=lambda x: x[1]['after_score'], reverse=True)

    # Find target validator's ranks
    target_before_rank = None
    target_after_rank = None

    for rank, (name, _) in enumerate(before_ranked, 1):
        if name == target_name:
            target_before_rank = rank
            break

    for rank, (name, _) in enumerate(after_ranked, 1):
        if name == target_name:
            target_after_rank = rank
            break

    return {
        'peers': peer_results,
        'before_ranked': before_ranked,
        'after_ranked': after_ranked,
        'target_name': target_name,
        'target_before_rank': target_before_rank,
        'target_after_rank': target_after_rank,
        'network': network,
    }


def print_peer_comparison(comparison: Dict, before_sessions: str, after_sessions: str):
    """Print peer comparison results

    Args:
        comparison: Results from analyze_peer_comparison
        before_sessions: Description of before period (e.g., "Sessions 11800-11899")
        after_sessions: Description of after period (e.g., "Sessions 11901-12000")
    """
    target_name = comparison['target_name']
    before_ranked = comparison['before_ranked']
    after_ranked = comparison['after_ranked']
    target_before_rank = comparison['target_before_rank']
    target_after_rank = comparison['target_after_rank']

    print("\n" + "=" * 80)
    print("PEER COMPARISON (Your Validators)")
    print("=" * 80)

    # Before period
    print(f"\nBEFORE CHANGE ({before_sessions})")
    print("-" * 80)
    for rank, (name, data) in enumerate(before_ranked, 1):
        score = data['before_score']
        grade = data['before_grade']
        para_rate = data['before_para_rate']
        indicator = "← This validator" if name == target_name else ""
        rank_emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
        print(f"  {rank_emoji} #{rank}  {name:12s}  {score:.4f}  ({grade})  Para: {para_rate:5.1f}%  {indicator}")

    # After period
    print(f"\nAFTER CHANGE ({after_sessions})")
    print("-" * 80)
    for rank, (name, data) in enumerate(after_ranked, 1):
        score = data['after_score']
        grade = data['after_grade']
        para_rate = data['after_para_rate']

        # Find previous rank
        prev_rank = None
        for prev_r, (prev_name, _) in enumerate(before_ranked, 1):
            if prev_name == name:
                prev_rank = prev_r
                break

        # Determine rank change indicator
        rank_change = ""
        if prev_rank is not None:
            if rank < prev_rank:
                rank_change = f"↑ Was #{prev_rank}"
            elif rank > prev_rank:
                rank_change = f"↓ Was #{prev_rank}"

        indicator = f"← This validator {rank_change}".strip() if name == target_name else rank_change
        rank_emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
        print(f"  {rank_emoji} #{rank}  {name:12s}  {score:.4f}  ({grade})  Para: {para_rate:5.1f}%  {indicator}")

    # Insights
    if target_name and target_before_rank and target_after_rank:
        print("\nPEER INSIGHTS")
        print("-" * 80)

        # Rank movement
        if target_after_rank < target_before_rank:
            improvement = target_before_rank - target_after_rank
            print(f"  ✅ Moved from #{target_before_rank} to #{target_after_rank} among your validators (↑{improvement} position{'s' if improvement > 1 else ''})")
        elif target_after_rank > target_before_rank:
            decline = target_after_rank - target_before_rank
            print(f"  ⚠️  Moved from #{target_before_rank} to #{target_after_rank} among your validators (↓{decline} position{'s' if decline > 1 else ''})")
        else:
            print(f"  • Maintained position #{target_after_rank} among your validators")

        # Score vs best peer
        if target_after_rank == 1:
            # We're #1, compare to #2
            if len(after_ranked) > 1:
                second_score = after_ranked[1][1]['after_score']
                target_score = after_ranked[0][1]['after_score']
                diff = ((target_score - second_score) / second_score) * 100
                print(f"  • Now {diff:.2f}% ahead of your next best peer ({after_ranked[1][0]})")
            else:
                print(f"  • You're the only validator in this comparison")
        else:
            # Compare to #1
            best_name, best_data = after_ranked[0]
            target_score = None
            for name, data in after_ranked:
                if name == target_name:
                    target_score = data['after_score']
                    break

            if target_score:
                best_score = best_data['after_score']
                diff = ((target_score - best_score) / best_score) * 100
                print(f"  • Currently {abs(diff):.2f}% {'ahead of' if diff > 0 else 'behind'} your best peer ({best_name})")

        # Overall assessment
        if target_after_rank < target_before_rank:
            print(f"  • 🎯 Configuration change gave you a competitive edge among your fleet")
        elif target_after_rank == target_before_rank and target_after_rank == 1:
            print(f"  • 🏆 Maintained your lead position")
        elif target_after_rank == target_before_rank:
            print(f"  • Maintained relative position, all peers may have similar configurations")
        else:
            print(f"  • Consider investigating what improved performance on your other validators")

    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='Compare Turboflakes validator performance before and after configuration changes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare 10 sessions before/after session 51400
  %(prog)s JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ 51400

  # Compare 20 sessions before, 15 sessions after
  %(prog)s JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ 51400 -b 20 -a 15

  # Auto-calculate sessions from last change to current change
  %(prog)s JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ 51973 --last-change 51800

  # Add a comment to the report
  %(prog)s JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ 51973 -c "interrupt coalescing rx_usecs=50"

  # Polkadot validator with detailed session output
  %(prog)s 16fbkDCMrAo1uyC52NyA8Y2dETnYVpCofSoj3QEE2WUNnkLk 12345 -n polkadot -d

  # JSON output for further processing
  %(prog)s JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ 51400 --json
        """
    )

    parser.add_argument(
        'address',
        help='Validator address'
    )
    parser.add_argument(
        'change_session',
        type=int,
        help='Session number when configuration change was made'
    )
    parser.add_argument(
        '-b', '--before',
        type=int,
        default=10,
        help='Number of sessions before change to include (default: 10)'
    )
    parser.add_argument(
        '-a', '--after',
        type=int,
        default=None,
        help='Number of sessions after change to include (default: auto-detect to current-1)'
    )
    parser.add_argument(
        '--last-change',
        type=int,
        metavar='SESSION',
        help='Session of previous configuration change (auto-calculates -b from last change+1 to current change-1)'
    )
    parser.add_argument(
        '-c', '--comment',
        type=str,
        help='Optional comment to display in the report (e.g., "interrupt coalescing rx_usecs=50")'
    )
    parser.add_argument(
        '-n', '--network',
        choices=['kusama', 'polkadot'],
        default='kusama',
        help='Network (default: kusama)'
    )
    parser.add_argument(
        '-d', '--detailed',
        action='store_true',
        help='Show detailed session-by-session data'
    )
    parser.add_argument(
        '--exclude-latest',
        action='store_true',
        help='Exclude the latest returned session (use if you suspect incomplete data)'
    )
    parser.add_argument(
        '--network-normalized',
        action='store_true',
        help='Use network-wide normalization for backing points (matches Turboflakes exactly, slower)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    parser.add_argument(
        '--peers',
        nargs='?',
        const='peers.ini',
        metavar='FILE',
        help='Compare against peer validators from config file (default: peers.ini)'
    )

    args = parser.parse_args()

    # Resolve peer name to address if peers file is specified or exists
    validator_address = args.address
    peers = None

    # Try to load peers if --peers is specified or peers.ini exists
    if args.peers:
        peers = load_peers(args.peers)
    elif Path('peers.ini').exists():
        # Auto-load peers.ini if it exists (for convenience)
        try:
            peers = load_peers('peers.ini')
        except:
            pass  # Silently ignore if auto-load fails

    # Check if address is actually a peer name
    if peers and validator_address in peers:
        actual_address = peers[validator_address]
        print(f"Resolved peer name '{validator_address}' → {actual_address}", file=sys.stderr)
        validator_address = actual_address

    # Calculate sessions_before from --last-change if provided
    sessions_before = args.before
    if args.last_change is not None:
        if args.last_change >= args.change_session:
            print(f"Error: --last-change ({args.last_change}) must be before change_session ({args.change_session})", file=sys.stderr)
            sys.exit(1)
        # Calculate: from (last_change + 1) to (change_session - 1)
        sessions_before = args.change_session - args.last_change - 1
        if sessions_before < 1:
            print(f"Error: Only {sessions_before} session(s) between last change and current change (need at least 1)", file=sys.stderr)
            sys.exit(1)
        print(f"Auto-calculated -b {sessions_before} from --last-change {args.last_change} (sessions {args.last_change + 1} to {args.change_session - 1})", file=sys.stderr)

    # Initialize analyzer
    analyzer = ValidatorPerformanceAnalyzer(
        network=args.network,
        use_network_normalization=args.network_normalized
    )

    # Analyze performance
    results = analyzer.analyze_sessions(
        address=validator_address,
        change_session=args.change_session,
        sessions_before=sessions_before,
        sessions_after=args.after,
        exclude_current=args.exclude_latest
    )

    # Add comment to results if provided
    if args.comment:
        results['comment'] = args.comment

    # Output results
    if args.json:
        # Convert to JSON-serializable format
        output = {
            'validator': results['validator'],
            'network': results['network'],
            'change_session': results['change_session'],
            'current_session': results['current_session'],
            'excluded_current': results['excluded_current'],
            'before_sessions': results['before_sessions'],
            'after_sessions': results['after_sessions'],
            'before_stats': results['before_stats'],
            'after_stats': results['after_stats'],
            'improvement': results['improvement'],
            'overall_grade': results['overall_grade'],
            'overall_auth_inclusion': results['overall_auth_inclusion'],
            'overall_para_inclusion': results['overall_para_inclusion'],
        }
        print(json.dumps(output, indent=2))
    else:
        analyzer.print_analysis(results, detailed=args.detailed)

        # Peer comparison if requested
        if args.peers:
            if not peers:
                peers = load_peers(args.peers)
            if peers:
                peer_comparison = analyze_peer_comparison(
                    analyzer=analyzer,
                    peers=peers,
                    target_address=validator_address,
                    change_session=args.change_session,
                    sessions_before=sessions_before,
                    sessions_after=args.after,
                    exclude_current=args.exclude_latest,
                    network=args.network
                )

                # Format session ranges for display
                before_start = args.change_session - sessions_before
                before_end = args.change_session - 1
                after_start = args.change_session + 5  # Buffer
                after_end = results['current_session']
                if results['excluded_current']:
                    after_end -= 1

                before_sessions_str = f"Sessions {before_start}-{before_end}: {sessions_before} sessions"
                if args.after:
                    after_sessions_str = f"Sessions {after_start}-{after_end}: {args.after} sessions"
                else:
                    actual_after = after_end - after_start + 1
                    after_sessions_str = f"Sessions {after_start}-{after_end}: {actual_after} sessions"

                print_peer_comparison(peer_comparison, before_sessions_str, after_sessions_str)


if __name__ == '__main__':
    main()
