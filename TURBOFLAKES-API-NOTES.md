# Turboflakes API Documentation & Notes

This document captures important findings and best practices for working with the Turboflakes ONE-T API.

## Table of Contents

1. [API Endpoints](#api-endpoints)
2. [Address Format (SS58)](#address-format-ss58)
3. [Session Data](#session-data)
4. [API Limitations](#api-limitations)
5. [Common Pitfalls](#common-pitfalls)
6. [Best Practices](#best-practices)
7. [Testing Examples](#testing-examples)

---

## API Endpoints

### Individual Validator Query

**Without `/grade` (Recommended for most use cases):**

```bash
# Polkadot - current session only
curl https://polkadot-onet-api.turboflakes.io/api/v1/validators/ADDRESS?show_summary=true

# Kusama - current session only
curl https://kusama-onet-api.turboflakes.io/api/v1/validators/ADDRESS?show_summary=true
```

**Response Structure:**

```json
{
  "address": "5xxx...",
  "session": 11840,
  "is_auth": true,
  "is_para": true,
  "auth": { ... },
  "para": { ... },
  "para_summary": {
    "pt": 11260,
    "ca": 562,
    "ab": 2,
    "ev": 143,
    "iv": 409,
    "mv": 0
  }
}
```

**Key Points:**

- ✅ Returns current (open/incomplete) session
- ✅ Useful for real-time monitoring (e.g., stalled validator detection)
- ✅ Returns validator data without grade calculation
- ✅ Has `para_summary` with all scoring data
- ⚠️ **`number_last_sessions` parameter is IGNORED on this endpoint** - always returns current session only

**With `/grade` (Used by Crunch payout software):**

```bash
# Polkadot - get last N completed sessions
curl https://polkadot-onet-api.turboflakes.io/api/v1/validators/ADDRESS/grade?number_last_sessions=3&show_summary=true

# Kusama - get last N completed sessions
curl https://kusama-onet-api.turboflakes.io/api/v1/validators/ADDRESS/grade?number_last_sessions=3&show_summary=true
```

**Response Structure:**

```json
{
  "address": "5xxx...",
  "grade": "A+",
  "sessions_data": [
    {
      "session": 11837,
      "is_auth": true,
      "is_para": true,
      "auth": { ... },
      "para": { ... },
      "para_summary": { ... }
    },
    { ... },
    { ... }
  ],
  "authority_inclusion": 1.0,
  "para_authority_inclusion": 0.95,
  ...
}
```

**Key Points:**

- ✅ Includes grade calculation
- ✅ Returns only **completed sessions** (excludes the current open session)
- ✅ **`number_last_sessions` parameter WORKS on this endpoint** - returns array in `sessions_data`
- ✅ Has `para_summary` for each session with all scoring data
- ✅ Use when you need historical data for multiple sessions

**Recommendation from Turboflakes**

According to Turboflakes developer, the `/grade` endpoint was specifically designed to be used in Crunch. One may not really care about the grade since one can calculate the Grade themselves, thus one can just use `.../validators/ADDRESS?show_summary=true`"

**Important:** For our performance analysis script, we use `/grade` endpoint because we need historical session data (`number_last_sessions` parameter only works with `/grade`).

### Network-Wide Validator Query

```bash
# Polkadot - get all paravalidators for a session
curl https://polkadot-onet-api.turboflakes.io/api/v1/validators?role=para_authority&session=11796&show_summary=true

# Kusama - get all paravalidators for a session
curl https://kusama-onet-api.turboflakes.io/api/v1/validators?role=para_authority&session=51500&show_summary=true
```

**Response Structure:**

```json
{
  "session": 11796,
  "data": [
    {
      "address": "5xxx...",
      "is_auth": true,
      "is_para": true,
      "auth": { ... },
      "para": { ... },
      "para_summary": {
        "pt": 11020,
        "ca": 552,
        "ab": 2,
        "ev": 480,
        "iv": 67,
        "mv": 2
      }
    },
    ...
  ]
}
```

**Key Points:**

- ✅ Returns **ALL active paravalidators** for the specified session
- ✅ Polkadot: ~600 active paravalidators
- ✅ Kusama: ~700 active paravalidators
- ✅ Useful for network-wide statistics and normalization
- ⚠️ **Large response** - Can be 500KB+ (cache recommended)
- See [API Limitations](#api-limitations) for details

---

## Address Format (SS58)

### The Critical Discovery

**Turboflakes stores all addresses in generic Substrate SS58 format (prefix 42), NOT network-specific formats.**

#### Example Conversion

| Network Format               | Address                                            | Starts With                       |
| ---------------------------- | -------------------------------------------------- | --------------------------------- |
| **Polkadot** (prefix 0)      | `16fbkDCMrAo1uyC52NyA8Y2dETnYVpCofSoj3QEE2WUNnkLk` | `1`, `2`, or `3`                  |
| **Generic SS58** (prefix 42) | `5HjJbswHzPXYUSBZ4jv9zPCUNqntoWefax5Et7EsURSrcKDV` | `5`                               |
| **Kusama** (prefix 2)        | `JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ`  | `C`, `D`, `E`, `F`, `G`, `H`, `J` |
| **Generic SS58** (prefix 42) | `5xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`        | `5`                               |

> **These are the SAME validator**, just encoded differently!

### How Turboflakes Handles This

Turboflakes keeps the account in SS58 format without the prefix, so (prefix: 0) `16fbkDCMrAo1uyC52NyA8Y2dETnYVpCofSoj3QEE2WUNnkLk` `5HjJbswHzPXYUSBZ4jv9zPCUNqntoWefax5Et7EsURSrcKDV`

**You can query the API with EITHER format**, and it will return data using the generic SS58 format (starting with `5`).

### Address Conversion Methods

#### Option 1: Use Turboflakes API

```bash
# Query with your network-specific address
curl https://polkadot-onet-api.turboflakes.io/api/v1/validators/16fbk...nkLk?number_last_sessions=1 | jq '.address'

# Returns: "5HjJbswHzPXYUSBZ4jv9zPCUNqntoWefax5Et7EsURSrcKDV"
```

#### Option 2: Use Subscan Tool

Visit: https://polkadot.subscan.io/tools/format_transform

#### Option 3: Python Library

```python
from substrateinterface import Keypair

# Decode any SS58 format
keypair = Keypair(ss58_address="16fbkDCMrAo1uyC52NyA8Y2dETnYVpCofSoj3QEE2WUNnkLk")

# Re-encode with generic prefix (42)
generic = keypair.ss58_address_from_ss58_public_key(keypair.public_key, ss58_format=42)
# Returns: "5HjJbswHzPXYUSBZ4jv9zPCUNqntoWefax5Et7EsURSrcKDV"
```

### Impact on Network Queries

When searching for validators in the network-wide API response, you **MUST use the generic SS58 format** (starting with `5`).

**Wrong:**

```bash
jq '.data[] | select(.address == "16fbkDCMrAo1uyC52NyA8Y2dETnYVpCofSoj3QEE2WUNnkLk")' response.json
# Returns: nothing (not found)
```

**Correct:**

```bash
jq '.data[] | select(.address == "5HjJbswHzPXYUSBZ4jv9zPCUNqntoWefax5Et7EsURSrcKDV")' response.json
# Returns: validator data ✓
```

---

## Session Data

### Current vs Completed Sessions

- **Without `/grade`**: Returns ALL sessions including the current open session
- **With `/grade`**: Returns only completed sessions (an intentional limitation of /grade)

### Session Completeness

Our investigation ([SESSION-DATA-FINDINGS.md](./SESSION-DATA-FINDINGS.md)) confirmed that:

- ✅ The API returns complete data for the latest session
- ✅ Low points in a session indicate low activity for that validator's group, NOT incomplete data
- ✅ Default behavior: Include the latest completed session in analysis

### Inactive Paravalidator Sessions

⚠️ **CRITICAL FINDING:** Some sessions have `is_para: true` but `para_summary: null`.

#### What This Means

These are validators that were **selected as paravalidators** but had **no paravalidation work** in that session:

- ✅ **Bitfields exist** (ba/bu values present)
- ❌ **No votes** (ev=0, iv=0, mv=0)
- ❌ **No backing points** (pt=null or 0)
- ❌ **para_summary is null** (not just empty)

**Example from Kusama Session 51934:**

```json
{
  "session": 51934,
  "is_para": true,
  "para_summary": null,
  "para": {
    "bitfields": {
      "ba": 593,
      "bu": 1
    },
    "group": 106
  }
}
```

#### How Turboflakes Handles These

**Dashboard Display:**

- Shows as "Score: 0" in single-session view
- **Hidden** when "Show only active paravalidators" filter is enabled
- Displays all stats as blank/NaN except bitfields and BAR

**API & Aggregation Behavior:**

- ✅ **Included in `para_authority_inclusion`** calculation (counts toward para rate: 37/50 = 0.74)
- ✅ **Included in aggregated scoring** when multiple sessions are selected
- ✅ **Scored internally** using bitfield data (~0.82: MVR=0.50, BAR=0.25, PTS=0.00, PV=0.07)
- ❌ **Not shown in "active paravalidators" network rankings** (excluded from the displayed list)

**Why This Happens:**

- Validator was assigned to a paravalidator group
- The parachain(s) in their group had no activity that session
- Validator submitted bitfields but had no backing work to perform
- This is normal network behavior, not a validator issue

#### Impact on Performance Analysis

When analyzing before/after configuration changes:

- ✅ **Include them** in session counts (matches Turboflakes' `para_authority_inclusion`)
- ✅ **Include them** in statistics (they represent actual node behavior)
- ✅ **Label them** as `[PARA-INACTIVE]` for visibility
- ⚠️ **Score them** using available data: MVR=0.5, BAR=(from bitfields), PTS=0, PV=0.07

**Real-world impact:**

- Configuration changes can affect the frequency of these sessions
- Tuning that causes higher CPU/memory usage might increase inactive para sessions
- They indicate parachain activity patterns, not necessarily node issues
- Excluding them would misrepresent actual validator participation rates

### API Data Completeness Update (November 2025)

✅ **RESOLVED:** Historical API inconsistency has been fixed!

**Previous Issue:**

In rare edge cases (particularly around epoch boundaries), the `/validators?session=X` endpoint would return `para_summary: null` for active paravalidator sessions even when the validator performed work. This was distinct from legitimate inactive paravalidator sessions (where validators had no work to perform).

**Resolution Status:**

- ✅ **Fixed** as of November 2025 by Turboflakes development team
- ✅ **Verified** on 11-19-25 with comprehensive testing:
  - 40 consecutive Polkadot sessions tested (11970-12010)
  - 100% success rate - all paravalidator sessions returned complete `para_summary` data
  - No instances of missing data for active sessions
- ✅ **Impact:** No longer affects performance analysis

**Testing Details:**

```bash
# Verification test performed:
./compare-performance.py 12Qq3fn9xnFZ37Ltcj6BH8NSpAQjEMp2oKnEALa7bbuguU4L 12000 \
  -b 30 -a 10 -n polkadot --network-normalized -d

Results:
- All 40 sessions: Complete data (600/600 or 599/599 validators)
- All paravalidator sessions: Full para_summary present
- All rankings calculated successfully (requires para_summary)
- Zero errors or warnings about missing data
```

**Conclusion:**

The API now consistently returns complete data for all active paravalidator sessions. The only sessions with `para_summary: null` are legitimate inactive paravalidator sessions (documented above) where validators had no work to perform.

### Aggregated vs Per-Session Scoring

⚠️ **Important:** Turboflakes uses **aggregated statistics** to calculate scores, not per-session averages.

**Their Method (from source code):**

```
Score = (1 - total_missed/total_votes) * 0.50
      + (total_ba/total_bitfields) * 0.25
      + (avg_backing_points normalized) * 0.18
      + (para_sessions/total_sessions) * 0.07
```

**Not this:**

```
Score = average(session1_score, session2_score, session3_score, ...)
```

**Why This Matters:**

- Aggregating statistics first, then calculating one score ≠ averaging individual session scores
- Difference is usually small (<1%) but can be significant with inactive sessions
- When you select sessions 51934+51935 on dashboard:
  - Session 51934: Displayed as "Score: 0", internally ~0.82
  - Session 51935: Score: 0.935216
  - Combined: 0.897688 (aggregated stats, not (0+0.935)/2)

**Our Implementation:**

- Uses **per-session scoring** for easier before/after comparisons
- Scores individual sessions with network-wide normalization
- Better for identifying specific sessions with issues
- Simpler to understand which configuration change affected which sessions
- Tradeoff: Scores differ slightly (~1-3%) from Turboflakes' aggregated approach

---

## API Limitations

### Validator Count per Network

The `/api/v1/validators?session=X` endpoint returns **all active paravalidators** for the specified network and session.

#### Active Paravalidator Counts

| Network      | Active Paravalidators | Notes                            |
| ------------ | --------------------- | -------------------------------- |
| **Polkadot** | ~600                  | Consistent count across sessions |
| **Kusama**   | ~700                  | Slightly higher validator set    |

**Key Point:** The "600 validator limit" that was initially thought to be an API restriction is actually just the number of active paravalidators on Polkadot. The API returns **all** active paravalidators.

#### What This Means

**For Active Validators:**

- ✅ All active paravalidators ARE included in network-wide queries
- ✅ Full ranking is available for all active validators
- ✅ Network-wide statistics (min/max/avg) include all active paravalidators

**For Inactive Validators:**

- ❌ Inactive validators won't appear in network queries (they're not participating)
- ✅ They can still be queried individually
- ⚠️ Their ranking cannot be determined (not in the active set)

**Example - User's Polkadot Validators in Session 11796:**

| Validator                                          | In Query? | Status                                                |
| -------------------------------------------------- | --------- | ----------------------------------------------------- |
| `12Qq3fn9xnFZ37Ltcj6BH8NSpAQjEMp2oKnEALa7bbuguU4L` | ✅ Yes    | Active - Full ranking available (#136, #231)          |
| `15zH8tbFxyBgvkAdF3UWSfykAXADbS32vJuYRHTkZJ15Y4jd` | ✅ Yes    | Active - Full ranking available (#31, #467)           |
| `16fbkDCMrAo1uyC52NyA8Y2dETnYVpCofSoj3QEE2WUNnkLk` | ❌ No     | Inactive for 2+ weeks (not participating in sessions) |

> **Important**: After implementing SS58 address conversion (Polkadot format → generic SS58), both active validators were found in the network response! The third wasn't found because it's inactive, not because of any API limitation.

### Number of Sessions Limit (`number_last_sessions`)

⚠️ **CRITICAL**: The `number_last_sessions` parameter has a hard limit of **192 sessions**.

#### Observed Behavior

| Sessions Requested | Result   | Notes                                            |
| ------------------ | -------- | ------------------------------------------------ |
| 100 sessions       | ✅ Works | Returns 100 sessions successfully                |
| 145 sessions       | ✅ Works | Returns 145 sessions successfully                |
| 188 sessions       | ✅ Works | Returns 188 sessions successfully (via `-b 177`) |
| 192 sessions       | ✅ Works | **Maximum** supported by API                     |
| 193 sessions       | ❌ Fails | Returns 404 error (exceeds limit)                |
| 200+ sessions      | ❌ Fails | Exceeds hard limit                               |

**Error Example:**

```bash
# Requesting 193 sessions fails
./compare-performance.py VALIDATOR 51973 -b 178

Error fetching data: 404 Client Error: Not Found for url:
https://kusama-onet-api.turboflakes.io/api/v1/validators/VALIDATOR/grade?number_last_sessions=193&show_summary=true
```

**Note:** When using `-b N`, the total sessions requested = N + (current_session - change_session) + padding, so the effective maximum for `-b` is approximately **177-180** depending on how many sessions after the change exist.

#### Workaround

If you need to analyze more than 192 sessions:

1. **Break into smaller chunks:**

   ```bash
   # Instead of -b 200, split into multiple runs:
   ./compare-performance.py VALIDATOR 51700 -b 100 -a 0   # Sessions 51600-51700
   ./compare-performance.py VALIDATOR 51800 -b 100 -a 0   # Sessions 51700-51800
   ```

2. **Use network-normalized mode with caching:**

   ```bash
   # First run caches sessions 51700-51800
   ./compare-performance.py VALIDATOR 51750 -b 50 -a 50 --network-normalized

   # Second run reuses cache, just queries validator data
   ./compare-performance.py VALIDATOR 51650 -b 50 -a 50 --network-normalized
   ```

3. **Consider session ranges carefully:**
   - Kusama sessions: ~1 hour each (150 sessions = ~1 week)
   - Polkadot sessions: ~4 hours each (150 sessions = ~4 weeks)

### Response Size

- **Polkadot:** ~500-600KB per session (600 validators)
- **Kusama:** ~600-700KB per session (700 validators)
- **Recommendation:** Cache network-wide queries to avoid repeated large downloads

### Auth-Only Session Detection

When a validator is selected as an authority but not as a paravalidator for a session:

- The script displays: `ℹ️  Session X: is_para: false, no paravalidator score. Auth-only, no para work`
- The session is excluded from paravalidator statistics (matching Turboflakes behavior)
- The session is still counted for overall activity tracking

---

## Common Pitfalls

### 1. `number_last_sessions` Parameter Behavior

⚠️ **CRITICAL:** The `number_last_sessions` parameter behaves differently depending on the endpoint:

| Endpoint                           | `number_last_sessions` | Behavior                            |
| ---------------------------------- | ---------------------- | ----------------------------------- |
| `/api/v1/validators/ADDRESS`       | ❌ IGNORED             | Always returns current session only |
| `/api/v1/validators/ADDRESS/grade` | ✅ WORKS               | Returns array of N sessions         |

**Example of Confusion:**

```bash
# This DOES NOT return 3 sessions (parameter is ignored)
curl https://polkadot-onet-api.turboflakes.io/api/v1/validators/ADDRESS?show_summary=true&number_last_sessions=3

# This DOES return 3 sessions (in sessions_data array)
curl https://polkadot-onet-api.turboflakes.io/api/v1/validators/ADDRESS/grade?show_summary=true&number_last_sessions=3
```

**Why this matters:**

- If you need historical data for multiple sessions, **you must use `/grade`**
- The standard endpoint (without `/grade`) will always return only the current session, regardless of `number_last_sessions` value

### 2. `number_last_sessions` Has a Hard Limit of 192

⚠️ **CRITICAL:** Requesting more than **192 sessions** will result in a **404 error**:

```bash
# ✅ Works - 192 sessions (maximum)
curl "https://kusama-onet-api.turboflakes.io/api/v1/validators/ADDRESS/grade?number_last_sessions=192&show_summary=true"

# ❌ Fails - 193 sessions (returns 404)
curl "https://kusama-onet-api.turboflakes.io/api/v1/validators/ADDRESS/grade?number_last_sessions=193&show_summary=true"
```

**Solution:** Break large requests into smaller chunks (see [API Limitations](#api-limitations) for workarounds)

**Script Behavior:** The limit check is performed **at API query time**, not at user input time:

- Users can request any number of sessions via `--last-change` or `-b`
- When the script is about to query the API, it checks if the request exceeds 192 sessions
- If it does, the script automatically adjusts the range and displays a warning
- Continues with the maximum possible range within the limit
- **Future benefit**: This approach allows caching mechanisms to serve data beyond 192 sessions without artificial input restrictions

Example:

```bash
# Request 372 sessions (exceeds limit)
./compare-performance.py ADDRESS 51973 --last-change 51600 --network-normalized

# Output:
# Auto-calculated -b 372 from --last-change 51600 (sessions 51601 to 51972)
# ⚠️  API LIMIT: Requested 389 sessions exceeds API limit (192)
#     Adjusted -b from 372 to 175 to stay within limit
#     Analysis will cover sessions 51798 to 51972 (before)
# API Query: .../grade?number_last_sessions=192&show_summary=true
```

**Network-Normalized Mode**: In this mode, after the initial grade fetch, individual sessions are queried via `/validators?session=X` (no limit) and cached in memory. This means network data can be reused across the analysis without hitting the 192-session restriction repeatedly.

---

## Best Practices

### When Querying Individual Validators

1. ✅ Use `?show_summary=true` for detailed para_summary data
2. ✅ Use `/grade` endpoint when you need historical data (multiple sessions)
3. ✅ Omit `/grade` for real-time monitoring (current session only)
4. ✅ Accept either Polkadot or generic SS58 format in queries
5. ✅ Store/display the generic SS58 format (what API returns)

### When Querying Network-Wide Data

1. ✅ Query with `?role=authority&session=X&show_summary=true` to get ALL validators (para + auth-only)
2. ✅ Convert addresses to generic SS58 (prefix 42) before searching
3. ✅ Check `is_para` field to distinguish paravalidators from auth-only
4. ✅ Cache results to avoid repeated queries
5. ✅ Handle auth-only sessions gracefully with informative messages

### Address Handling

1. ✅ Accept user input in any SS58 format
2. ✅ Convert to generic SS58 (prefix 42) for API lookups
3. ✅ Display addresses in the format the API returns (generic SS58)
4. ✅ Optionally provide both formats for user convenience

---

## Testing Examples

Use these working validator addresses to test API behavior:

**Polkadot Validator:** `15zH8tbFxyBgvkAdF3UWSfykAXADbS32vJuYRHTkZJ15Y4jd`
**Kusama Validator:** `JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ`

### Get Current Session Number (Quick Reference)

**Fastest method** (~1 second, 2KB response):

```bash
# Polkadot
curl -s "https://polkadot-onet-api.turboflakes.io/api/v1/validators/15zH8tbFxyBgvkAdF3UWSfykAXADbS32vJuYRHTkZJ15Y4jd" | jq -r '.session'

# Kusama
curl -s "https://kusama-onet-api.turboflakes.io/api/v1/validators/JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cmxWkc8vM2uZ" | jq -r '.session'
```

**Alternative** (no validator address needed, but slower ~1.8s, 500-700KB):

```bash
# Polkadot
curl -s "https://polkadot-onet-api.turboflakes.io/api/v1/validators?role=para_authority" | jq -r '.session'

# Kusama
curl -s "https://kusama-onet-api.turboflakes.io/api/v1/validators?role=para_authority" | jq -r '.session'
```

### Verify `number_last_sessions` Behavior

```bash
# Test 1: Standard endpoint - parameter IGNORED
curl -s "https://polkadot-onet-api.turboflakes.io/api/v1/validators/15zH8tbFxyBgvkAdF3UWSfykAXADbS32vJuYRHTkZJ15Y4jd?show_summary=true&number_last_sessions=3" | jq '{session: .session, note: "Only 1 session - parameter ignored"}'

# Test 2: /grade endpoint - parameter WORKS
curl -s "https://polkadot-onet-api.turboflakes.io/api/v1/validators/15zH8tbFxyBgvkAdF3UWSfykAXADbS32vJuYRHTkZJ15Y4jd/grade?number_last_sessions=3&show_summary=true" | jq '{sessions: [.sessions_data[].session], note: "Multiple sessions - parameter works!"}'
```

**Expected Results:**

- Test 1: Returns single session number
- Test 2: Returns array of 3 session numbers

### Verify Network Validator Counts

```bash
# Polkadot - should return ~600 validators
curl -s "https://polkadot-onet-api.turboflakes.io/api/v1/validators?role=para_authority&session=11840&show_summary=true" | jq '.data | length'

# Kusama - should return ~700 validators
curl -s "https://kusama-onet-api.turboflakes.io/api/v1/validators?role=para_authority&session=51680&show_summary=true" | jq '.data | length'
```

**Expected Results:**

- Polkadot: `600`
- Kusama: `700`

### Verify Address Conversion

```bash
# Query with network-specific format, get generic SS58 back
curl -s "https://polkadot-onet-api.turboflakes.io/api/v1/validators/15zH8tbFxyBgvkAdF3UWSfykAXADbS32vJuYRHTkZJ15Y4jd?show_summary=true" | jq -r '.address'
```

**Expected Result:** `5H3yzZLC7BvDVDA7HQRWJX9bJuAZu8UtqpB4FzUQ1CyZMaGC` (generic SS58 format, starts with '5')

---

## Related Documentation

- [NETWORK-NORMALIZATION.md](./NETWORK-NORMALIZATION.md) - Network-wide score normalization
- [API-LIMITATION-SOLUTION.md](./API-LIMITATION-SOLUTION.md) - How we handle the 600-validator limit
- [SESSION-DATA-FINDINGS.md](./SESSION-DATA-FINDINGS.md) - Session data completeness investigation
- [VALIDATION-GUIDE.md](./VALIDATION-GUIDE.md) - How to validate scores against dashboard

---

## Credits

Many thanks to **Paulo from Turboflakes** for clarifying the SS58 address format behavior and API endpoint purposes.
