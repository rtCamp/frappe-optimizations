__version__ = "0.0.1"


def monkey_patch():
	from .monkey_patches.update_coupon_code_count import update_coupon_code_count_monkey_patch

	update_coupon_code_count_monkey_patch()

	from .monkey_patches.get_pricing_rules import get_pricing_rules_monkey_patch

	get_pricing_rules_monkey_patch()


try:
	monkey_patch()
except Exception:
	import frappe

	frappe.log_error("Frappe Optimizations: Monkey Patch Failed", frappe.get_traceback())
