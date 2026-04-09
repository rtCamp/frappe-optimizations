import frappe


def choose_top_doctypes(doctype_names: list[str]) -> list[str] | None:
	"""Return top doctypes by approximate row count using a single INFORMATION_SCHEMA query.

	Replaces the original N+1 implementation that called frappe.db.count() per doctype.
	INFORMATION_SCHEMA.TABLE_ROWS is an InnoDB estimate — accurate enough for ranking.
	"""
	from frappe.model.utils import is_single_doctype

	doctype_limit = 3
	if len(doctype_names) <= doctype_limit:
		return None

	try:
		eligible = [
			d for d in doctype_names if not is_single_doctype(d) and not frappe.get_meta(d).is_virtual
		]
		if not eligible:
			return None

		table_names = [f"tab{d}" for d in eligible]
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
		# strip the "tab" prefix to get back to doctype names
		return [row["table_name"].removeprefix("tab") for row in rows]
	except frappe.db.ProgrammingError:
		return None


def choose_top_doctypes_monkey_patch() -> None:
	# nosemgrep
	from frappe.desk.doctype.workspace_sidebar import workspace_sidebar

	workspace_sidebar.choose_top_doctypes = choose_top_doctypes  # nosemgrep
