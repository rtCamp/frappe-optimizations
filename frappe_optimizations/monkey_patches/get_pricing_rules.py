import frappe
from erpnext.accounts.doctype.pricing_rule.utils import (
	_get_pricing_rules,
	apply_multiple_pricing_rules,
	filter_pricing_rule_based_on_condition,
	filter_pricing_rules,
	sorted_by_priority,
)
from frappe.core.doctype.recorder.recorder import redis_cache


@redis_cache()
def get_cache_total_count_pricing_rules():
	return frappe.db.count("Pricing Rule", cache=True)


def clear_pricing_rule_cache(doc, method=None):
	# Clear the cache for get_pricing_rules function
	get_cache_total_count_pricing_rules.clear_cache()


def get_pricing_rules(args, doc=None):
	pricing_rules = []
	values = {}

	if not get_cache_total_count_pricing_rules():
		return

	for apply_on in ["Item Code", "Item Group", "Brand"]:
		pricing_rules.extend(_get_pricing_rules(apply_on, args, values))
		if pricing_rules and pricing_rules[0].has_priority:
			continue

		if pricing_rules and not apply_multiple_pricing_rules(pricing_rules):
			break

	rules = []

	pricing_rules = filter_pricing_rule_based_on_condition(pricing_rules, doc)

	if not pricing_rules:
		return []

	if apply_multiple_pricing_rules(pricing_rules):
		pricing_rules = sorted_by_priority(pricing_rules, args, doc)
		for pricing_rule in pricing_rules:
			if isinstance(pricing_rule, list):
				rules.extend(pricing_rule)
			else:
				rules.append(pricing_rule)
	else:
		pricing_rule = filter_pricing_rules(args, pricing_rules, doc)
		if pricing_rule:
			rules.append(pricing_rule)

	return rules


def get_pricing_rules_monkey_patch():
	# nosemgrep
	from erpnext.accounts.doctype.pricing_rule import utils

	utils.get_pricing_rules = get_pricing_rules  # nosemgrep
