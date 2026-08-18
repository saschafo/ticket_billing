"""API rund um Tickets.

Zwei Regeln gelten hier durchgehend:

1. Gelesen wird mit ``frappe.get_list`` -- das wendet die Bedingungen aus
   ``permissions.py`` an. ``frappe.get_all`` umgeht sie und darf nur nach
   einer eigenen, expliziten Prüfung verwendet werden.
2. Geschrieben wird über Dokumente, nicht über die Datenbank. Damit laufen
   die Hooks aus ``doc_events`` mit -- inklusive der Prüfung, wer umverteilen
   darf.

Alle Endpunkte nehmen benannte Parameter statt eines Datenpakets. Ein
durchgereichtes Dictionary hieße, dass der Aufrufer bestimmt, welche Felder er
schreibt -- und damit könnte er sich ein Ticket selbst zuweisen.
"""

import frappe
from frappe import _

from ticket_billing.constants import (
	CLOSED_STATUSES,
	FIELD_ASSIGNEE,
	FIELD_DEPARTMENT,
	FIELD_ORIGIN,
	OPEN_STATUSES,
	ORIGIN_EXTERNAL,
	ORIGIN_INTERNAL,
)
from ticket_billing.utils.context import (
	get_access_level,
	get_employee,
	get_scope_departments,
	is_lead,
	is_unrestricted,
)

LIST_FIELDS = [
	"name",
	"subject",
	"status",
	"priority",
	"issue_type",
	"customer",
	"opening_date",
	"creation",
	"modified",
	FIELD_DEPARTMENT,
	FIELD_ORIGIN,
	FIELD_ASSIGNEE,
]

EDITABLE_FIELDS = ("subject", "description", "status", "priority", "issue_type")


def _employee_names(employee_ids: list[str]) -> dict[str, str]:
	ids = [e for e in set(employee_ids) if e]
	if not ids:
		return {}

	rows = frappe.get_all(
		"Employee", filters={"name": ["in", ids]}, fields=["name", "employee_name"]
	)
	return {r.name: r.employee_name or r.name for r in rows}


def _conversation_state(names: list[str]) -> dict[str, dict]:
	"""Je Ticket der Zeitpunkt der letzten ein- und ausgehenden Nachricht.

	Eine Abfrage fuer die ganze Seite statt einer je Zeile: Bei 200 Tickets
	waere das sonst 200-mal Datenbank, nur um ein Kennzeichen zu setzen.
	"""
	names = [n for n in names if n]
	if not names:
		return {}

	rows = frappe.db.sql(
		"""
		select reference_name, sent_or_received,
		       max(creation) as last_on, count(*) as messages
		from `tabCommunication`
		where reference_doctype = 'Issue'
		  and communication_type = 'Communication'
		  and reference_name in %(names)s
		group by reference_name, sent_or_received
		""",
		{"names": tuple(names)},
		as_dict=True,
	)

	state: dict[str, dict] = {}
	for row in rows:
		entry = state.setdefault(row.reference_name, {})
		key = "inbound" if row.sent_or_received == "Received" else "outbound"
		entry[key] = row.last_on
		entry[f"{key}_count"] = row.messages
	return state


def _decorate(rows: list[dict]) -> list[dict]:
	names = _employee_names([r.get(FIELD_ASSIGNEE) for r in rows])
	conversation = _conversation_state([r.get("name") for r in rows])

	for row in rows:
		row["assignee_name"] = names.get(row.get(FIELD_ASSIGNEE))
		row["is_open"] = row.get("status") not in CLOSED_STATUSES

		state = conversation.get(row.get("name"), {})
		inbound, outbound = state.get("inbound"), state.get("outbound")

		row["last_inbound_on"] = inbound
		# Nicht die Eroeffnung, sondern eine Nachricht danach. Beides zaehlt:
		# eine gesendete Antwort davor, oder schlicht eine zweite Mail des
		# Ausstellers -- ein Ticket kann auch ohne Mailverkehr bearbeitet
		# worden sein, und dann waere die Rueckfrage sonst unsichtbar.
		row["is_follow_up"] = bool(
			state.get("outbound_count") or (state.get("inbound_count") or 0) > 1
		)
		# Am Zug sind wir, wenn die juengste Nachricht von aussen kam.
		# Geschlossene Tickets bleiben aussen vor -- dort ist nichts mehr zu
		# tun, auch wenn zuletzt der Kunde geschrieben hat.
		row["awaiting_reply"] = bool(
			inbound and (not outbound or inbound > outbound) and row["is_open"]
		)
	return rows


