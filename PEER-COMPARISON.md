# Peer Comparison Feature

## Overview

The peer comparison feature allows you to compare performance rankings among your own validators. This helps you identify which of your nodes is performing best and how configuration changes affect their relative positions.

## Setup

1. Create a `peers.ini` file in the turboflakes directory
2. Add your validators in the format: `NAME = ADDRESS`

### Example `peers.ini`

```ini
# Polkadot Validators
IC01DOT = 15i7KZA28F82jCfHubQ22RptEJypTZsbnSSobjU9KUnxUvdW
IC02DOT = 16JwE96t9MMvWQHuyHntqVyo6Ks97XCK1kHvWumGNLGVJg5p

# Kusama Validators
IC01KSM = HbhEnjBuXX4zRjxQRXqUxLMEy4oftmTK4GdTTkgEhdY8bdj
IC02KSM = HS4wfui3HrAG3K7UUFsUK4PVd1GXtqRQUdT5vH18gyTe88D
IC03KSM = Em4HYqVrWX3uCvrC8NWoabfKpV9z8stdRKkXYXcZdWGxdXT
IC04KSM = EkMhcssLmZnMS2WtBXhsBQwPwMm9KQiwom3u7JxNJmcgSf4
IC05KSM = FrCnkchTNhzTu6qKCZnk4TeYaEGQ1tL8GPVPwcnajd7q5LP
```

**Note:** `peers.ini` is in `.gitignore` to protect your validator addresses.

**Network Filtering:** The script automatically filters peers by network. When analyzing a Kusama validator, it only compares against other Kusama validators (and vice versa for Polkadot). You'll see a message like:

```
ℹ️  Skipped 2 peer(s) from different network: IC01DOT (Polkadot), IC02DOT (Polkadot)
🔍 Analyzing 5 kusama peer validator(s)...
```

## Usage

The script now supports **peer name resolution** - you can use short names instead of full addresses!

```bash
# Use peer name directly (requires peers.ini)
./compare-performance.py IC01KSM 51900 -b 100 --network-normalized --peers

# Peer names work without --peers if peers.ini exists
./compare-performance.py IC02KSM 51900 -b 100 --network-normalized

# You can still use full addresses
./compare-performance.py HS4wfui3HrAG3K7UUFsUK4PVd1GXtqRQUdT5vH18gyTe88D 51900 --network-normalized --peers

# Specify a custom peers file
./compare-performance.py IC01KSM 51900 -b 100 --network-normalized --peers my-validators.ini
```

**How it works:**

1. Script checks if `peers.ini` exists (or loads the file specified with `--peers`)
2. If the address argument matches a peer name (e.g., `IC02KSM`), it looks up the actual address
3. Displays: `Resolved peer name 'IC02KSM' → HS4wfui3HrAG3K7UUFsUK4PVd1GXtqRQUdT5vH18gyTe88D`
4. Uses the resolved address for analysis

## Output

The peer comparison appears after the main analysis and shows:

```
================================================================================
PEER COMPARISON (Your Validators)
================================================================================

BEFORE CHANGE (Sessions 51800-51899: 100 sessions)
--------------------------------------------------------------------------------
  🥇 #1  IC02KSM      0.9945  (A+)  Para:  72.0%
  🥈 #2  IC01KSM      0.9932  (A+)  Para:  70.0%  ← This validator
  🥉 #3  IC03KSM      0.9920  (A+)  Para:  71.0%
     #4  IC04KSM      0.9910  (A+)  Para:  69.0%
     #5  IC05KSM      0.9905  (A+)  Para:  70.0%

AFTER CHANGE (Sessions 51901-52000: 100 sessions)
--------------------------------------------------------------------------------
  🥇 #1  IC01KSM      0.9951  (A+)  Para:  77.0%  ← This validator ↑ Was #2
  🥈 #2  IC02KSM      0.9940  (A+)  Para:  75.0%  ↓ Was #1
  🥉 #3  IC03KSM      0.9925  (A+)  Para:  74.0%
     #4  IC04KSM      0.9915  (A+)  Para:  73.0%
     #5  IC05KSM      0.9908  (A+)  Para:  72.0%

PEER INSIGHTS
--------------------------------------------------------------------------------
  ✅ Moved from #2 to #1 among your validators (↑1 position)
  • Now 0.11% ahead of your next best peer (IC02KSM)
  • 🎯 Configuration change gave you a competitive edge among your fleet
================================================================================
```

## Features

### Rankings

- **Before/After Rankings:** See how your validator ranks before and after the configuration change
- **Rank Movement:** Visual indicators (↑/↓) show position changes
- **Medals:** Top 3 validators get 🥇🥈🥉 indicators

### Insights

The tool automatically provides:

- Rank movement analysis
- Performance gap vs your best peer
- Overall assessment of the configuration change impact

### Error Handling

- Validators that fail to analyze show error messages but don't block the comparison
- The script automatically filters out validators with missing data
- Only validators with complete data appear in rankings

## Use Cases

### 1. Configuration Testing

Test a change on one validator and compare against your other nodes:

```bash
# Changed IC01KSM config at session 51900, compare against other 4 Kusama nodes
./compare-performance.py IC01KSM 51900 -b 100 -a 50 --network-normalized --peers
```

### 2. Hardware Comparison

Compare performance between different hardware configurations:

```bash
# peers.ini contains validators on different hardware
# Use peer name for convenience
./compare-performance.py SERVER_A 51900 --network-normalized --peers
```

### 3. Network Location Testing

Compare validators in different data centers or geographic locations.

### 4. Gradual Rollout Verification

After changing config on all nodes, verify they all improved consistently:

- Each node should show similar score improvements
- Relative rankings should stay roughly the same
- If one node improved much more/less, investigate why

## Tips

1. **Use peer names:** Much easier than typing long addresses! `./compare-performance.py IC01KSM ...` vs `./compare-performance.py HS4wfui3HrAG3K7UUFsUK4PVd1GXtqRQUdT5vH18gyTe88D ...`
2. **Mix networks in peers.ini:** You can have both Polkadot and Kusama validators in one file - the script automatically filters by network
3. **Use network-normalized mode:** `--network-normalized` provides the most accurate scores for comparison
4. **Sufficient data:** Use at least 50-100 sessions for reliable comparisons
5. **Name consistently:** Use clear, descriptive names (IC01KSM, IC02KSM) for easy identification
6. **Cache benefits:** Once peers are analyzed, subsequent analyses use cached data for speed
7. **Auto-loads peers.ini:** If `peers.ini` exists, peer names work even without `--peers` flag

## Technical Details

- Analyzes all peers using the same session ranges
- Uses aggregated scoring (matches Turboflakes methodology)
- Caches individual validator data for efficiency
- Ranks by aggregated score (not median or mean)
- Handles auth-only sessions correctly for each validator

## Privacy

The `peers.ini` file is automatically ignored by git to protect your validator addresses. Share the example file (`peers.ini.example`) but never commit your actual `peers.ini` file.
