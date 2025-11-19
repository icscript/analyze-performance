# Validation Guide: Verifying Script Accuracy

## How to Validate the Script Against Turboflakes

### Understanding What Turboflakes Shows

**Turboflakes Dashboard/API provides:**

- **Aggregate grade** over N sessions (e.g., "A+", "A", "B+")
- **Authority inclusion** (0.0-1.0)
- **Para authority inclusion** (0.0-1.0)
- **Total votes** (summed across all sessions)

**Our script provides:**

- **Per-session scores** (0.0-1.0 using ONE-T formula)
- **Statistical analysis** (mean, median, range)
- **Before/after comparison**
- **Component breakdown** (MVR, BAR, PTS, PV ratio)

### Validation Method 1: Grade Consistency Check

Compare the overall grade range:

```bash
# Get Turboflakes grade
curl -s "https://kusama-onet-api.turboflakes.io/api/v1/validators/YOUR_ADDRESS/grade?number_last_sessions=10" | jq '.grade'

# Compare with script's mean score
./compare-performance.py YOUR_ADDRESS CHANGE_SESSION -b 5 -a 5
```

**Grade to Score Mapping:**

- A+ = 0.99+
- A = 0.95-0.99
- A- = 0.90-0.95
- B+ = 0.85-0.90
- B = 0.80-0.85

**Example:**

- Turboflakes shows: **"A"**
- Script mean score: **0.96** (A grade) ✓ **Match!**

### Validation Method 2: Component Verification

Verify the raw data our script uses:

```bash
# Run with detailed output
./compare-performance.py YOUR_ADDRESS CHANGE_SESSION -b 2 -a 2 -d
```

**Output shows:**

```
Session 51462: 0.9992 (A+) [PARA]
  MVR: 0.000 (0/164) = 0.5000
  BAR: 0.997 = 0.2492
  PTS: 3320 pts = 0.1800
  PV:  = 0.0700
```

**Verify manually:**

```bash
curl -s "https://kusama-onet-api.turboflakes.io/api/v1/validators/YOUR_ADDRESS/grade?number_last_sessions=5&show_summary=true" | jq '.sessions_data[] | select(.session == 51462)'
```

**Check:**

- ✓ Explicit votes (ev)
- ✓ Implicit votes (iv)
- ✓ Missed votes (mv)
- ✓ Bitfields available (ba)
- ✓ Bitfields unavailable (bu)
- ✓ Para points (pt)

### Validation Method 3: Formula Verification

