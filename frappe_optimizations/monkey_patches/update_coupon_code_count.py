def update_coupon_code_count(coupon_name, transaction_type):
	import frappe

	if transaction_type == "used":
		cache_key = f"coupon_code_count:{coupon_name}"
		lock_key = f"coupon_code_lock:{coupon_name}"
		BATCH_SIZE = 100
		coupon_data = frappe.cache.hget(cache_key, "data")

		if not coupon_data:
			coupon_data = frappe.db.get_value(
				"Coupon Code",
				coupon_name,
				["used", "maximum_use"],
				as_dict=True,
			)
			if coupon_data:
				frappe.cache.hset(cache_key, "data", coupon_data)
				frappe.cache.hset(cache_key, "pending_count", 0)
			else:
				frappe.throw(frappe._("Invalid coupon code"))

		new_pending_count = frappe.cache.hincrby(cache_key, "pending_count", 1)

		frappe.db.after_rollback.add(lambda: frappe.cache.hincrby(cache_key, "pending_count", -1))

		used = coupon_data.get("used") or 0
		total_used = used + new_pending_count
		maximum_use = coupon_data.get("maximum_use") or 0

		if maximum_use and total_used > maximum_use:
			frappe.cache.hincrby(cache_key, "pending_count", -1)
			frappe.throw(frappe._("Coupon code is no longer available or has reached its usage limit"))

		lock_acquired = frappe.cache.set_value(lock_key, "1", nx=True, ex=5)

		if new_pending_count >= BATCH_SIZE and lock_acquired:
			flush_count = new_pending_count

			old_coupon_data = coupon_data.copy()

			frappe.cache.hincrby(cache_key, "pending_count", -flush_count)

			coupon_data["used"] = used + flush_count
			frappe.cache.hset(cache_key, "data", coupon_data)

			def rollback_flush():
				frappe.cache.hincrby(cache_key, "pending_count", flush_count)
				frappe.cache.hset(cache_key, "data", old_coupon_data)

			frappe.db.after_rollback.add(rollback_flush)

			frappe.db.sql(
				"""
				UPDATE `tabCoupon Code`
				SET used = used + %s, modified = %s
				WHERE name = %s
				""",
				(flush_count, frappe.utils.now(), coupon_name),
			)

			print(f"Flushed {flush_count} pending updates for coupon {coupon_name}")

		if lock_acquired:
			frappe.cache.hdel(lock_key, "1")

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
