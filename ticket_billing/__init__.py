__version__ = "0.0.1"


def check_app_permission() -> bool:
	"""Darf dieser Benutzer die App im Umschalter sehen?

	Nur wer eine der Ticket-Rollen hat. Ohne die Pruefung erschiene die
	Kachel bei jedem Desk-Benutzer -- auch bei einem Buchhalter, der mit
	Tickets nichts zu tun hat und hinter der Kachel nur eine leere Liste
	faende.
	"""
	import frappe

	from ticket_billing.constants import TICKET_ROLES, UNRESTRICTED_ROLES

	if frappe.session.user == "Administrator":
		return True

	rollen = set(frappe.get_roles())
	return bool(rollen & set(TICKET_ROLES + UNRESTRICTED_ROLES))
