# Coupon Code Update Monkey Patch

## Problem Statement

We are facing deadlocks during the subscription purchase to payment process when updating coupon code usage counts. This monkey patch addresses race conditions that occur when multiple concurrent requests attempt to update the same coupon code's `used` count.

## Original Issue

The original implementation in ERPNext's `erpnext.accounts.doctype.pricing_rule.utils.update_coupon_code_count` uses Frappe's ORM runtime operations:

```python
def update_coupon_code_count(coupon_name, transaction_type):
    coupon = frappe.get_doc("Coupon Code", coupon_name)
    if coupon:
        if transaction_type == "used":
            if not coupon.maximum_use:
                coupon.used = coupon.used + 1
                coupon.save(ignore_permissions=True)
            elif coupon.used < coupon.maximum_use:
                coupon.used = coupon.used + 1
                coupon.save(ignore_permissions=True)
```

**Problems with this approach:**
1. **Race Condition**: Multiple concurrent requests load the same count value, increment it, and save - resulting in lost updates
2. **Deadlocks**: Under high load, concurrent transactions compete for locks on the same row, causing deadlocks
3. **No Atomic Operations**: The read-modify-write cycle is not atomic at the database level

## Solution

This monkey patch replaces the original function with an optimized version that:

### 1. **Direct SQL Updates (Atomic Operations)**
```python
frappe.db.sql("""
    UPDATE `tabCoupon Code`
    SET used = used + 1
    WHERE name = %s
    AND (maximum_use IS NULL OR maximum_use = 0 OR used < maximum_use)
""", (coupon_name,))
```

**Benefits:**
- Single atomic database operation
- No race conditions between read and write
- Database handles the increment directly

### 2. **Row Count Validation**
```python
affected_rows = frappe.db.sql("""SELECT ROW_COUNT();""")[0][0]
if not affected_rows:
    frappe.throw("Coupon code is no longer available or has reached its usage limit")
```

- Ensures the update actually happened (coupon is still valid)
- Prevents silent failures

### 3. **Automatic Retry with Exponential Backoff**
```python
max_retries = 3
for attempt in range(max_retries):
    try:
        # ... perform update ...
        break
    except frappe.QueryDeadlockError:
        if attempt == max_retries - 1:
            raise
        
        # Exponential backoff with jitter
        base_delay = 0.05  # 50ms
        jitter = random.uniform(0.01, 0.5)  # 10-500ms random
        exponential_backoff = base_delay * (2**attempt)  # 50ms, 100ms, 200ms
        total_delay = exponential_backoff + jitter + random.random() * 0.1
        time.sleep(total_delay)
```

**Why this works:**
- **Exponential backoff**: Each retry waits longer (50ms → 100ms → 200ms)
- **Random jitter**: Prevents multiple concurrent requests from retrying in lockstep
- **Limited retries**: Fails fast after 3 attempts instead of indefinite loops

### 4. **Safe Decrement for Cancellations**
```python
frappe.db.sql("""
    UPDATE `tabCoupon Code`
    SET used = GREATEST(used - 1, 0), modified = %s
    WHERE name = %s AND used > 0
""", (frappe.utils.now(), coupon_name))
```

- Uses `GREATEST()` to prevent negative counts
- Only updates if `used > 0` to avoid unnecessary writes

## Implementation

The monkey patch is applied in the [`frappe_optimizations`](../hooks.py) app hooks:

```python
def update_coupon_code_count_monkey_patch():
    from erpnext.accounts.doctype.pricing_rule import utils
    utils.update_coupon_code_count = update_coupon_code_count
```

This replaces the function at runtime before any coupon code operations occur.

## Impact

- **Reduced deadlocks**: Direct SQL operations and retries significantly reduce deadlock occurrences
- **Better performance**: Atomic operations are faster than ORM save operations
- **Data integrity**: Row count validation ensures coupon limits are respected
- **High concurrency support**: Handles multiple simultaneous purchase attempts gracefully

## Related Questions

### Does MariaDB revert the whole transaction on a deadlock error?

**Yes.** When MariaDB detects a deadlock:
1. It chooses one transaction as the "victim" 
2. Rolls back that entire transaction
3. Returns a deadlock error to the application
4. The other transaction(s) can proceed

This is why our retry mechanism works - we can safely retry the entire operation after a deadlock because no partial state remains.

## Testing

This patch has been tested under load and has shown:
- Significant reduction in deadlock errors
- No lost coupon code updates
- Proper enforcement of usage limits even under concurrent load

## Future Improvements

Consider exploring:
- Database-level advisory locks for more complex multi-row operations
- Optimistic locking patterns for the subscription document itself
- Connection pool tuning to reduce lock contention
