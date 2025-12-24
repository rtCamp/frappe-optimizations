def initialize_coupon_in_redis(coupon_name):
	import frappe

	cache_key = f"coupon_code:{coupon_name}"

	coupon_data = frappe.db.get_value(
		"Coupon Code",
		coupon_name,
		["name", "used", "maximum_use"],
		as_dict=True,
	)

	if not coupon_data:
		frappe.throw(frappe._("Coupon code not found"))

	current_used = int(frappe.cache.hincrby(cache_key, "used", 0) or 0)
	current_maximum_use = int(frappe.cache.hincrby(cache_key, "maximum_use", 0) or 0)

	target_used = int(coupon_data.get("used") or 0)
	target_maximum_use = int(coupon_data.get("maximum_use") or 0)

	frappe.cache.hincrby(cache_key, "used", target_used - current_used)
	frappe.cache.hincrby(cache_key, "maximum_use", target_maximum_use - current_maximum_use)

	print(
		f"✓ Initialized coupon {coupon_name} in Redis: used={coupon_data.get('used')}, max={coupon_data.get('maximum_use')}"
	)

	return coupon_data


def get_coupon_counter_info(coupon_name):
	import frappe

	cache_key = f"coupon_code:{coupon_name}"
	redis_used = frappe.cache.hincrby(cache_key, "used", 0)
	redis_max = frappe.cache.hincrby(cache_key, "maximum_use", 0)

	info = {
		"coupon_name": coupon_name,
		"redis": {
			"exists": redis_used is not None or redis_max is not None,
			"used": int(redis_used) if redis_used is not None else None,
			"maximum_use": int(redis_max) if redis_max is not None else None,
		},
	}

	return info


def update_coupon_code_count(coupon_name, transaction_type):
	import frappe

	cache_key = f"coupon_code:{coupon_name}"

	if transaction_type == "used":
		redis_conn = frappe.cache

		# Lua script for atomic check-and-increment
		# This runs on Redis server, so it's truly atomic even with 500 concurrent requests
		lua_script = """
		local cache_key = KEYS[1]
		local current_used = tonumber(redis.call('HGET', cache_key, 'used') or 0)
		local maximum_use = tonumber(redis.call('HGET', cache_key, 'maximum_use') or 0)

		if maximum_use==0 or current_used < maximum_use then
			redis.call('HINCRBY', cache_key, 'used', 1)
			return current_used + 1
		else
			return -1
		end
		"""

		new_used_count = redis_conn.eval(lua_script, 1, cache_key)

		if new_used_count == -1:
			return frappe.throw(frappe._("Coupon code has reached its maximum usage limit"))

		def rollback_increment():
			frappe.cache.hincrby(cache_key, "used", -1)

		frappe.db.after_rollback.add(rollback_increment)

	elif transaction_type == "cancelled":
		current_used = int(frappe.cache.hget(cache_key, "used") or 0)

		if current_used > 0:
			new_used_count = frappe.cache.hincrby(cache_key, "used", -1)
			print(f"✓ Coupon {coupon_name} decremented to: {new_used_count}")
		else:
			print(f"⚠ Coupon {coupon_name} already at 0, cannot decrement")


def update_coupon_code_count_monkey_patch():
	# nosemgrep
	from erpnext.accounts.doctype.pricing_rule import utils

	utils.update_coupon_code_count = update_coupon_code_count  # nosemgrep

	# nosemgrep
	from erpnext.accounts.doctype.sales_invoice import sales_invoice

	sales_invoice.update_coupon_code_count = update_coupon_code_count  # nosemgrep
