# Network-Wide Normalization Feature

## Overview

The `--network-normalized` flag enables network-wide normalization of backing points, matching Turboflakes dashboard scores exactly and providing validator rankings.

## Usage

```bash
# Standard mode (fast, single-validator normalization)
./compare-performance.py VALIDATOR 51400 -b 10 -a 10

# Network-normalized mode (slower, matches Turboflakes exactly)
./compare-performance.py VALIDATOR 51400 -b 10 -a 10 --network-normalized -d
```

## What It Does

### Standard Mode

- Normalizes backing points against YOUR validator's min/max in the query range
- Fast (~1 second)
- Scores typically +1-3% higher than Turboflakes
- Perfect for before/after comparisons

### Network-Normalized Mode

- Normalizes backing points against ALL validators in the network for each session
- Calculates scores for all ~600 validators per session
- Provides ranking: "#90 of 395 paravalidators (Top 23%)"
- Shows vs network average: "+12% vs avg"
- Matches Turboflakes scores exactly
- Slower (~7-10 seconds for 20 sessions with caching)

## Performance

**First run (no cache):**

```
Fetching network-wide data for 10 sessions...
  ✓ Session 51503 (540 paravalidators)
  ✓ Session 51504 (540 paravalidators)
  ...
Time: ~7-10 seconds
```

**Subsequent runs (with cache):**

```
Time: ~2 seconds (cache reuse)
```

## Output Example

### With Ranking (Network-Normalized):

```
Session 51503: 0.9996 (A+) [PARA]
  Rank by Score: #1 of 540 paravalidators (Top 1%, +12% vs avg)
  Backing Points: 3420 (network: 40-3420, avg: 1723)
```

### Standard (Non-Network-Normalized Mode):

```
Session 51503: 0.9996 (A+) [PARA]
  MVR: 0.000 (0/164) = 0.5000
  BAR: 0.997 = 0.2492
  Backing Points: 3420 pts = 0.1800
```

## Cache System

**Location:** `turboflakes/.cache/`

**Structure:**

```
.cache/
  kusama_session_51503.json   (132 KB)
  kusama_session_51504.json
  polkadot_session_11796.json
```

**Each file contains:**

- All validator scores for that session (ranked)
- Network backing points statistics (min/max/avg/median)
- Timestamp

**Benefits:**

- Instant reuse for repeated analyses
- Share network data across different validators
- Git-ignored (won't bloat your repo)

## Terminology

**Backing Points:**

- Pure backing points: `pt - (ab × 20)` where `ab` = authored blocks
- Excludes authored block bonus (20 points per block)
- This is what Turboflakes normalizes and displays as "Avg Backing Points"
- Example: If pt=3480 and ab=3, backing points = 3480 - 60 = 3420

**Rank by Score:**

- Ranking based on FULL Turboflakes score (not just points)
- Score = MVR*0.50 + BAR*0.25 + Normalized_Points*0.18 + PV*0.07
- Example: "#1 of 540 paravalidators"

**vs Network Average:**

- Your score compared to network mean
- Example: "+12% vs avg" = 12% above network average score

## API Limitations

**Turboflakes API returns max ~600 validators** per network query.

**Coverage:**

- Kusama: ✅ All ~700 paravalidators per session
- Polkadot: ✅ All ~600 paravalidators per session

**Auth-Only Session Detection:**
When your validator is selected as authority but not as paravalidator:

1. ℹ️ Clear informative message: "Session X: is_para: false, no paravalidator score. Auth-only, no para work"
2. ✅ Session excluded from para statistics (matching Turboflakes behavior)
3. ✅ Session counted in overall activity tracking

**Output Format:**

When validator is active as paravalidator:

```
Rank by Score: #13 of 700 paravalidators (Top 98%, +1% vs avg)
```

When validator is auth-only (not paravalidator):

```
ℹ️  Session 51855: is_para: false, no paravalidator score. Auth-only, no para work
```

## When to Use Network-Normalized Mode

### Use Network-Normalized When:

✅ You want to match Turboflakes scores exactly
✅ You want to see your ranking vs other validators
✅ You want network-wide context (min/max/avg)
✅ Analyzing long time periods (months apart)
✅ Network-wide performance shifts are a concern
✅ Validating script accuracy against dashboard
✅ **RECOMMENDED:** This mode provides the most accurate and comprehensive analysis

### Use Standard Mode When:

✅ Quick iterations during testing
✅ Recent configuration changes (days/weeks)
✅ Relative comparison is enough
✅ Faster results needed

## Real-World Example

**Test Run:**

```bash
$ ./compare-performance.py 5DLK5dUsunrjdbnJudWyfD3BHa7s3dn8j857bC28WVvUPDka \
  51500 -b 2 -a 3 --network-normalized -d

Fetching network-wide data for 7 sessions...
  ✓ Session 51498 (550 paravalidators)
  ...
Network data fetch complete: 7/7 sessions

BEFORE CHANGE (Sessions 51498-51499: 2 sessions total, 2 paravalidator)
Mean Score:       0.9461 (A-)

Session 51498: 0.9793 (A) [PARA]
  Rank by Score: #73 of 550 paravalidators (Top 14%, +10% vs avg)
  Backing Points: 3140 (network: 40-3400, avg: 1724)

AFTER CHANGE (Sessions 51501-51503: 3 sessions total, 2 paravalidator)
Mean Score:       0.9145 (A-)

Session 51503: 0.9996 (A+) [PARA]
  Rank by Score: #1 of 540 paravalidators (Top 1%, +12% vs avg)  ← #1!
  Backing Points: 3420 (network: 40-3420, avg: 1723)
```

## Technical Details

**What Gets Normalized:**

- Only the **backing points** component (18% of total score)
- MVR (50%), BAR (25%), and PV Ratio (7%) remain the same

**Normalization Formula:**

```
Standard Mode:
  PTS_normalized = (your_points - your_min) / (your_max - your_min)

Network Mode:
  PTS_normalized = (your_points - network_min) / (network_max - network_min)
```

**Why Scores Match Turboflakes:**

```rust
// Turboflakes source (polkadot.rs):
let avg_para_points: Vec<u32> = validators
    .iter()
    .map(|v| v.avg_para_points)    // ← ALL validators
    .collect();
let max = avg_para_points.iter().max()  // ← Network-wide
let min = avg_para_points.iter().min()  // ← Network-wide
```

We now do the same!

## Cleanup

**Remove cache files:**

```bash
rm -rf turboflakes/.cache/
```

**Remove specific network:**

```bash
rm turboflakes/.cache/polkadot_*.json
```

**Cache is safe to delete** - files regenerate automatically on next run.

## Performance Optimization

**Parallel Fetching:**

- Uses ThreadPoolExecutor with 5 workers
- 20 sessions: 4 batches × ~2 seconds = ~8 seconds total
- Much faster than sequential (which would be ~35 seconds)

**Smart Caching:**

- Checks cache before API call
- Validates cached data (correct session)
- Handles corrupted cache gracefully

## Compatibility

✅ **Works with both networks:**

- Kusama: Full support, all validators typically included
- Polkadot: Full support for all ~600 active paravalidators per session

✅ **Backward compatible:**

- Standard mode unchanged
- All existing scripts/commands work as before
- Network mode is purely additive

✅ **JSON output:**

- Rankings included in JSON when available
- `--json` flag works with `--network-normalized`

## Date

Feature implemented: October 13, 2025
