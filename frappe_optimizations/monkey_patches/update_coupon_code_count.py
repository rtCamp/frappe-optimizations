import frappe


def update_coupon_code_count(coupon_name, transaction_type):
	if transaction_type == "used":
		frappe.db.sql(
			"""
                    UPDATE `tabCoupon Code`
                    SET used = used + 1,  modified = %s
                    WHERE name = %s
                    AND (maximum_use IS NULL OR maximum_use = 0 OR used < maximum_use)
                """,
			(frappe.utils.now(), coupon_name),
		)
		affected_rows = frappe.db.sql("""SELECT ROW_COUNT();""")[0][0]

		if not affected_rows:
			frappe.throw(frappe._("Coupon code is no longer available or has reached its usage limit"))

	elif transaction_type == "cancelled":
		frappe.db.sql(
			"""
                    UPDATE `tabCoupon Code`
                    SET used = GREATEST(used - 1, 0), modified = %s
                    WHERE name = %s AND used > 0
                """,
			(frappe.utils.now(), coupon_name),
		)


def update_coupon_code_count_monkey_patch():
	# nosemgrep
	from erpnext.accounts.doctype.pricing_rule import utils

	utils.update_coupon_code_count = update_coupon_code_count  # nosemgrep

	# nosemgrep
	from erpnext.accounts.doctype.sales_invoice import sales_invoice

	sales_invoice.update_coupon_code_count = update_coupon_code_count  # nosemgrep
