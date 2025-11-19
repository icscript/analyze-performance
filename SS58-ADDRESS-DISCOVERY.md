# SS58 Address Format Discovery

## The Breakthrough

**Date:** October 14, 2025

**Problem:** Validators appeared to be missing from Turboflakes network API responses.

**Root Cause:** Address format mismatch - Turboflakes stores addresses in generic SS58 format (prefix 42), not network-specific formats.

---

## The Investigation

### Initial Symptoms

When querying `/api/v1/validators?role=para_authority&session=11796`:

- API returned 600 validators ✓
- Searched for user's Polkadot validators ❌
- Found 0 results

**Conclusion (Wrong):** "Polkadot has >600 active paravalidators, API is limiting us."

### The Discovery

User provided information from Paulo (Turboflakes):

> "We kept the account in SS58 format without the prefix, so (prefix: 0) `16fbkDCMrAo1uyC52NyA8Y2dETnYVpCofSoj3QEE2WUNnkLk` = `5HjJbswHzPXYUSBZ4jv9zPCUNqntoWefax5Et7EsURSrcKDV`"

**Key Insight:** These are the SAME validator, just in different SS58 encoding formats!

### Testing the Theory

```bash
# Query API with Polkadot address
curl ".../validators/12Qq3fn9xnFZ37Ltcj6BH8NSpAQjEMp2oKnEALa7bbuguU4L/grade?number_last_sessions=1"

# Returns:
{
  "address": "5DUXuLX66zz5baLNf63B8yYHxYR5Y4Ftiq3k13am3WtAipuL",  # ← Generic SS58!
  "sessions_data": [...]
}
```

**Search in saved network data:**

```bash
grep "12Qq3fn9xnFZ37Ltcj6BH8NSpAQjEMp2oKnEALa7bbuguU4L" session-11796-all-validators.json
# Result: 0 matches ❌

grep "5DUXuLX66zz5baLNf63B8yYHxYR5Y4Ftiq3k13am3WtAipuL" session-11796-all-validators.json
# Result: 1 match ✅ FOUND!
```

---

## Address Format Explained

### SS58 Format Prefixes

| Network               | Prefix | Address Starts With               | Example                                            |
| --------------------- | ------ | --------------------------------- | -------------------------------------------------- |
| **Polkadot**          | 0      | `1`, `2`, `3`                     | `16fbkDCMrAo1uyC52NyA8Y2dETnYVpCofSoj3QEE2WUNnkLk` |
| **Generic Substrate** | 42     | `5`                               | `5HjJbswHzPXYUSBZ4jv9zPCUNqntoWefax5Et7EsURSrcKDV` |
| **Kusama**            | 2      | `C`, `D`, `E`, `F`, `G`, `H`, `J` | `JKupaoCtkRzMjCDQJbVMbG1jmEr8ebtoRG7cemxWkc8vM2uZ` |

### Why This Matters

- **User input:** Network-specific format (Polkadot, Kusama, etc.)
- **Turboflakes storage:** Generic SS58 format (prefix 42)
- **Search requirement:** Must convert before comparing

### Conversions for User's Validators

| Polkadot Address (input)                           | Generic SS58 (in API)                              | Status                        |
| -------------------------------------------------- | -------------------------------------------------- | ----------------------------- |
| `12Qq3fn9xnFZ37Ltcj6BH8NSpAQjEMp2oKnEALa7bbuguU4L` | `5DUXuLX66zz5baLNf63B8yYHxYR5Y4Ftiq3k13am3WtAipuL` | ✅ Active, found in 600       |
| `15zH8tbFxyBgvkAdF3UWSfykAXADbS32vJuYRHTkZJ15Y4jd` | `5H3yzZLC7BvDVDA7HQRWJX9bJuAZu8UtqpB4FzUQ1CyZMaGC` | ✅ Active, found in 600       |
| `16fbkDCMrAo1uyC52NyA8Y2dETnYVpCofSoj3QEE2WUNnkLk` | `5HjJbswHzPXYUSBZ4jv9zPCUNqntoWefax5Et7EsURSrcKDV` | ❌ Inactive (not in response) |

> **Note:** The third validator wasn't found because it's been inactive for weeks, NOT because of API limitations!

---

## The Solution

### Implementation in `compare-performance.py`

Added `convert_to_generic_ss58()` method:

```python
def convert_to_generic_ss58(self, address: str) -> str:
    """Convert address to generic SS58 format (prefix 42)

    Turboflakes stores all addresses in generic SS58 format,
    regardless of the network-specific format used in queries.
    """
    # Query the API with the address - it returns generic SS58 format
    url = f"{self.api_base}/api/v1/validators/{address}/grade"
    params = {'number_last_sessions': 1}

    response = requests.get(url, params=params, timeout=30)
    data = response.json()
    return data.get('address')  # Returns generic SS58 format
```

Updated `get_validator_ranking()` to convert before searching:

```python
def get_validator_ranking(self, address: str, session: int, network_data: Dict):
    # Convert address to generic SS58 format for comparison
    generic_address = self.convert_to_generic_ss58(address)

    # Find validator in list
    for rank, val in enumerate(validators, 1):
        if val['address'] == generic_address:  # ← Now matches!
            # ... ranking calculation ...
```

---

## Results: Before vs After

### Before Address Conversion Fix

```
Session  11795: 0.9932 (A+) [PARA]
  Rank by Score: Not ranked (validator outside API's 600 returned, +1% vs network avg)
  Backing Points: 11340 (network min-max: 0-11500, avg: 10749)
  Note: Score calculated using network-wide normalization
```

**Issue:** Validator not found in network data due to address format mismatch.

### After Address Conversion Fix

```
Session  11795: 0.9932 (A+) [PARA]
  Rank by Score: #136 of 600 paravalidators (Top 23%, +1% vs avg)
  Backing Points: 11340 (network: 0-11500, avg: 10749)
```

**Success:** Validator found in the 600, full ranking available!

### Impact on Rankings

**Validator `12Qq...`:**

- Session 11795: **#136** of 600 (Top 23%)
- Session 11797: **#231** of 600 (Top 39%)

**Validator `15zH...`:**

- Session 11795: **#31** of 600 (Top 6%) 🌟
- Session 11797: **#467** of 600 (Top 78%)

---

## Lessons Learned

1. **Always check address formats** when working with substrate-based chains
2. **API responses can use different encoding** than user input
3. **"Not found" doesn't always mean "doesn't exist"** - it might mean "wrong format"
4. **Use the API itself for conversion** - simplest and most reliable method
5. **Test with known validators** before assuming API limitations

---

## Key Takeaways

✅ **The API is working correctly** - Returns all active validators via `role=authority`
✅ **Address conversion is essential** when searching network data
✅ **Auth-only sessions clearly detected** with informative messages
✅ **Exact scores and rankings now available** for all active validators

---

## Related Documentation

- **[TURBOFLAKES-API-NOTES.md](./TURBOFLAKES-API-NOTES.md)** - Full API documentation including address formats
- **[NETWORK-NORMALIZATION.md](./NETWORK-NORMALIZATION.md)** - Network-wide score normalization
- **[PROJECT-STATUS.md](./PROJECT-STATUS.md)** - Complete project status and validation

---

## Credits

**Massive thanks to Paulo from Turboflakes** for the critical insight about SS58 address format storage!

This discovery transformed what appeared to be an insurmountable API limitation into a simple format conversion problem.
