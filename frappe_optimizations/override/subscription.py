import frappe
from erpnext.accounts.doctype.subscription.subscription import Subscription
from frappe.model.document import Document

if "frappe_affiliate" in frappe.get_installed_apps():
	from frappe_affiliate.override.subscription_override import SubscriptionOverride

	BaseSubscription = SubscriptionOverride
else:
	BaseSubscription = Subscription


class OptimizeSubscriptionOverride(BaseSubscription):
	@property
	def current_invoice(self) -> Document | None:
		"""
		Adds property for accessing the current_invoice
		"""
		if not hasattr(self, "_current_invoice_cache"):
			self._current_invoice_cache = self.get_current_invoice()
		return self._current_invoice_cache

	def get_current_invoice(self) -> Document | None:
		"""
		Returns the most recent generated invoice.
		"""
		invoice = frappe.get_all(
			self.invoice_document_type,
			fields=["name", "to_date"],
			filters={"subscription": self.name, "docstatus": ("<", 2)},
		)

		if invoice:
			invoice = sorted(invoice, key=lambda x: x["to_date"], reverse=True)
			return frappe.get_doc(self.invoice_document_type, invoice[0]["name"])

	@property
	def invoices(self) -> list[dict]:
		invoices = frappe.get_all(
			self.invoice_document_type,
			filters={"subscription": self.name},
			# order_by="from_date asc",
		)

		return sorted(invoices, key=lambda x: x["from_date"])