Our formula (from [Turboflakes ONE-T](https://github.com/turboflakes/one-t/blob/main/SCORES.md)):

```
Score = (1 - MVR) × 0.50 + BAR × 0.25 + PTS_normalized × 0.18 + PV_ratio × 0.07
```

**Example calculation (Session 51462):**

```
Votes: 147 explicit + 17 implicit + 0 missed = 164 total
MVR: 0/164 = 0.0000
MVR Component: (1 - 0.0000) × 0.50 = 0.5000 ✓

Bitfields: 590 available + 2 unavailable = 592 total
BAR: 590/592 = 0.9966
BAR Component: 0.9966 × 0.25 = 0.2492 ✓

PTS: 3320 (normalized to 0.1800 based on dataset) ✓
PV Ratio: Paravalidator session = 0.0700 ✓

Total: 0.5000 + 0.2492 + 0.1800 + 0.0700 = 0.9992 ✓
Script shows: 0.9992 ✓✓ MATCH!
```

### Validation Method 4: Authority/Para Inclusion

Compare inclusion rates:

```bash
# Get Turboflakes inclusion rates
curl -s "https://kusama-onet-api.turboflakes.io/api/v1/validators/YOUR_ADDRESS/grade?number_last_sessions=20" | jq '{authority_inclusion, para_authority_inclusion}'

# Script shows:
./compare-performance.py YOUR_ADDRESS CHANGE_SESSION
```

**Output:**

```
Auth Inclusion:   100.00%
Para Inclusion:   50.00%
```

Should roughly match Turboflakes over the same period.

## Common Discrepancies (and Why They're Normal)

### 1. Grade Doesn't Match Exactly

**Why:** Turboflakes calculates over different session ranges than your comparison period.
**Solution:** Use the same number of sessions: `-b 10 -a 10` vs Turboflakes `number_last_sessions=20`

### 2. Our Scores Are Slightly Higher (+0.01 to +0.03)

**Why:** We normalize PTS against our query dataset (single validator's sessions); Turboflakes normalizes against **all validators in the network** for that time period.

**Source:** Confirmed from [Turboflakes source code](https://github.com/turboflakes/one-t/blob/main/src/polkadot.rs):

```rust
// Turboflakes collects ALL validators' avg_para_points
let avg_para_points: Vec<u32> = validators
    .iter()
    .filter(|v| v.para_epochs >= 1 && v.missed_ratio.is_some())
    .map(|v| v.avg_para_points)      // ← ALL validators
    .collect();
let max = avg_para_points.iter().max()  // ← Network-wide max
let min = avg_para_points.iter().min()  // ← Network-wide min
```

**Our approach:** We only have access to one validator's sessions via the API, so we normalize against that validator's own min/max.

**Real-World Examples (Session 51466):**

```
Validator E3VZNd9JzQfBfh6GxMHx67b3LP8gWnJbhjZL7XPPGtCQvks:
  Our score:        0.9992
  Turboflakes:      0.988438
  Difference:      +0.0108 (+1.1%)

Validator GG1fakzTavhuof7CVaZU7SJxeK1r4ndoxcCrzbgPcZ7sQDx:
  Our score:        0.9425
  Turboflakes:      0.915251
  Difference:      +0.0273 (+3.0%)
```

**Impact:** This is **expected and acceptable**. For before/after comparisons, this difference cancels out since we use consistent normalization for both periods.

**Why it doesn't matter:** Your use case is comparing Session A vs Session B for the same validator, not comparing absolute scores to Turboflakes. Relative changes are what matter.

### 3. Authority-Only Sessions Are Excluded from Statistics

**Our behavior:** AUTH-only sessions are shown in detailed output (marked [AUTH]) but excluded from mean/median/range calculations.

**Turboflakes behavior:** AUTH-only sessions effectively score as 0 or are excluded from dashboard scores.

**This matches!** Both systems treat AUTH-only sessions as non-scoring for performance evaluation. You'll see output like:

```
AFTER CHANGE (3 sessions total, 2 paravalidator)
Note: 1 AUTH-only session(s) excluded from statistics
Para Rate: 66.7%
Mean Score: 0.9161 (calculated from 2 PARA sessions only)
```

## Real-World Validation Example

**Test Run:**

```bash
$ ./compare-performance.py JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ 51463 -b 1 -a 1 -d

Session 51462: 0.9992 (A+)
  MVR: 0.000 (0/164) = 0.5000
  BAR: 0.997 = 0.2492
  PTS: 3320 pts = 0.1800
  PV:  = 0.0700
  Total: 0.9992
```

**API Verification:**

```bash
$ curl -s "https://kusama-onet-api.turboflakes.io/api/v1/validators/JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ/grade?number_last_sessions=10&show_summary=true" | jq '.sessions_data[] | select(.session == 51462) | {ev: .para_summary.ev, iv: .para_summary.iv, mv: .para_summary.mv, ba: .para.bitfields.ba, bu: .para.bitfields.bu, pt: .para_summary.pt}'

{
  "ev": 147,
  "iv": 17,
  "mv": 0,
  "ba": 590,
  "bu": 2,
  "pt": 3320
}
```

**Manual Calculation:**

- MVR: 0/164 = 0, Component: 0.5000 ✓
- BAR: 590/592 = 0.9966, Component: 0.2492 ✓
- PTS: Normalized = 0.1800 ✓
- PV: Paravalidator = 0.0700 ✓
- **Total: 0.9992** ✓✓

## Quick Validation Checklist

When testing your configuration changes:

- [ ] Run script with `-d` flag to see detailed components
- [ ] Compare overall grade range (A, A+, B, etc.) with Turboflakes
- [ ] Verify raw vote counts match API data
- [ ] Check authority/para inclusion percentages
- [ ] Focus on relative comparison (before vs after) not absolute scores
- [ ] Use at least 5-10 sessions for meaningful statistics

## The Bottom Line

**The script uses the official Turboflakes ONE-T formula** and calculates scores directly from the raw API data. Variations of ±0.02 in individual components are normal due to:

- Different session ranges
- Point normalization (dataset-specific vs network-wide)
- Timing of API queries

**For performance comparison purposes** (before/after a change), these minor variations don't matter - you're comparing relative changes using the same calculation method, which is statistically sound.

## Need Help?

If you see significant discrepancies (>0.10 difference):

1. Check you're using the correct validator address
2. Verify the validator was active in those sessions
3. Compare the raw API data with `-d` detailed output
4. Ensure you're comparing the same session ranges
