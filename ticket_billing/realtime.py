"""Realtime-Ereignisse an die Oberfläche.

Frappe verteilt Ereignisse über Räume. Hier wird ausschließlich in
**Benutzerräume** gesendet (``publish_realtime(..., user=...)``) und die
Empfängerliste vorher serverseitig bestimmt. Der Grund ist ein
Sicherheitsgrund: Ein Ereignis in einem Raum, den der Client selbst abonniert,
wäre nur so dicht wie die Raumverwaltung. Wer die Empfänger vorher ausrechnet,
kann niemandem etwas zustellen, das er nicht ohnehin sehen dürfte.

Deshalb enthalten die Nutzdaten auch nur, was in der Liste ohnehin steht --
Nummer, Betreff, Status. Keine Beschreibung, keine Kundendaten.
"""

import frappe

from ticket_billing.constants import (
	CLOSED_STATUSES,
	FIELD_ASSIGNEE,
	FIELD_DEPARTMENT,
	FIELD_ORIGIN,
	ROLE_LEAD,
)

#: Änderung an einem Ticket (angelegt, zugewiesen, Status geändert).
EVENT_TICKET = "ticket_billing:ticket"
#: Zustand des eigenen Timers -- damit ein zweites Gerät nachzieht.
EVENT_TIMER = "ticket_billing:timer"


def _user_of(employee: str | None) -> str | None:
	if not employee:
		return None
	return frappe.db.get_value("Employee", employee, "user_id")


def get_department_leads(department: str) -> list[str]:
	"""Benutzerkonten der Abteilungsleitung einer Abteilung.

	Sie sehen alle Vorgänge ihrer Abteilung, also gehen Änderungen daran auch
	dann an sie, wenn das Ticket jemand anderem gehört.
	"""
	if not department:
		return []

	employees = frappe.get_all(
		"Employee",
		filters={"department": department, "status": "Active", "user_id": ["!=", ""]},
		pluck="user_id",
	)
	if not employees:
		return []

	return frappe.get_all(
		"Has Role",
		filters={"role": ROLE_LEAD, "parenttype": "User", "parent": ["in", employees]},
		pluck="parent",
	)


def get_ticket_recipients(doc, previous_assignee: str | None = None) -> list[str]:
	"""Wer über eine Änderung an diesem Ticket informiert wird.

	Der vorherige Bearbeiter ist bewusst dabei: Nach einer Umverteilung soll
	das Ticket aus seiner Liste verschwinden, und ohne Ereignis merkte er das
	erst beim nächsten Neuladen.
	"""
	users = {
		_user_of(doc.get(FIELD_ASSIGNEE)),
		_user_of(previous_assignee),
		doc.get("owner"),
	}
	users.update(get_department_leads(doc.get(FIELD_DEPARTMENT)))

	return sorted(u for u in users if u and u != "Guest")


def _payload(doc, kind: str, previous_assignee: str | None = None) -> dict:
	return {
		"kind": kind,
		"name": doc.name,
		"subject": doc.get("subject"),
		"status": doc.get("status"),
		"is_open": doc.get("status") not in CLOSED_STATUSES,
		"department": doc.get(FIELD_DEPARTMENT),
		"origin": doc.get(FIELD_ORIGIN),
		"assignee": doc.get(FIELD_ASSIGNEE),
		"assignee_name": frappe.db.get_value(
			"Employee", doc.get(FIELD_ASSIGNEE), "employee_name"
		)
		if doc.get(FIELD_ASSIGNEE)
		else None,
		"previous_assignee": previous_assignee,
		"by": frappe.session.user,
	}


def publish_ticket(doc, kind: str, previous_assignee: str | None = None) -> None:
	"""Ticketänderung an alle Betroffenen senden.

	``after_commit``: Ohne das ginge das Ereignis auch dann raus, wenn die
	Transaktion danach zurückgerollt wird -- die Oberfläche zeigte dann eine
	Änderung, die es nicht gibt.

	Fehler werden geschluckt: Realtime ist Komfort. Wenn der Socket-Dienst
	klemmt, darf daran kein Ticket scheitern.
	"""
	try:
		payload = _payload(doc, kind, previous_assignee)
		for user in get_ticket_recipients(doc, previous_assignee):
			frappe.publish_realtime(
				EVENT_TICKET, payload, user=user, after_commit=True
			)
	except Exception:
		frappe.log_error(
			title="ticket_billing: Realtime-Ereignis fehlgeschlagen",
			message=frappe.get_traceback(),
		)


def publish_timer(user: str, timer: dict | None) -> None:
	"""Timerzustand an den eigenen Benutzer -- für weitere offene Geräte."""
	try:
		frappe.publish_realtime(
			EVENT_TIMER, {"timer": timer}, user=user, after_commit=True
		)
	except Exception:
		frappe.log_error(
			title="ticket_billing: Realtime-Timerereignis fehlgeschlagen",
			message=frappe.get_traceback(),
		)


# ---------------------------------------------------------------------------
# Doc-Hook
# ---------------------------------------------------------------------------


def on_issue_update(doc, method=None):
	"""Hook für ``on_update`` auf Issue.

	Sendet nur, wenn sich etwas geändert hat, das eine Liste betrifft. Ohne
	diese Einschränkung löste jedes Speichern -- auch das der Beschreibung --
	bei allen Beteiligten ein Nachladen aus.
	"""
	watched = ("status", FIELD_ASSIGNEE, FIELD_DEPARTMENT, "subject", "priority")
	changed = [f for f in watched if doc.has_value_changed(f)]
	if not changed:
		return

	previous = None
	if doc.has_value_changed(FIELD_ASSIGNEE):
		before = doc.get_doc_before_save()
		previous = before.get(FIELD_ASSIGNEE) if before else None

	kind = "assigned" if FIELD_ASSIGNEE in changed else "updated"
	publish_ticket(doc, kind, previous)


def on_inbound_communication(doc, method=None):
	"""Hook für ``after_insert`` auf Communication.

	Ohne dieses Ereignis faellt eine Kundenantwort erst beim naechsten
	Neuladen auf -- der Bearbeiter sieht die Liste, in der sich scheinbar
	nichts getan hat.

	Laeuft nach dem Rueckläufer-Filter, damit die Meldung am richtigen
	Ticket haengt.
	"""
	if doc.sent_or_received != "Received" or doc.reference_doctype != "Issue":
		return
	if not doc.reference_name or not frappe.db.exists("Issue", doc.reference_name):
		return

	publish_ticket(frappe.get_doc("Issue", doc.reference_name), "reply")
