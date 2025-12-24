import frappe


def update_coupon_code_count(coupon_name, transaction_type):
	max_retries = 3
	for attempt in range(max_retries):
		try:
			if transaction_type == "used":
				frappe.db.sql(
					"""
                    UPDATE `tabCoupon Code`
                    SET used = used + 1
                    WHERE name = %s
                    AND (maximum_use IS NULL OR maximum_use = 0 OR used < maximum_use)
                """,
					(coupon_name,),
				)
				affected_rows = frappe.db.sql("""SELECT ROW_COUNT();""")[0][0]

				if not affected_rows:
					frappe.throw(
						frappe._("Coupon code is no longer available or has reached its usage limit")
					)

			elif transaction_type == "cancelled":
				frappe.db.sql(
					"""
                    UPDATE `tabCoupon Code`
                    SET used = GREATEST(used - 1, 0), modified = %s
                    WHERE name = %s AND used > 0
                """,
					(frappe.utils.now(), coupon_name),
				)

			# Success - break out of retry loop
			break

		except frappe.QueryDeadlockError:
			if attempt == max_retries - 1:
				# Last attempt failed, re-raise the error
				raise

			import random
			import time

			# Random backoff to avoid concurrent retries colliding
			base_delay = 0.05  # 50ms base
			jitter = random.uniform(0.01, 0.5)  # 10ms to 500ms random jitter
			exponential_backoff = base_delay * (2**attempt)  # Exponential: 50ms, 100ms, 200ms
			total_delay = exponential_backoff + jitter + random.random() * 0.1

			time.sleep(total_delay)
			continue


def update_coupon_code_count_monkey_patch():
	# nosemgrep
	from erpnext.accounts.doctype.pricing_rule import utils

	utils.update_coupon_code_count = update_coupon_code_count  # nosemgrep

	# nosemgrep
	from erpnext.accounts.doctype.sales_invoice import sales_invoice

	sales_invoice.update_coupon_code_count = update_coupon_code_count  # nosemgrep
