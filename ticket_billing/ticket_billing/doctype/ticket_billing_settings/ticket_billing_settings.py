import frappe
from frappe import _
from frappe.model.document import Document

from ticket_billing.assignment.registry import is_registered, list_strategies


class TicketBillingSettings(Document):
	def validate(self):
		self.validate_strategy()

	def validate_strategy(self):
		"""Nur eingetragene Regeln zulassen.

		Ein Tippfehler hier führte sonst erst beim nächsten eingehenden
		Ticket zu einem Fehler -- also genau dann, wenn niemand hinschaut.
		"""
		if is_registered(self.assignment_strategy):
			return

		available = ", ".join(s["key"] for s in list_strategies()) or "-"
		frappe.throw(
			_("Unknown assignment strategy {0}. Available: {1}").format(
				frappe.bold(self.assignment_strategy), available
			)
		)