def require_department_access(department: str) -> None:
	"""Zugriff auf eine ganze Abteilung -- nur Leitung und Geschäftsführung."""
	if is_unrestricted():
		return

	if is_lead() and department in get_scope_departments():
		return

	frappe.throw(
		_("You are not allowed to access department {0}.").format(department),
		frappe.PermissionError,
	)


@frappe.whitelist()
def list_tickets(
	status: str | None = None,
	department: str | None = None,
	origin: str | None = None,
	assignee: str | None = None,
	search: str | None = None,
	only_open: int | str = 0,
	limit_start: int | str = 0,
	limit_page_length: int | str = 50,
	order_by: str = "modified desc",
):
	"""Tickets im Rahmen der eigenen Berechtigung.

	Es wird bewusst nicht geprüft, ob der Aufrufer die gewünschte Abteilung
	sehen darf: ``get_list`` filtert ohnehin. Ein Filter auf eine fremde
	Abteilung liefert damit eine leere Liste statt eines Fehlers -- und
	verrät so auch nicht, ob es dort Tickets gäbe.
	"""
	filters: dict = {}

	if status:
		filters["status"] = status
	elif frappe.utils.cint(only_open):
		filters["status"] = ["in", list(OPEN_STATUSES)]

	if department:
		filters[FIELD_DEPARTMENT] = department
	if origin:
		filters[FIELD_ORIGIN] = origin
	if assignee:
		filters[FIELD_ASSIGNEE] = assignee

	or_filters = None
	if search:
		or_filters = {"name": ["like", f"%{search}%"], "subject": ["like", f"%{search}%"]}

	# Nur erlaubte Sortierspalten -- order_by geht ungefiltert in SQL.
	allowed_order = {
		"modified desc", "modified asc",
		"creation desc", "creation asc",
		"status asc", "status desc",
		"priority asc", "priority desc",
	}
	if order_by not in allowed_order:
		order_by = "modified desc"

	rows = frappe.get_list(
		"Issue",
		filters=filters,
		or_filters=or_filters,
		fields=LIST_FIELDS,
		order_by=order_by,
		limit_start=frappe.utils.cint(limit_start),
		limit_page_length=frappe.utils.cint(limit_page_length),
	)

	total = frappe.get_list(
		"Issue", filters=filters, or_filters=or_filters, limit_page_length=0, as_list=True
	)

	return {
		"rows": _decorate(rows),
		"total": len(total),
		"access_level": get_access_level(),
	}


@frappe.whitelist()
def get_ticket(name: str):
	"""Ein Ticket samt Zeiteinträgen."""
	if not frappe.has_permission("Issue", "read", doc=name):
		raise frappe.PermissionError

	doc = frappe.get_doc("Issue", name)

	assignee_name = None
	if doc.get(FIELD_ASSIGNEE):
		assignee_name = frappe.db.get_value("Employee", doc.get(FIELD_ASSIGNEE), "employee_name")

	from ticket_billing.api.timesheet import get_entries_for_issue

	return {
		"conversation": get_conversation(name),
		"name": doc.name,
		"subject": doc.subject,
		"description": doc.description,
		"status": doc.status,
		"priority": doc.priority,
		"issue_type": doc.issue_type,
		"customer": doc.customer,
		"raised_by": doc.raised_by,
		"opening_date": doc.opening_date,
		"creation": doc.creation,
		"modified": doc.modified,
		FIELD_DEPARTMENT: doc.get(FIELD_DEPARTMENT),
		FIELD_ORIGIN: doc.get(FIELD_ORIGIN),
		FIELD_ASSIGNEE: doc.get(FIELD_ASSIGNEE),
		"assignee_name": assignee_name,
		"is_open": doc.status not in CLOSED_STATUSES,
		"can_write": frappe.has_permission("Issue", "write", doc=doc),
		"can_reassign": is_lead() or is_unrestricted(),
		"time_entries": get_entries_for_issue(name),
	}


