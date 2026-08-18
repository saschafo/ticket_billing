"""Zeiterfassung auf Tickets.

Zwei Wege, ein Ergebnis: Timer starten und stoppen, oder eine Dauer von Hand
eintragen. Beide erzeugen dieselbe Zeile in einem ERPNext-Timesheet, verknüpft
mit Ticket, Mitarbeiter und -- bei externen Tickets -- dem Kunden.

Warum ein Timesheet pro Mitarbeiter, Tag und Kunde: Der Kunde hängt in ERPNext
am Timesheet, nicht an der einzelnen Zeile. Würde man alles in ein Timesheet
je Tag schreiben, ließen sich Zeiten für zwei Kunden nicht mehr trennen.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, flt, get_datetime, now_datetime, time_diff_in_hours

from ticket_billing.constants import FIELD_ORIGIN, FIELD_TIMESHEET_ISSUE, ORIGIN_EXTERNAL
from ticket_billing.realtime import publish_timer
from ticket_billing.utils.context import get_employee


def _require_employee() -> str:
	employee = get_employee()
	if not employee:
		frappe.throw(
			_("Your user account is not linked to an employee record."),
			title=_("No employee record"),
		)
	return employee


def _require_issue_access(issue: str, ptype: str = "write") -> None:
	if not frappe.has_permission("Issue", ptype, doc=issue):
		raise frappe.PermissionError


def _issue_customer(issue: str) -> str | None:
	"""Kunde des Tickets -- nur wenn es tatsächlich von außen kam."""
	row = frappe.db.get_value("Issue", issue, ["customer", FIELD_ORIGIN], as_dict=True)
	if not row or row.get(FIELD_ORIGIN) != ORIGIN_EXTERNAL:
		return None

	return row.get("customer")


def _add_entry(issue: str, employee: str, from_time, to_time, description: str | None):
	"""Einen Zeiteintrag als eigenes Timesheet im Entwurf anlegen.

	Ein Dokument je Eintrag, nicht ein Tagesbeleg mit mehreren Zeilen: In
	ERPNext wird pro **Dokument** gebucht. Nur so lässt sich ein einzelner
	Eintrag unabhängig ändern, löschen und freigeben -- und nur so kann der
	Abteilungsleiter gezielt einen Vorgang buchen statt den ganzen Tag.

	Gebucht wird hier nichts: Der Entwurf (docstatus 0) wartet auf die
	Freigabe durch die Abteilungsleitung.
	"""
	hours = flt(time_diff_in_hours(to_time, from_time), 4)
	if hours <= 0:
		frappe.throw(_("The recorded duration must be greater than zero."))

	employee_row = frappe.db.get_value(
		"Employee", employee, ["company", "department"], as_dict=True
	)
	subject = frappe.db.get_value("Issue", issue, "subject")
	activity_type = frappe.db.get_single_value(
		"Ticket Billing Settings", "default_activity_type"
	)

	# Zeit an einem externen Ticket ist abrechenbar. Das Kennzeichen ist nicht
	# Kosmetik: ERPNext summiert nur Zeilen mit is_billable zu
	# total_billable_hours, und "Sales Invoice aus Timesheet" bricht bei null
	# abrechenbaren Stunden ab. Ohne diese Zeile wäre der Standardweg zur
	# Rechnung versperrt.
	customer = _issue_customer(issue)

	timesheet = frappe.get_doc(
		{
			"doctype": "Timesheet",
			"title": (subject or issue)[:140],
			"employee": employee,
			"company": employee_row.company,
			"department": employee_row.department,
			"customer": customer,
			"time_logs": [
				{
					"activity_type": activity_type,
					"from_time": from_time,
					"to_time": to_time,
					"hours": hours,
					"is_billable": 1 if customer else 0,
					"description": description or subject,
					FIELD_TIMESHEET_ISSUE: issue,
				}
			],
		}
	)

	# ignore_permissions: Die Berechtigung hängt am Ticket und wurde vom
	# Aufrufer bereits geprüft. Ein Mitarbeiter, der ein Ticket bearbeiten
	# darf, darf auch Zeit darauf buchen -- ohne dass er deshalb fremde
	# Timesheets anfassen könnte, denn angelegt wird immer nur sein eigenes.
	timesheet.insert(ignore_permissions=True)

	return timesheet


# ---------------------------------------------------------------------------
# Timer
# ---------------------------------------------------------------------------


def get_timer_warning_hours() -> float:
	return flt(
		frappe.db.get_single_value("Ticket Billing Settings", "timer_warning_hours") or 4
	)


@frappe.whitelist()
def get_running_timer():
	employee = get_employee()
	if not employee:
		return None

	row = frappe.db.get_value(
		"Ticket Timer",
		{"employee": employee},
		["name", "issue", "start_time", "note"],
		as_dict=True,
	)
	if not row:
		return None

	row["subject"] = frappe.db.get_value("Issue", row.issue, "subject")
	row["elapsed_hours"] = flt(time_diff_in_hours(now_datetime(), row.start_time), 4)
	# Die Schwelle kommt mit, damit die Oberfläche sie nicht gesondert holen
	# muss -- und damit sie zentral in den Einstellungen änderbar bleibt.
	row["warning_hours"] = get_timer_warning_hours()
	row["is_warning"] = row["elapsed_hours"] > row["warning_hours"]
	return row


@frappe.whitelist()
def start_timer(issue: str, note: str | None = None):
	employee = _require_employee()
	_require_issue_access(issue)

	timer = frappe.get_doc(
		{
			"doctype": "Ticket Timer",
			"employee": employee,
			"issue": issue,
			"start_time": now_datetime(),
			"note": note,
		}
	)
	timer.insert(ignore_permissions=True)

	running = get_running_timer()
	publish_timer(frappe.session.user, running)
	return running


#: Obergrenze für eine einzelne Buchung. Alles darüber ist praktisch immer ein
#: Tippfehler in der Korrektur -- und wäre als Arbeitszeit ohnehin fragwürdig.
MAX_ENTRY_HOURS = 24


@frappe.whitelist()
def stop_timer(
	description: str | None = None,
	discard: int | str = 0,
	hours: float | str | None = None,
):
	"""Timer beenden und die Zeit buchen -- oder verwerfen.

	``hours`` überschreibt die gemessene Dauer. Die Oberfläche zeigt sie vor
	dem Buchen zur Bestätigung an; wer zwischendurch etwas anderes gemacht
	hat, korrigiert sie dort.

	Der gebuchte Zeitraum beginnt beim Start des Timers. Eine gekürzte Dauer
	liegt damit innerhalb der Zeit, in der der Timer tatsächlich lief -- das
	ist nicht nur die ehrlichere Lesart, es vermeidet auch Überschneidungen
	mit älteren Einträgen. ERPNext lässt zwei sich überlappende Zeiteinträge
	desselben Mitarbeiters nicht zu, und rückwärts von jetzt gerechnet liefe
	eine korrigierte Dauer regelmäßig in einen vorher gebuchten Eintrag.

	Nur wenn jemand mehr angibt, als der Timer lief, wird rückwärts von jetzt
	gerechnet -- sonst entstünde ein Eintrag, der in der Zukunft endet.
	"""
	employee = _require_employee()

	name = frappe.db.get_value("Ticket Timer", {"employee": employee}, "name")
	if not name:
		frappe.throw(_("No timer is running."), title=_("Nothing to stop"))

	timer = frappe.get_doc("Ticket Timer", name)
	_require_issue_access(timer.issue)

	if frappe.utils.cint(discard):
		frappe.delete_doc("Ticket Timer", name, ignore_permissions=True, force=True)
		publish_timer(frappe.session.user, None)
		return {"discarded": True}

	measured = time_diff_in_hours(now_datetime(), timer.start_time)
	booked = flt(hours) if hours not in (None, "") else measured

	# Unter einer Minute gibt es nichts zu buchen. Wichtig ist die Formulierung:
	# Der Timer bleibt stehen, und der Ausweg (verwerfen) steht in der Meldung --
	# sonst hinge er fest, weil Stoppen scheitert und es keinen anderen Weg gäbe.
	if booked < 1 / 60:
		frappe.throw(
			_("The timer has been running for less than a minute. Keep working, or discard it."),
			title=_("Too short to record"),
		)

	if booked > MAX_ENTRY_HOURS:
		frappe.throw(
			_("A single entry cannot exceed {0} hours.").format(MAX_ENTRY_HOURS),
			title=_("Duration too long"),
		)

	if booked <= measured:
		start = timer.start_time
		end = add_to_date(get_datetime(start), hours=booked)
	else:
		end = now_datetime()
		start = add_to_date(end, hours=-booked)

	timesheet = _add_entry(
		issue=timer.issue,
		employee=employee,
		from_time=start,
		to_time=end,
		description=description or timer.note,
	)

	frappe.delete_doc("Ticket Timer", name, ignore_permissions=True, force=True)
	publish_timer(frappe.session.user, None)

	return {
		"timesheet": timesheet.name,
		"issue": timer.issue,
		"hours": flt(booked, 4),
	}


# ---------------------------------------------------------------------------
# Manuelle Erfassung
# ---------------------------------------------------------------------------


@frappe.whitelist()
def log_time(
	issue: str,
	hours: float | str,
	description: str | None = None,
	from_time: str | None = None,
):
	"""Dauer von Hand buchen.

	Ohne ``from_time`` wird rückwärts von jetzt gerechnet -- das entspricht
	dem üblichen Fall "ich habe gerade zwei Stunden daran gearbeitet".
	"""
	employee = _require_employee()
	_require_issue_access(issue)

	hours = flt(hours)
	if hours <= 0:
		frappe.throw(_("The recorded duration must be greater than zero."))

	if from_time:
		start = get_datetime(from_time)
		end = add_to_date(start, hours=hours)
	else:
		end = now_datetime()
		start = add_to_date(end, hours=-hours)

	timesheet = _add_entry(
		issue=issue,
		employee=employee,
		from_time=start,
		to_time=end,
		description=description,
	)

	return {"timesheet": timesheet.name, "issue": issue}


@frappe.whitelist()
def get_entries_for_issue(issue: str):
	"""Zeiteinträge eines Tickets.

	Wer das Ticket lesen darf, darf auch sehen, wie viel Zeit darauf gebucht
	wurde -- deshalb hängt die Prüfung am Ticket und nicht am Timesheet.
	"""
	_require_issue_access(issue, "read")

	rows = frappe.get_all(
		"Timesheet Detail",
		filters={FIELD_TIMESHEET_ISSUE: issue, "docstatus": ["<", 2]},
		fields=["name", "parent", "from_time", "to_time", "hours", "description"],
		order_by="from_time desc",
		limit_page_length=0,
	)

	owners = frappe.get_all(
		"Timesheet",
		filters={"name": ["in", [r.parent for r in rows]]} if rows else {"name": ""},
		fields=["name", "employee", "employee_name"],
	)
	by_sheet = {o.name: o for o in owners}

	for row in rows:
		sheet = by_sheet.get(row.parent)
		row["employee"] = sheet.employee if sheet else None
		row["employee_name"] = sheet.employee_name if sheet else None

	return {
		"rows": rows,
		"total_hours": flt(sum(flt(r.hours) for r in rows), 2),
	}
