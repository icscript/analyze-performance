# Turboflakes Validator Performance Analysis

Tools for analyzing Polkadot/Kusama validator performance using the Turboflakes API.

## Project Status

✅ **COMPLETE & VALIDATED** - Exact score matching with Turboflakes dashboard
📊 See [PROJECT-STATUS.md](./PROJECT-STATUS.md) for complete validation results and project summary

## Overview

This directory contains scripts to help evaluate the impact of configuration changes on validator performance by comparing [Turboflakes ONE-T scores](https://github.com/turboflakes/one-t/blob/main/SCORES.md) before and after changes.

## Quick Links

- 📖 **This file (README.md)** - Main documentation and usage guide
- 📊 **PROJECT-STATUS.md** - **Project completion summary & validation results**
- 🔑 **TURBOFLAKES-API-NOTES.md** - **IMPORTANT**: API documentation including SS58 address format issue
- 🎯 **SS58-ADDRESS-DISCOVERY.md** - How we solved the "missing validators" mystery
- 🌐 **NETWORK-NORMALIZATION.md** - Network-wide normalization feature (matches Turboflakes exactly, with rankings!)
- ✅ **VALIDATION-GUIDE.md** - How to verify scores against Turboflakes dashboard
- 📝 **AUTH-SESSION-EXCLUSION-UPDATE.md** - Changelog for AUTH session exclusion feature
- 🔍 **SESSION-DATA-FINDINGS.md** - Investigation into session data completeness

## Installation

```bash
# Install Python dependencies
pip3 install -r requirements.txt
```

## Compare Performance Script

`compare-performance.py` - Compare validator scores before and after a configuration change.

### Features

- ✅ Uses the official **Turboflakes ONE-T Performance Score formula**
- ✅ **Network-wide normalization mode** (`--network-normalized`) - matches Turboflakes exactly, shows rankings!
  - **🚀 UNLIMITED SESSION ANALYSIS** - No 192-session API limit! Analyze 200+, 300+, or more sessions
  - Uses per-session queries with file-based caching (bypasses bulk `/grade` endpoint limit)
- ✅ **Handles inactive paravalidator sessions** - labels `[PARA-INACTIVE]` when validator selected but had no work
- ✅ Calculates scores per session with component breakdown
- ✅ **Excludes AUTH-only sessions from statistics** (matching Turboflakes behavior)
- ✅ **Clear auth-only session detection** - informative messages when validator not selected as paravalidator
- ✅ Shows paravalidator rate (% of sessions as paravalidator)
- ✅ Shows mean, median, and range statistics
- ✅ Provides improvement percentage and interpretation
- ✅ Supports both Kusama and Polkadot validators
- ✅ Detailed mode shows score components (MVR, BAR, PTS, PV ratio) or rankings
- ✅ **Smart caching system** for fast repeated analyses (eliminates redundant API calls)
- ✅ **Address conversion** - automatically handles Polkadot/Kusama to generic SS58 format
- ✅ JSON output for further processing
- ✅ **Auto-calculate `-b` from `--last-change`** session number

### Turboflakes Score Formula

The script uses the official formula:

```
Performance Score = (1 - MVR) * 0.50 + BAR * 0.25 +
                    ((avg_pts - min_pts) / (max_pts - min_pts)) * 0.18 +
                    (pv_sessions / total_sessions) * 0.07
```

**Components:**

- **MVR** (50% weight): Missed Votes Ratio - percentage of votes missed
- **BAR** (25% weight): Bitfield Availability Ratio - parachain block availability
- **PTS** (18% weight): Normalized paravalidator points
- **PV Ratio** (7% weight): Paravalidator session participation

**Score Range:** 0.0 to 1.0 (higher is better)

**Grade Mapping:**

- A+ = 0.99+
- A = 0.95+
- A- = 0.90+
- B+ = 0.85+
- B = 0.80+
- And so on...

### Usage

```bash
# Basic usage - automatically analyzes from change to current session
# (Excludes current open session by default)
./compare-performance.py VALIDATOR_ADDRESS CHANGE_SESSION
# Compare 10 sessions before vs all sessions after

# Specify number of sessions before, auto-detect after
./compare-performance.py VALIDATOR_ADDRESS CHANGE_SESSION -b 20

# Specify exact number of sessions before AND after
./compare-performance.py VALIDATOR_ADDRESS CHANGE_SESSION -b 20 -a 15

# Show detailed session-by-session breakdown with score components
./compare-performance.py VALIDATOR_ADDRESS CHANGE_SESSION -d

# Polkadot validator
./compare-performance.py VALIDATOR_ADDRESS CHANGE_SESSION -n polkadot

# Auto-calculate sessions from last change (NEW!)
# Analyzes from session AFTER last change to session BEFORE current change
./compare-performance.py VALIDATOR_ADDRESS 51973 --last-change 51800
# This auto-calculates -b 172 (sessions 51801-51972)
# Note: 192-session API limit ONLY applies to regular mode (not --network-normalized)
# Network-normalized mode has NO LIMIT - analyze 200+, 300+, or more sessions!

# Add a comment/note to the report (NEW!)
./compare-performance.py VALIDATOR_ADDRESS 51973 -c "interrupt coalescing rx_usecs=50"

# Network-wide normalization - matches Turboflakes exactly, shows rankings!
./compare-performance.py VALIDATOR_ADDRESS CHANGE_SESSION --network-normalized -d

# JSON output for automation
./compare-performance.py VALIDATOR_ADDRESS CHANGE_SESSION --json

# Exclude the latest session (optional - use if you suspect incomplete data)
./compare-performance.py VALIDATOR_ADDRESS CHANGE_SESSION --exclude-latest
# is this excluding latest complete/closed session

# Technique for large session ranges:
# 1. Break into chunks:
# Analyze 300 sessions in two runs
./compare-performance.py VALIDATOR 51700 -b 100 -a 0
./compare-performance.py VALIDATOR 51800 -b 100 -a 0
./compare-performance.py VALIDATOR 51900 -b 100 -a 0
# 2. Use network-normalized mode with caching:
# First run caches network data
./compare-performance.py VALIDATOR 51750 -b 50 -a 50 --network-normalized
# Second run reuses cache
./compare-performance.py VALIDATOR 51650 -b 50 -a 50 --network-normalized

```

### Automatic Session Detection

**NEW FEATURE:** The script now automatically detects the latest session and fetches all available data from your change to now!

```bash
# Simple: just specify when you made the change
./compare-performance.py JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ 51400

# It will:
# 1. Query the API to find latest session (e.g., 51468)
# 2. Include all returned sessions (Turboflakes returns finalized data)
# 3. Fetch all sessions from 51400 to 51468
# 4. Compare 10 sessions before vs all sessions after
```

**Output shows:**

```
Change Session:   51400
Latest Session:   51468
AFTER CHANGE (68 sessions)  ← All available sessions!
```

**About session data:** Turboflakes returns finalized session data. Some sessions may have lower points due to paravalidation group assignments and chain activity - this is normal variation, not incomplete data. The API typically has a short delay (minutes) before very recent sessions appear.

### Examples

**Compare Kusama validator performance:**

```bash
./compare-performance.py JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ 51400 -b 10 -a 10
```

**Detailed analysis with component breakdown:**

```bash
./compare-performance.py JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ 51400 -b 5 -a 5 -d
```

**Output:**

```
================================================================================
VALIDATOR PERFORMANCE ANALYSIS
================================================================================
Network:          KUSAMA
Validator:        JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ
Change Session:   51460
Overall Grade:    A+
Auth Inclusion:   100.00%
Para Inclusion:   50.00%

--------------------------------------------------------------------------------
BEFORE CHANGE (Sessions 51455-51459: 5 sessions total, 4 paravalidator)
--------------------------------------------------------------------------------
Para Rate:        80.0%
Mean Score:       0.8598 (B+)
Median Score:     0.8598
Range:            0.7500 - 0.9696
Note:             1 AUTH-only session(s) excluded from statistics

Session Details:
  (Score = MVR*0.50 + BAR*0.25 + PTS*0.18 + PV*0.07)
  Session  51458: 0.9696 (A) [PARA]
    MVR: 0.000 (0/136) = 0.5000
    BAR: 0.998 = 0.2496
    PTS: 2800 pts = 0.1500
    PV:  = 0.0700

--------------------------------------------------------------------------------
AFTER CHANGE (Sessions 51461-51465: 5 sessions total, 5 paravalidator)
--------------------------------------------------------------------------------
Para Rate:        100.0%
Mean Score:       0.8696 (B+)
Median Score:     0.8196
Range:            0.7500 - 0.9992

--------------------------------------------------------------------------------
COMPARISON
--------------------------------------------------------------------------------
Score Change:     +0.0099 (+0.99%) ↑ IMPROVEMENT
Grade Change:     B+ → B+

Interpretation:
  ✓ No significant change in performance
```

### Workflow for Evaluating Configuration Changes

1. **Note the session** when you make a configuration change
2. **Wait for sufficient data** (typically 10-20 sessions after the change)
3. **Run the comparison** with equal sessions before/after:
   ```bash
   ./compare-performance.py VALIDATOR_ADDRESS CHANGE_SESSION -b 10 -a 10 -d
   ```
4. **Interpret the results:**
   - **+5% or more**: Significant improvement ✓✓
   - **+2% to +5%**: Moderate improvement ✓
   - **-2% to +2%**: No significant change ≈
   - **-2% to -5%**: Moderate decline ✗
   - **-5% or less**: Significant decline ✗✗

### Finding Session Numbers

You can find current session numbers from:

1. **Polkadot.js Apps**: https://polkadot.js.org/apps/#/explorer
2. **Subscan**: https://kusama.subscan.io/ or https://polkadot.subscan.io/
3. **Your node logs**: Look for session change events
4. **Turboflakes API** directly:
   ```bash
   curl -s "https://kusama-onet-api.turboflakes.io/api/v1/validators/YOUR_ADDRESS/grade?number_last_sessions=1" | jq '.sessions[0]'
   ```

### Understanding the Metrics

**Authority-only (AUTH) sessions:**

- No paravalidation duties - validator was in active set but not selected for paravalidation
- These sessions are **excluded from score statistics** (matching Turboflakes dashboard behavior)
- Still shown in detailed output for transparency, marked as [AUTH]
- Common during rotation periods when validator group isn't assigned to paravalidation

**Paravalidator (PARA) sessions:**

- Full scoring applies using the Turboflakes formula
- **Only these sessions count toward your mean/median/range statistics**
- MVR: Keep this at 0.0 (no missed votes)
- BAR: Aim for >0.99 (high availability)
- PTS: Higher is better (depends on workload assigned to your validator group)

**Para Rate:**

- Shows what percentage of your sessions included paravalidation duties
- Example: "Para Rate: 66.7%" means 2 out of 3 sessions were paravalidator
- A drop in para rate doesn't reflect performance, just selection randomness
- Tracked separately so you can distinguish performance changes from selection changes

**What impacts each component:**

- **MVR**: Network latency, CPU performance, peer connectivity
- **BAR**: Block production timing, attestation speed
- **PTS**: Parachain validation speed, backing efficiency
- **PV Ratio**: Just tracks para vs auth-only sessions

### Limitations and Score Differences

**Point normalization (PTS component):**

- The PTS component (18% weight) normalizes against the min/max points **in your query dataset** (single validator)
- Turboflakes normalizes against **all validators in the network** for that time period (confirmed from [source code](https://github.com/turboflakes/one-t/blob/main/src/polkadot.rs))
- This causes our scores to be slightly higher (typically +0.01 to +0.03) than Turboflakes dashboard
- **This doesn't affect before/after comparison** since we use consistent normalization for both periods
- For more accurate absolute scores, use larger session ranges (20+)

**Why we normalize differently:**

- The Turboflakes API doesn't provide network-wide validator data
- For your use case (comparing your validator against itself), using your own historical range as baseline is actually more meaningful
- The relative changes (what you care about) are accurate

**Single validator view:**

- This compares your validator against itself over time, not against other validators
- Perfect for evaluating configuration changes, but not for network-wide ranking

**Session selection:**

- Ensure your "before" period doesn't include other configuration changes
- Use equal session counts before/after for fair comparison (e.g., `-b 10 -a 10`)

**Para selection randomness:**

- Validators are randomly selected for paravalidation duties
- Low para rate in one period vs another doesn't indicate a problem
- The script tracks and reports para rate changes separately from performance changes

### Troubleshooting

**"No session data available"**

- Verify the validator address is correct
- Check that the validator was active in the requested sessions
- Try increasing the session range

**Scores seem wrong**

- Verify you're using the correct network (`-n kusama` or `-n polkadot`)
- Check that the change session number is accurate
- Review detailed output (`-d`) to see component breakdown

## API References

- **Turboflakes API Documentation**: https://turboflakes.io/
- **ONE-T Score Formula**: https://github.com/turboflakes/one-t/blob/main/SCORES.md
- **Kusama API**: https://kusama-onet-api.turboflakes.io
- **Polkadot API**: https://polkadot-onet-api.turboflakes.io

## Future Enhancements

Potential improvements:

- Compare multiple validators simultaneously
  --- Compare change in ranking amongst our own validator (rank could be high score order)
- Fetch network-wide min/max for accurate PTS normalization
- Track changes over time (database storage)
- Automated alerts when scores drop
- Grafana dashboard integration
- Export to CSV for spreadsheet analysis