@frappe.whitelist()
def create_ticket(
	subject: str,
	department: str,
	description: str | None = None,
	origin: str = ORIGIN_INTERNAL,
	customer: str | None = None,
	priority: str | None = None,
	issue_type: str | None = None,
):
	"""Ticket anlegen.

	Bewusst ohne Abteilungsprüfung: Interne Anfragen gehen gerade an *andere*
	Abteilungen. Die Zuweisung übernimmt danach der after_insert-Hook.
	"""
	if not frappe.has_permission("Issue", "create"):
		raise frappe.PermissionError

	if origin not in (ORIGIN_INTERNAL, ORIGIN_EXTERNAL):
		frappe.throw(_("Invalid origin {0}.").format(origin))

	if origin == ORIGIN_INTERNAL and customer:
		frappe.throw(_("A customer can only be set on external tickets."))

	doc = frappe.get_doc(
		{
			"doctype": "Issue",
			"subject": subject,
			"description": description,
			FIELD_DEPARTMENT: department,
			FIELD_ORIGIN: origin,
			"customer": customer if origin == ORIGIN_EXTERNAL else None,
			"priority": priority,
			"issue_type": issue_type,
		}
	)
	doc.insert()

	return get_ticket(doc.name)


@frappe.whitelist()
def update_ticket(
	name: str,
	subject: str | None = None,
	description: str | None = None,
	status: str | None = None,
	priority: str | None = None,
	issue_type: str | None = None,
):
	"""Ticket bearbeiten -- nur die fachlich freigegebenen Felder.

	Abteilung und Zuweisung stehen bewusst nicht in der Liste: Sie ändern,
	wer das Ticket sieht, und laufen deshalb über eigene Endpunkte mit
	eigener Prüfung.
	"""
	if not frappe.has_permission("Issue", "write", doc=name):
		raise frappe.PermissionError

	doc = frappe.get_doc("Issue", name)

	values = {
		"subject": subject,
		"description": description,
		"status": status,
		"priority": priority,
		"issue_type": issue_type,
	}
	for field, value in values.items():
		if value is not None and field in EDITABLE_FIELDS:
			doc.set(field, value)

	doc.save()

	return get_ticket(doc.name)


@frappe.whitelist()
def reassign_ticket(name: str, employee: str):
	"""Ticket manuell einem anderen Mitarbeiter geben.

	Nur für die Leitung der zuständigen Abteilung. Die Prüfung, ob der
	Mitarbeiter überhaupt zu der Abteilung gehört, macht der validate-Hook --
	damit sie auch für Änderungen aus dem Desk gilt.
	"""
	if not frappe.has_permission("Issue", "write", doc=name):
		raise frappe.PermissionError

	doc = frappe.get_doc("Issue", name)
	require_department_access(doc.get(FIELD_DEPARTMENT))

	previous = doc.get(FIELD_ASSIGNEE)
	doc.set(FIELD_ASSIGNEE, employee)
	doc.save()

	# Frappes eigene Zuweisung nachziehen, damit "Mir zugewiesen" im Desk und
	# die Benachrichtigungen zum Feld passen.
	_sync_todo(doc, previous, employee)

	return get_ticket(doc.name)


def _sync_todo(doc, previous: str | None, employee: str) -> None:
	from frappe.desk.form.assign_to import add as assign_to_add
	from frappe.desk.form.assign_to import remove as assign_to_remove

	try:
		if previous and previous != employee:
			previous_user = frappe.db.get_value("Employee", previous, "user_id")
			if previous_user:
				assign_to_remove(doc.doctype, doc.name, previous_user)

		new_user = frappe.db.get_value("Employee", employee, "user_id")
		if new_user:
			assign_to_add(
				{
					"assign_to": [new_user],
					"doctype": doc.doctype,
					"name": doc.name,
					"description": doc.subject or doc.name,
				}
			)
	except Exception:
		frappe.log_error(
			title="ticket_billing: ToDo-Abgleich nach Umverteilung fehlgeschlagen",
			message=frappe.get_traceback(),
		)


@frappe.whitelist()
def get_department_members(department: str):
	"""Mitarbeiter einer Abteilung samt aktueller Auslastung.

	Grundlage für die Umverteilung: Man sieht beim Auswählen, wen man damit
	belastet.
	"""
	require_department_access(department)

	from ticket_billing.assignment import get_candidates

	return [
		{
			"employee": c.employee,
			"employee_name": c.employee_name,
			"user": c.user,
			"open_tickets": c.open_tickets,
		}
		for c in sorted(get_candidates(department), key=lambda c: c.employee_name)
	]


