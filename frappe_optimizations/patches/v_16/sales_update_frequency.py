import frappe


def execute():
	try:
		frappe.db.set_single_value("Selling Settings", "sales_update_frequency", "Monthly")
	except Exception:
		print("Failed to set sales update frequency to Monthly")
		pass
