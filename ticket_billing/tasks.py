"""Zeitgesteuerte Aufgaben."""

from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import add_days, flt, nowdate

from ticket_billing.realtime import get_department_leads


@contextmanager
def _user_language(user: str):
	"""Texte vorübergehend in der Sprache eines bestimmten Benutzers erzeugen."""
	previous = frappe.local.lang
	try:
		lang = frappe.db.get_value("User", user, "language")
		frappe.local.lang = lang or frappe.db.get_default("lang") or "en"
		yield
	finally:
		frappe.local.lang = previous


def notify_pending_timesheets():
	"""Täglicher Hinweis an die Abteilungsleitung auf liegengebliebene Entwürfe.

	Erfasste, aber nie gebuchte Zeit fällt niemandem auf -- sie steht in
	keiner Auswertung und in keiner Rechnung. Deshalb einmal am Tag ein
	Hinweis, sobald ein Entwurf älter ist als die eingestellte Frist.

	Es wird eine Frappe-Benachrichtigung erzeugt, kein E-Mail-Versand: Die
	erscheint im Desk und braucht keinen konfigurierten Mailausgang.
	"""
	days = frappe.db.get_single_value("Ticket Billing Settings", "draft_reminder_days")
	days = int(days or 3)
	cutoff = add_days(nowdate(), -days)

	rows = frappe.db.sql(
		"""
		select department, count(name) as entries, sum(total_hours) as hours
		from `tabTimesheet`
		where docstatus = 0
		  and department is not null and department != ''
		  and creation < %(cutoff)s
		group by department
		""",
		{"cutoff": cutoff},
		as_dict=True,
	)

	for row in rows:
		leads = get_department_leads(row.department)
		if not leads:
			# Ohne Leitung gibt es niemanden, der buchen könnte. Das ist ein
			# Einrichtungsfehler und gehört ins Log, nicht ins Nichts.
			frappe.log_error(
				title="ticket_billing: Entwürfe ohne Abteilungsleitung",
				message=f"{row.entries} offene Zeiteinträge in {row.department}, "
				"aber kein Benutzer mit der Rolle Abteilungsleiter.",
			)
			continue

		for user in leads:
			# Sprache je Empfänger. Ein Hintergrundjob hat keine
			# Sitzungssprache -- ohne das käme der Hinweis in der Sprache
			# heraus, in der der Scheduler zufällig läuft, und nicht in der
			# des Lesers.
			with _user_language(user):
				subject = _("{0} time entries in {1} are waiting to be submitted").format(
					row.entries, row.department
				)
				message = _(
					"Oldest entries are more than {0} days old. Total: {1} hours."
				).format(days, flt(row.hours, 2))

			frappe.get_doc(
				{
					"doctype": "Notification Log",
					"for_user": user,
					"type": "Alert",
					"subject": subject,
					"email_content": message,
					"document_type": "Timesheet",
				}
			).insert(ignore_permissions=True)

	frappe.db.commit()
