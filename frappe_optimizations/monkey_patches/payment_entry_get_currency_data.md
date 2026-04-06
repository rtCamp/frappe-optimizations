# Payment Entry get_currency_data Monkey Patch

## Problem Statement

We needed a custom change in ERPNext Payment Entry function `get_currency_data()` without editing ERPNext core files directly.

Direct core edits are difficult to maintain and can be overwritten during updates.

## Original Issue

The function in ERPNext core did not include our required argument in the `frappe.db.get_all()` query for fetching currency/exchange-rate metadata.

We required this behavior:

```python
frappe.db.get_all(
	doctype,
	filters={"name": ["in", refdoc]},
	fields=["name", "currency", "conversion_rate", "party_account_currency"],
	ignore_ifnull=True,
)
```

## Solution

Implemented a runtime monkey patch in `frappe_optimizations` that replaces:

- `erpnext.accounts.doctype.payment_entry.payment_entry.get_currency_data`

with our app-level implementation.

### Why this approach

1. No direct ERPNext core modification
2. Upgrade-safe customization path
3. Centralized patch loading with existing optimization patches

## Implementation

### 1. Added patch module

`frappe_optimizations/monkey_patches/payment_entry_get_currency_data.py`

- Contains custom `get_currency_data()` implementation
- Includes `get_currency_data_monkey_patch()` that assigns the function at runtime

### 2. Registered startup patch

In `frappe_optimizations/__init__.py`:

- Imported `get_currency_data_monkey_patch`
- Called it inside existing `monkey_patch()` loader

## Impact

- Core file remains untouched
- Required `ignore_ifnull=True` behavior is now active via app patch
- Patch is applied automatically during app import/startup

## Notes

- This follows the same monkey patch pattern already used in this app for pricing-rule optimizations.
