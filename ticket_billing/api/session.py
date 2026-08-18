"""Sitzungsdaten für die Oberfläche.

Liefert das, woraus die Vue-Seite entscheidet, welchen Bereich sie zeigt.
Die Rollen kommen dabei aus Frappe -- die Oberfläche wertet sie nur aus.
Verlassen darf sie sich darauf nicht: Jeder Endpunkt prüft eigenständig, was
der Aufrufer sehen darf. Was hier steht, steuert nur die Darstellung.

Serverseitige Texte laufen durch ``frappe._()``, damit ``bench
get-untranslated`` sie einsammelt und spätere Sprachen ohne Code-Änderung
dazukommen.
"""

import frappe
from frappe import _

from ticket_billing.constants import ROLE_EMPLOYEE, ROLE_LEAD, ROLE_MANAGEMENT
from ticket_billing.utils.context import (
	get_access_level,
	get_employee,
	get_scope_departments,
)


@frappe.whitelist()
def get_session_info():
	"""Benutzer, Rollen, Abteilung und Sprache der aktuellen Sitzung."""
	user = frappe.session.user

	if user == "Guest":
		return {
			"user": "Guest",
			"full_name": _("Guest"),
			"roles": [],
			"access_level": "none",
			"employee": None,
			"department": None,
			"lang": frappe.local.lang or "de",
		}

	roles = frappe.get_roles(user)
	employee = get_employee(user)
	departments = get_scope_departments(user)
	department = departments[0] if departments else None

	employee_row = None
	if employee:
		employee_row = frappe.db.get_value(
			"Employee", employee, ["employee_name", "company"], as_dict=True
		)

	return {
		"user": user,
		"full_name": frappe.utils.get_fullname(user),
		"roles": roles,
		"access_level": get_access_level(user),
		"is_employee": ROLE_EMPLOYEE in roles,
		"is_lead": ROLE_LEAD in roles,
		"is_management": ROLE_MANAGEMENT in roles,
		"employee": employee,
		"employee_name": employee_row.employee_name if employee_row else None,
		"company": employee_row.company if employee_row else None,
		"department": department,
		"departments": departments,
		"lang": frappe.local.lang or "de",
		# Frappe sendet Realtime-Ereignisse in den Namespace "/<sitename>".
		# Der interne Site-Name muss nicht der Domain entsprechen, unter der
		# die Anwendung erreichbar ist -- der Client kann ihn also nicht aus
		# der URL ableiten und bekommt ihn hier.
		"sitename": frappe.local.site,
	}


@frappe.whitelist()
def get_available_languages():
	"""Sprachen, die auf dieser Site eingerichtet sind."""
	rows = frappe.get_all(
		"Language",
		filters={"enabled": 1},
		fields=["name", "language_name"],
		order_by="language_name asc",
	)
	return [{"code": r.name, "label": r.language_name or r.name} for r in rows]


@frappe.whitelist()
def set_user_language(lang: str):
	"""Sprache dauerhaft am Benutzer speichern.

	Die Oberfläche schaltet vue-i18n selbst um; das hier sorgt dafür, dass
	auch serverseitig erzeugte Texte -- Fehlermeldungen, E-Mails, PDFs --
	derselben Wahl folgen.
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to change the language."), frappe.PermissionError)

	if not frappe.db.exists("Language", lang):
		frappe.throw(_("Language {0} is not available.").format(lang))

	frappe.db.set_value("User", frappe.session.user, "language", lang)
	frappe.local.lang = lang
	frappe.clear_cache(user=frappe.session.user)

	return {"lang": lang}
