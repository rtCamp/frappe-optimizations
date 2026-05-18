# Choose Top Doctypes - N+1 Query Optimization

This monkey patch optimizes `choose_top_doctypes()` in Frappe's `WorkspaceSidebar` by replacing per-doctype `COUNT(*)` queries with a single `INFORMATION_SCHEMA` lookup using the Frappe query builder.

## Problem Statement

The original `choose_top_doctypes()` function calls `frappe.db.count(doctype)` inside a loop — one `COUNT(*)` query per doctype:

```python
for doctype in doctype_names:
    if not is_single_doctype(doctype) and not frappe.get_meta(doctype).is_virtual:
        doctype_count_map[doctype] = frappe.db.count(doctype)
```

For a module with 20+ doctypes this fires 20+ individual queries, causing:
- **N+1 query problem** — one round-trip per doctype
- **Performance bottleneck** during sidebar auto-generation
- **Higher DB load** proportional to the number of doctypes per module

## Solution

Replace the per-doctype loop with a single `INFORMATION_SCHEMA.TABLES` query that fetches approximate row counts for all tables at once, with `ORDER BY table_rows DESC LIMIT 3` pushed to the database.

### Key Changes

#### Before

```python
doctype_count_map = {}
for doctype in doctype_names:
    if not is_single_doctype(doctype) and not frappe.get_meta(doctype).is_virtual:
        doctype_count_map[doctype] = frappe.db.count(doctype)  # N queries

top_doctypes = [
    name
    for name, count in sorted(doctype_count_map.items(), key=lambda x: x[1], reverse=True)[:3]
]
```

#### After

```python
info_schema = frappe.qb.Schema("information_schema")
rows = (
    frappe.qb.from_(info_schema.tables)
    .select(info_schema.tables.table_name)
    .where(
        (info_schema.tables.table_schema == frappe.conf.db_name)
        & (info_schema.tables.table_name.isin(table_names))
    )
    .orderby(info_schema.tables.table_rows, order=frappe.qb.desc)
    .limit(doctype_limit)
    .run(as_dict=True)
)
return [row["table_name"].removeprefix("tab") for row in rows]
```

#### `choose_top_doctypes_monkey_patch()`

```python
def choose_top_doctypes_monkey_patch() -> None:
    # nosemgrep
    from frappe.desk.doctype.workspace_sidebar import workspace_sidebar
    workspace_sidebar.choose_top_doctypes = choose_top_doctypes  # nosemgrep
```

**Purpose**: Replace Frappe's original function with the optimized version  
**Execution**: Automatically on app startup via `__init__.py`

---

## Performance Impact

| | Before | After |
|---|---|---|
| DB Queries | N (one per doctype) | 1 |
| Sorting | Python `sorted()` | `ORDER BY` in SQL |
| Rows transferred | All doctypes | 3 (LIMIT) |
| Count accuracy | Exact (`COUNT(*)`) | Approximate (InnoDB `TABLE_ROWS`) |

`TABLE_ROWS` in `INFORMATION_SCHEMA` is an InnoDB row-count estimate. It is not exact but is sufficient for picking the top 3 most-used doctypes by relative size.

> **Note**: Frappe's query builder handles Postgres transparently — `table_rows` is translated to `n_tup_ins` and `information_schema.tables` to `pg_stat_all_tables` automatically.
