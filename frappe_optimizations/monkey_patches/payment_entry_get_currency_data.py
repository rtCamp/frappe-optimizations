import frappe


def get_currency_data(outstanding_refdocs: list, company: str | None = None) -> dict:
	"""Get currency and conversion data for a list of invoices."""
	exc_rates = frappe._dict()
	company_currency = frappe.db.get_value("Company", company, "default_currency") if company else None

	for doctype in ["Sales Invoice", "Purchase Invoice", "Sales Order", "Purchase Order"]:
		refdoc = [x.voucher_no for x in outstanding_refdocs if x.voucher_type == doctype]
		if len(refdoc) == 0:
			continue

		for row in frappe.db.get_all(
			doctype,
			filters={"name": ["in", refdoc]},
			fields=["name", "currency", "conversion_rate", "party_account_currency"],
			ignore_ifnull=True,
		):
			exc_rates[row.name] = frappe._dict(
				conversion_rate=row.conversion_rate,
				currency=row.currency,
				party_account_currency=row.party_account_currency,
				company_currency=company_currency,
			)

	return exc_rates


def get_currency_data_monkey_patch():
	# nosemgrep
	from erpnext.accounts.doctype.payment_entry import payment_entry

	payment_entry.get_currency_data = get_currency_data  # nosemgrep