@frappe.whitelist()
def get_form_options():
	"""Auswahlwerte für Formulare -- gefiltert nach Berechtigung."""
	departments = frappe.get_list(
		"Department",
		filters={"disabled": 0, "is_group": 0},
		fields=["name", "department_name"],
		limit_page_length=0,
		order_by="department_name asc",
	)

	return {
		"departments": departments,
		"priorities": frappe.get_all("Issue Priority", pluck="name"),
		"issue_types": frappe.get_all("Issue Type", pluck="name"),
		"statuses": list(OPEN_STATUSES) + list(CLOSED_STATUSES),
		"origins": [ORIGIN_INTERNAL, ORIGIN_EXTERNAL],
		"my_department": (get_scope_departments() or [None])[0],
		"my_employee": get_employee(),
	}


@frappe.whitelist()
def get_conversation(name: str, limit: int = 50):
	"""E-Mail-Verlauf eines Tickets.

	Der Text einer eingehenden Mail landet **nicht** im Ticket, sondern in
	einem verknüpften ``Communication``-Datensatz -- ``Issue.description``
	bleibt bei per Mail erzeugten Tickets leer. Ohne diesen Verlauf sähe der
	Bearbeiter also den Betreff und sonst nichts.

	Die Rechteprüfung hängt am Ticket: Wer es lesen darf, darf auch lesen,
	was dazu geschrieben wurde.
	"""
	if not frappe.has_permission("Issue", "read", doc=name):
		raise frappe.PermissionError

	rows = frappe.get_all(
		"Communication",
		filters={"reference_doctype": "Issue", "reference_name": name},
		fields=[
			"name",
			"sender",
			"sender_full_name",
			"recipients",
			"subject",
			"content",
			"sent_or_received",
			"communication_medium",
			"creation",
		],
		order_by="creation asc",
		limit_page_length=frappe.utils.cint(limit),
	)

	# Anhänge je Nachricht. Angezeigt wird nur, dass es sie gibt -- das
	# Herunterladen läuft über Frappes eigene Datei-URLs.
	files = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": "Communication",
			"attached_to_name": ["in", [r.name for r in rows]] if rows else "",
		},
		fields=["attached_to_name", "file_name", "file_url"],
	)
	by_comm: dict[str, list] = {}
	for f in files:
		by_comm.setdefault(f.attached_to_name, []).append(
			{"file_name": f.file_name, "file_url": f.file_url}
		)

	for row in rows:
		row["attachments"] = by_comm.get(row.name, [])

	return rows


def _outgoing_account(doc) -> str | None:
	"""Absenderadresse für eine Antwort.

	Bevorzugt das Postfach, über das das Ticket hereinkam -- der Kunde bekommt
	die Antwort dann von der Adresse, an die er geschrieben hat. Fehlt das
	(intern angelegtes Ticket), wird das Postfach der zuständigen Abteilung
	genommen.
	"""
	if doc.get("email_account"):
		account = frappe.db.get_value(
			"Email Account", doc.email_account, ["email_id", "enable_outgoing"], as_dict=True
		)
		if account and account.enable_outgoing:
			return account.email_id

	return frappe.db.get_value(
		"Email Account",
		{"tb_department": doc.get(FIELD_DEPARTMENT), "enable_outgoing": 1},
		"email_id",
	)


def _default_recipients(doc) -> list[str]:
	"""An wen die Antwort geht.

	Der Absender der letzten eingegangenen Nachricht ist genauer als
	``raised_by``: Bei einem weitergeleiteten Vorgang schreibt am Ende oft
	jemand anderes als der ursprüngliche Absender.
	"""
	last = frappe.get_all(
		"Communication",
		filters={
			"reference_doctype": "Issue",
			"reference_name": doc.name,
			"sent_or_received": "Received",
		},
		fields=["sender"],
		order_by="creation desc",
		limit=1,
	)
	if last and last[0].sender:
		return [last[0].sender]

	return [doc.raised_by] if doc.get("raised_by") else []



