# Operator Map func_in Monkey Patch

## Current Implementation

This monkey patch currently mirrors the original Frappe `func_in` implementation from `frappe.database.operator_map`:

```python
def func_in(key: Field, value: list | tuple) -> frappe.qb:
    if isinstance(value, str):
        value = value.split(",")

    value = ["" if v is None else v for v in value]
    if "" in value and key.name != "name":
        return Coalesce(key, "").isin(value)
    return key.isin(value)
```

## Behavior

- Converts `None` to empty string `''`
- Applies `COALESCE(field, '')` when empty strings are in the values list
- Excludes `name` field from COALESCE wrapping

## Known Issue

This logic applies COALESCE even for empty strings, which can prevent index usage:

### Current Query (with COALESCE)
```sql
-- Prevents efficient index usage
SELECT * FROM `tabAccount` 
WHERE COALESCE(`name`,'') IN ('','5gl876rgps')
```

### Potential Optimization

To fix the index usage issue, the logic should track if original values contained `None` before conversion:

```python
# Check for actual NULL before converting
has_null = any(v is None for v in value)
value = ["" if v is None else v for v in value]

# Only apply COALESCE if there was actual NULL
if has_null and key.name not in ("name", "modified", "creation"):
    return Coalesce(key, "").isin(value)
return key.isin(value)
```

This would generate:
```sql
-- Uses index efficiently when no NULL values
SELECT * FROM `tabAccount` 
WHERE `name` IN ('','5gl876rgps')
```

## Why This Monkey Patch Exists

Placeholder for future optimization or to override Frappe core changes without modifying bench files directly.

## Related

- `frappe.database.operator_map.func_in` (original implementation)
- `frappe.database.query.Engine._should_apply_ifnull` (QB engine compatibility)
