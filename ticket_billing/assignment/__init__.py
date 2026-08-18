"""Automatische Ticketzuweisung.

Diese Datei ist der Rahmen: Kandidaten ermitteln, die eingestellte Regel
fragen, Ergebnis anwenden. Die Entscheidung selbst trifft ausschließlich die
Regel (``strategies/``). Wer eine andere Regel will, schreibt eine Klasse und
stellt sie in den Einstellungen ein -- hier ändert sich nichts.
"""

import frappe

from ticket_billing.mail_filter import is_system_sender

from ticket_billing.assignment.base import Candidate
from ticket_billing.assignment.registry import get_strategy
from ticket_billing.constants import (
	FIELD_ASSIGNEE,
	FIELD_DEPARTMENT,
	OPEN_STATUSES,
	ROLE_EMPLOYEE,
)


def get_settings():
	return frappe.get_cached_doc("Ticket Billing Settings")


def get_open_ticket_counts(employees: list[str]) -> dict[str, int]:
	"""Offene Tickets je Mitarbeiter.

	Eine Abfrage für alle -- nicht eine pro Mitarbeiter. Wird auch von den
	Auswertungen genutzt, damit "Auslastung" dort dasselbe heißt wie bei der
	Zuweisung.
	"""
	if not employees:
		return {}

	# Direktes SQL statt frappe.get_all: Aggregatfunktionen sind dort nur
	# noch über eine Dict-Schreibweise erlaubt, die weder Alias noch
	# group_by sauber abbildet. Die Werte gehen parametrisiert hinein.
	rows = frappe.db.sql(
		f"""
		select `{FIELD_ASSIGNEE}` as employee, count(name) as open_tickets
		from `tabIssue`
		where `{FIELD_ASSIGNEE}` in %(employees)s and status in %(statuses)s
		group by `{FIELD_ASSIGNEE}`
		""",
		{"employees": employees, "statuses": list(OPEN_STATUSES)},
		as_dict=True,
	)

	counts = {row.employee: row.open_tickets for row in rows}
	return {emp: counts.get(emp, 0) for emp in employees}


def get_candidates(department: str) -> list[Candidate]:
	"""Zuweisbare Mitarbeiter einer Abteilung.

	Zuweisbar ist, wer aktiv ist, einen aktiven Frappe-Benutzer hat und die
	Rolle für Ticketbearbeitung trägt. Ohne Benutzerkonto kann jemand das
	Ticket nicht bearbeiten -- so jemandem eins zuzuteilen hieße, es
	verschwinden zu lassen.

	Läuft bewusst ohne Rechteprüfung: Die Zuweisung entscheidet im Namen des
	Systems, nicht im Namen dessen, der das Ticket gerade anlegt (das kann
	ein Kunde per E-Mail sein).
	"""
	if not department:
		return []

	role_users = frappe.get_all(
		"Has Role",
		filters={"role": ROLE_EMPLOYEE, "parenttype": "User"},
		pluck="parent",
	)
	if not role_users:
		return []

	active_users = frappe.get_all(
		"User",
		filters={"name": ["in", role_users], "enabled": 1},
		pluck="name",
	)
	if not active_users:
		return []

	employees = frappe.get_all(
		"Employee",
		filters={
			"department": department,
			"status": "Active",
			"user_id": ["in", active_users],
		},
		fields=["name", "employee_name", "user_id"],
	)
	if not employees:
		return []

	counts = get_open_ticket_counts([e.name for e in employees])

	return [
		Candidate(
			employee=e.name,
			employee_name=e.employee_name or e.name,
			user=e.user_id,
			department=department,
			open_tickets=counts.get(e.name, 0),
		)
		for e in employees
	]


def apply_assignment(doc, employee: str, notify: bool = True) -> None:
	"""Mitarbeiter am Ticket eintragen und Frappes eigene Zuweisung setzen.

	Das Feld ist die fachliche Wahrheit; der ToDo-Eintrag sorgt dafür, dass
	das Ticket auch im Desk unter "Mir zugewiesen" und in den
	Benachrichtigungen auftaucht.
	"""
	doc.db_set(FIELD_ASSIGNEE, employee, update_modified=False)

	# db_set löst kein on_update aus -- der Realtime-Hook dort greift hier
	# also nicht. Ohne diese Zeile bekäme der Bearbeiter sein frisch
	# zugewiesenes Ticket erst beim nächsten Neuladen zu sehen.
	from ticket_billing.realtime import publish_ticket

	publish_ticket(doc, "assigned")

	user = frappe.db.get_value("Employee", employee, "user_id")
	if not user:
		return

	try:
		from frappe.desk.form.assign_to import add as assign_to_add

		assign_to_add(
			{
				"assign_to": [user],
				"doctype": doc.doctype,
				"name": doc.name,
				"description": doc.get("subject") or doc.name,
				"notify": 1 if notify else 0,
			}
		)
	except Exception:
		# Der ToDo-Eintrag ist Komfort. Schlägt er fehl (etwa weil schon
		# einer existiert), bleibt die fachliche Zuweisung trotzdem stehen.
		frappe.log_error(
			title="ticket_billing: ToDo-Zuweisung fehlgeschlagen",
			message=frappe.get_traceback(),
		)


def assign_issue(doc, strategy_key: str | None = None) -> str | None:
	"""Ticket nach der eingestellten Regel zuweisen.

	:returns: zugewiesene Employee-ID oder None
	"""
	if doc.get(FIELD_ASSIGNEE):
		return doc.get(FIELD_ASSIGNEE)

	department = doc.get(FIELD_DEPARTMENT)
	if not department:
		return None

	settings = get_settings()
	strategy = get_strategy(strategy_key or settings.assignment_strategy)

	candidates = get_candidates(department)
	employee = strategy.select(doc, candidates)

	if not employee:
		return None

	# Eine Regel darf sich nicht an der Abteilung vorbei entscheiden.
	valid = {c.employee for c in candidates}
	if employee not in valid:
		frappe.log_error(
			title="ticket_billing: Regel lieferte fremden Mitarbeiter",
			message=f"Regel {strategy.key} lieferte {employee}, erlaubt waren {sorted(valid)}",
		)
		return None

	apply_assignment(doc, employee)
	return employee


def auto_assign_on_insert(doc, method=None) -> None:
	"""Hook für ``after_insert`` auf Issue.

	Fängt alles ab: Ein Ticket entsteht auch aus einer eingehenden E-Mail,
	und ein Fehler in der Zuweisung darf den Posteingang nicht blockieren.
	Deshalb wird hier geloggt statt geworfen -- ein unzugewiesenes Ticket ist
	sichtbar und nachträglich zuweisbar, ein verlorenes nicht.
	"""
	try:
		# Ein Rueckläufer vom Mailsystem ist keine Arbeit fuer jemanden.
		# Der Filter raeumt ihn gleich darauf weg; ohne diese Bremse
		# ginge vorher noch eine Zuweisungsmeldung raus.
		if is_system_sender(doc.get("raised_by")):
			return

		settings = get_settings()
		if not settings.auto_assign:
			return

		assign_issue(doc)
	except Exception:
		frappe.log_error(
			title="ticket_billing: automatische Zuweisung fehlgeschlagen",
			message=frappe.get_traceback(),
		)