def _send_immediately(communication: str) -> int:
	"""Die Mails dieser Nachricht sofort zustellen statt im Sammellauf.

	Frappe legt Ausgehendes nur in die Warteschlange; abgearbeitet wird sie
	vom Zeitplan alle paar Minuten. Gemessen lagen zwischen Klick und
	Zustellung 11 bis 244 Sekunden. Fuer eine Supportantwort ist das zu
	traege -- der Bearbeiter sieht nicht, ob sie raus ist, und schreibt im
	Zweifel ein zweites Mal.

	Als Hintergrundjob, nicht direkt: Der Griff zum SMTP-Server kann Sekunden
	dauern, und solange stuende die Oberflaeche. ``enqueue_after_commit``,
	weil der Eintrag sonst noch nicht festgeschrieben ist, wenn der Worker
	ihn sucht.
	"""
	names = frappe.get_all(
		"Email Queue",
		filters={"communication": communication, "status": "Not Sent"},
		pluck="name",
	)
	for name in names:
		frappe.enqueue(
			"ticket_billing.api.tickets.send_queued_mail",
			queue="short",
			enqueue_after_commit=True,
			queue_name=name,
		)
	return len(names)


def send_queued_mail(queue_name: str) -> None:
	"""Einen Warteschlangeneintrag zustellen. Laeuft im Hintergrundprozess.

	Fehler werden geloggt statt geworfen: Bleibt der Eintrag auf 'Not Sent',
	holt ihn der regulaere Sammellauf ohnehin nach -- die Mail geht also
	nicht verloren, sie kommt nur spaeter.
	"""
	try:
		frappe.get_doc("Email Queue", queue_name).send()
	except Exception:
		frappe.log_error(
			title="ticket_billing: Sofortversand fehlgeschlagen",
			message=frappe.get_traceback(),
		)

@frappe.whitelist()
def reply_to_ticket(
	name: str,
	message: str,
	recipients: str | list | None = None,
	cc: str | list | None = None,
	set_status: str | None = "Replied",
):
	"""Aus dem Ticket heraus per E-Mail antworten.

	Die Nachricht wird als ``Communication`` am Ticket abgelegt und über
	Frappes Mailversand hinausgeschickt -- damit steht sie im selben Verlauf
	wie die eingegangene Post, und die Antwort des Kunden findet über die
	Referenz zurück zum Ticket.
	"""
	if not frappe.has_permission("Issue", "write", doc=name):
		raise frappe.PermissionError

	if not (message or "").strip():
		frappe.throw(_("The reply must not be empty."))

	doc = frappe.get_doc("Issue", name)

	sender = _outgoing_account(doc)
	if not sender:
		frappe.throw(
			_(
				"No outgoing email account is configured for this ticket. "
				"Enable outgoing mail on the department's email account."
			),
			title=_("Cannot send"),
		)

	if isinstance(recipients, str):
		recipients = [r.strip() for r in recipients.split(",") if r.strip()]
	recipients = recipients or _default_recipients(doc)

	if not recipients:
		frappe.throw(_("No recipient could be determined for this ticket."))

	# Auf die letzte eingegangene Nachricht beziehen. Ohne das hängt die
	# Antwort im Postfach des Empfängers als eigener Vorgang.
	last_received = frappe.get_all(
		"Communication",
		filters={
			"reference_doctype": "Issue",
			"reference_name": name,
			"sent_or_received": "Received",
		},
		pluck="name",
		order_by="creation desc",
		limit=1,
	)

	from frappe.core.doctype.communication.email import make

	result = make(
		doctype="Issue",
		name=name,
		content=frappe.utils.md_to_html(message) if "\n" in message else message,
		subject=f"Re: {doc.subject}",
		sender=sender,
		recipients=recipients,
		cc=cc,
		communication_medium="Email",
		sent_or_received="Sent",
		send_email=True,
		in_reply_to=last_received[0] if last_received else None,
	)

	_send_immediately(result.get("name"))

	# Ein beantwortetes Ticket ist nicht mehr unbearbeitet. Der Statuswechsel
	# setzt nebenbei den Zeitstempel für die Reaktionszeit.
	#
	# reload() ist nötig, nicht Vorsicht: make() stößt ERPNext-Hooks auf
	# Communication an (set_first_response_time), die das Ticket in der
	# Datenbank anfassen. Das oben geladene Objekt ist danach veraltet, und
	# save() bricht mit TimestampMismatchError ab.
	doc.reload()
	if set_status and doc.status != set_status and doc.status not in CLOSED_STATUSES:
		doc.status = set_status
		doc.save()

	return {
		"communication": result.get("name"),
		"sender": sender,
		"recipients": recipients,
		"conversation": get_conversation(name),
		"status": frappe.db.get_value("Issue", name, "status"),
	}
