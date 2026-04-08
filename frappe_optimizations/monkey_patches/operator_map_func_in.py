import frappe
from frappe.query_builder import Field
from frappe.query_builder.functions import Coalesce


def func_in(key: Field, value: list | tuple) -> frappe.qb:
	"""Wrapper method for `IN`.

	Args:
	        key (str): field
	        value (Union[int, str]): criterion

	Return:
	        frappe.qb: `frappe.qb` object with `IN`
	"""
	if isinstance(value, str):
		value = value.split(",")

	value = ["" if v is None else v for v in value]
	if "" in value:
		return key.isin(value) | key.isnull()
	return key.isin(value)


def operator_map_func_in_monkey_patch():
	"""Monkey patch frappe.database.operator_map.func_in to fix COALESCE issue with empty strings."""
	# nosemgrep
	from frappe.database import operator_map

	operator_map.func_in = func_in  # nosemgrep
	operator_map.OPERATOR_MAP["in"] = func_in  # nosemgrep
