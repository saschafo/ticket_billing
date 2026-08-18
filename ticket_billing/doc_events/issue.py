"""Regeln, die für jedes Ticket gelten -- egal, woher es kommt.

Diese Hooks laufen für die Oberfläche, für die API und für Tickets, die
ERPNext aus eingehenden E-Mails erzeugt. Deshalb steht die Logik hier und
nicht in den API-Endpunkten: Ein Weg an den Regeln vorbei wäre ein Weg an den
Rechten vorbei.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from ticket_billing.constants import (
	CLOSED_STATUSES,
	FIELD_ASSIGNEE,
	FIELD_DEPARTMENT,
	FIELD_EMAIL_DEPARTMENT,
	FIELD_FIRST_RESPONSE,
	FIELD_ORIGIN,
	FIELD_RESOLVED,
	ORIGIN_EXTERNAL,
	ORIGIN_INTERNAL,
)
from ticket_billing.utils.context import is_lead, is_unrestricted


def before_validate(doc, method=None):
	set_department(doc)
	set_origin(doc)


def validate(doc, method=None):
	validate_customer(doc)
	validate_assignee(doc)
	track_status_timestamps(doc)


def track_status_timestamps(doc):
	"""Zeitpunkte für Reaktions- und Lösungszeit festhalten.

	ERPNext führt zwar ``first_responded_on`` und ``sla_resolution_date``,
	füllt sie aber nur über die SLA-Funktion. Ohne konfiguriertes Service
	Level Agreement bleiben sie leer -- und damit auch die Kennzahlen, die
	darauf aufbauen. Diese beiden Stempel hängen an nichts weiter als dem
	Statuswechsel.

	Wird ein erledigtes Ticket wieder geöffnet, verfällt der Lösungszeitpunkt.
	Sonst zählte die Lösungszeit einen Stand, der nicht mehr gilt.
	"""
	if doc.is_new():
		return

	if not doc.has_value_changed("status"):
		return

	now = now_datetime()

	if not doc.get(FIELD_FIRST_RESPONSE):
		doc.set(FIELD_FIRST_RESPONSE, now)

	if doc.status in CLOSED_STATUSES:
		if not doc.get(FIELD_RESOLVED):
			doc.set(FIELD_RESOLVED, now)
	else:
		doc.set(FIELD_RESOLVED, None)


def set_department(doc):
	"""Zuständige Abteilung bestimmen, falls noch keine gesetzt ist.

	Reihenfolge: was am Ticket steht, sonst die Abteilung des Postfachs,
	sonst die Standardabteilung. Ohne diese Kette würde jedes per E-Mail
	erzeugte Ticket am Pflichtfeld scheitern -- und eine Mail, die kein
	Ticket wird, fällt niemandem auf.
	"""
	# Das Postfach hat Vorrang vor dem, was schon im Feld steht -- und zwar
	# bewusst. Frappe belegt Link-Felder aus den Benutzerrechten vor: Wer
	# genau eine Abteilung sehen darf, bekommt sie beim Anlegen eingetragen.
	# Ruft ein Mitarbeiter die Post ab, entstuende das Ticket dadurch in
	# SEINER Abteilung statt in der des Postfachs. Eine Vorbelegung ist
	# keine Entscheidung.
	if doc.get("email_account"):
		from_inbox = frappe.db.get_value(
			"Email Account", doc.email_account, FIELD_EMAIL_DEPARTMENT
		)
		if from_inbox:
			doc.set(FIELD_DEPARTMENT, from_inbox)
			return

	if doc.get(FIELD_DEPARTMENT):
		return

	default = frappe.db.get_single_value("Ticket Billing Settings", "default_department")
	if default:
		doc.set(FIELD_DEPARTMENT, default)
		return

	frappe.throw(
		_(
			"No department could be determined for this ticket. "
			"Set a department on the ticket, on the email account, "
			"or configure a default department in Ticket Billing Settings."
		),
		title=_("Department missing"),
	)


def is_internal_sender(address: str | None) -> bool:
	"""Kommt die Mail aus dem eigenen Haus?

	Drei Wege, absteigend nach Verlässlichkeit: Die Adresse ist eines
	unserer eigenen Postfächer, sie gehört einem Benutzer des Systems, oder
	sie liegt auf derselben Domain wie eines unserer Postfächer.
	"""
	address = (address or "").strip().lower()
	if not address:
		return False

	if frappe.db.exists("Email Account", {"email_id": address}):
		return True

	# Mitarbeiter, nicht Benutzer: Ein Kunde mit Portalzugang ist auch ein
	# Benutzer, gehört aber nicht ins Haus. Die Unterscheidung entscheidet
	# darüber, ob Zeiten abgerechnet werden.
	if frappe.db.exists("Employee", {"user_id": address, "status": "Active"}):
		return True

	domain = address.rpartition("@")[2]
	if not domain:
		return False

	eigene = {
		(adresse or "").rpartition("@")[2].lower()
		for adresse in frappe.get_all("Email Account", pluck="email_id")
	}
	return domain in eigene


def set_origin(doc):
	"""Herkunft ableiten, falls nicht gesetzt.

	Nicht jede Mail kommt von außen: Eine Abteilung, die einer anderen
	schreibt, ist Hausverkehr. Vorher galt allein die Absenderadresse als
	Beweis für "extern" -- eine Anfrage von support@ an buchhaltung@ wurde
	dadurch als Kundenanfrage geführt.

	Das entscheidet mehr als eine Beschriftung: Zeiten auf externen Tickets
	gehen als abrechenbar in die Rechnungsstellung, interne nicht.
	"""
	if doc.get(FIELD_ORIGIN):
		return

	absender = doc.get("raised_by")
	if not doc.get("email_account") and not absender:
		# In der Anwendung angelegt, ohne jeden Mailbezug.
		doc.set(FIELD_ORIGIN, ORIGIN_INTERNAL)
		return

	intern = is_internal_sender(absender)
	doc.set(FIELD_ORIGIN, ORIGIN_INTERNAL if intern else ORIGIN_EXTERNAL)


def validate_customer(doc):
	"""Kunde nur bei externer Herkunft."""
	if doc.get(FIELD_ORIGIN) == ORIGIN_INTERNAL and doc.get("customer"):
		frappe.throw(
			_("A customer can only be set on external tickets."),
			title=_("Invalid customer"),
		)


def validate_assignee(doc):
	"""Zuweisung prüfen: passende Abteilung, und wer sie ändern darf."""
	assignee = doc.get(FIELD_ASSIGNEE)

	if doc.is_new():
		# Beim Anlegen entscheidet die Zuweisungsregel. Wer nicht umverteilen
		# darf, kann sich ein Ticket also nicht selbst zuschanzen.
		if assignee and not (is_lead() or is_unrestricted()):
			doc.set(FIELD_ASSIGNEE, None)
			return
	elif doc.has_value_changed(FIELD_ASSIGNEE) and not (is_lead() or is_unrestricted()):
		frappe.throw(
			_("Only the department lead can reassign a ticket."),
			frappe.PermissionError,
			title=_("Not allowed"),
		)

	assignee = doc.get(FIELD_ASSIGNEE)
	if not assignee:
		return

	employee_department = frappe.db.get_value("Employee", assignee, "department")
	if employee_department != doc.get(FIELD_DEPARTMENT):
		frappe.throw(
			_("{0} is not a member of department {1}.").format(
				frappe.bold(frappe.db.get_value("Employee", assignee, "employee_name") or assignee),
				frappe.bold(doc.get(FIELD_DEPARTMENT)),
			),
			title=_("Invalid assignment"),
		)
