"""Zeiterfassung nach dem Vier-Augen-Prinzip.

Der Mitarbeiter erfasst, die Abteilungsleitung bucht. Bis dahin ist ein
Eintrag ein Entwurf (``docstatus`` 0) und änderbar; gebucht (``docstatus`` 1)
ist er unveränderlich -- darum kümmert sich Frappe selbst, ein Sonderweg wäre
hier nur eine zusätzliche Stelle, an der etwas schiefgehen kann.

Jede Prüfung steht serverseitig. Die Oberfläche blendet zwar aus, was nicht
geht, aber verlassen darf sich darauf niemand.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, flt, get_datetime, nowdate

from ticket_billing.constants import FIELD_TIMESHEET_ISSUE
from ticket_billing.utils.context import (
	get_employee,
	get_scope_departments,
	is_lead,
	is_unrestricted,
)

DRAFT = 0
SUBMITTED = 1
CANCELLED = 2

#: Felder des Timesheets, die für die Übersichten gebraucht werden.
_PARENT_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"department",
	"customer",
	"total_hours",
	"docstatus",
	"start_date",
	"modified",
]


def _rows_for(names: list[str]) -> dict[str, list[dict]]:
	"""Zeiteinträge zu den Timesheets, nach Beleg gruppiert."""
	if not names:
		return {}

	rows = frappe.get_all(
		"Timesheet Detail",
		filters={"parent": ["in", names]},
		fields=[
			"name",
			"parent",
			"from_time",
			"to_time",
			"hours",
			"description",
			f"{FIELD_TIMESHEET_ISSUE} as issue",
		],
		order_by="from_time asc",
		limit_page_length=0,
	)

	grouped: dict[str, list[dict]] = {}
	for row in rows:
		grouped.setdefault(row.parent, []).append(row)
	return grouped


def _serialize(sheets: list[dict]) -> list[dict]:
	names = [s["name"] for s in sheets]
	by_sheet = _rows_for(names)

	issues = {
		r["issue"] for rows in by_sheet.values() for r in rows if r.get("issue")
	}
	subjects = (
		{
			i.name: i.subject
			for i in frappe.get_all(
				"Issue", filters={"name": ["in", list(issues)]}, fields=["name", "subject"]
			)
		}
		if issues
		else {}
	)

	result = []
	for sheet in sheets:
		rows = by_sheet.get(sheet["name"], [])
		first = rows[0] if rows else {}

		result.append(
			{
				**sheet,
				"hours": flt(sheet.get("total_hours"), 4),
				"issue": first.get("issue"),
				"issue_subject": subjects.get(first.get("issue")),
				"description": first.get("description"),
				"from_time": first.get("from_time"),
				"row_count": len(rows),
				# Ältere Belege aus der Zeit vor "ein Dokument je Eintrag"
				# können mehrere Zeilen haben. Die lassen sich hier nicht
				# sinnvoll einzeln ändern -- buchen geht trotzdem.
				"editable": sheet["docstatus"] == DRAFT and len(rows) == 1,
				"status": {DRAFT: "draft", SUBMITTED: "submitted", CANCELLED: "cancelled"}[
					sheet["docstatus"]
				],
			}
		)

	return result


# ---------------------------------------------------------------------------
# Prüfungen
# ---------------------------------------------------------------------------


def _load_draft(name: str, require_lead: bool = False):
	"""Timesheet laden und prüfen, ob der Aufrufer daran arbeiten darf."""
	doc = frappe.get_doc("Timesheet", name)

	if doc.docstatus != DRAFT:
		frappe.throw(
			_("This entry has already been submitted and can no longer be changed."),
			title=_("Already submitted"),
		)

	if is_unrestricted():
		return doc

	if require_lead:
		# Buchen und fremde Einträge korrigieren darf nur die Leitung -- und
		# nur in der eigenen Abteilung.
		if not is_lead() or doc.department not in get_scope_departments():
			frappe.throw(
				_("You may only submit entries from your own department."),
				frappe.PermissionError,
			)
		return doc

	employee = get_employee()
	if not employee or doc.employee != employee:
		frappe.throw(
			_("You may only change your own entries."), frappe.PermissionError
		)

	return doc


# ---------------------------------------------------------------------------
# Mitarbeitersicht
# ---------------------------------------------------------------------------


@frappe.whitelist()
def list_my_entries(
	from_date: str | None = None,
	to_date: str | None = None,
	only_draft: int | str = 0,
	limit_page_length: int | str = 100,
):
	"""Eigene Zeiteinträge, Entwürfe wie gebuchte."""
	employee = get_employee()
	if not employee:
		return {"rows": [], "draft_count": 0, "draft_hours": 0}

	filters: dict = {"employee": employee, "docstatus": ["<", 2]}
	if frappe.utils.cint(only_draft):
		filters["docstatus"] = DRAFT
	if from_date:
		filters["start_date"] = [">=", from_date]
	if to_date:
		filters.setdefault("start_date", None)
		filters["start_date"] = (
			["between", [from_date, to_date]] if from_date else ["<=", to_date]
		)

	sheets = frappe.get_all(
		"Timesheet",
		filters=filters,
		fields=_PARENT_FIELDS,
		order_by="start_date desc, modified desc",
		limit_page_length=frappe.utils.cint(limit_page_length),
	)

	rows = _serialize(sheets)
	drafts = [r for r in rows if r["status"] == "draft"]

	return {
		"rows": rows,
		"draft_count": len(drafts),
		"draft_hours": flt(sum(r["hours"] for r in drafts), 2),
	}


@frappe.whitelist()
def update_time_entry(
	name: str, hours: float | str | None = None, description: str | None = None
):
	"""Dauer oder Notiz eines Entwurfs ändern.

	Der Mitarbeiter darf nur die eigenen; die Abteilungsleitung darf auch
	fremde in der eigenen Abteilung korrigieren, bevor sie bucht.
	"""
	employee = get_employee()
	doc = frappe.get_doc("Timesheet", name)
	own = bool(employee) and doc.employee == employee

	doc = _load_draft(name, require_lead=not own)

	if len(doc.time_logs) != 1:
		frappe.throw(
			_("This entry has several time logs and cannot be edited here."),
			title=_("Not editable"),
		)

	row = doc.time_logs[0]

	if hours not in (None, ""):
		new_hours = flt(hours)
		if new_hours <= 0 or new_hours > 24:
			frappe.throw(_("A single entry cannot exceed {0} hours.").format(24))

		# Anfang bleibt stehen, das Ende wandert -- so verschiebt eine
		# Korrektur den Eintrag nicht in einen fremden Zeitraum.
		row.to_time = add_to_date(get_datetime(row.from_time), hours=new_hours)
		row.hours = new_hours

	if description is not None:
		row.description = description

	doc.save(ignore_permissions=True)

	return _serialize([{f: doc.get(f) for f in _PARENT_FIELDS}])[0]


@frappe.whitelist()
def delete_time_entry(name: str):
	"""Einen eigenen Entwurf löschen."""
	doc = _load_draft(name)
	frappe.delete_doc("Timesheet", doc.name, ignore_permissions=True)
	return {"deleted": name}


# ---------------------------------------------------------------------------
# Leitungssicht
# ---------------------------------------------------------------------------


@frappe.whitelist()
def list_pending(
	department: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	employee: str | None = None,
):
	"""Offene Entwürfe der eigenen Abteilung."""
	if not department:
		scope = get_scope_departments()
		department = scope[0] if scope else None

	if not department:
		frappe.throw(_("No department could be determined."), title=_("Department missing"))

	if not is_unrestricted():
		if not is_lead() or department not in get_scope_departments():
			frappe.throw(
				_("You are not allowed to access department {0}.").format(department),
				frappe.PermissionError,
			)

	filters: dict = {"docstatus": DRAFT, "department": department}
	if employee:
		filters["employee"] = employee
	if from_date and to_date:
		filters["start_date"] = ["between", [from_date, to_date]]
	elif from_date:
		filters["start_date"] = [">=", from_date]
	elif to_date:
		filters["start_date"] = ["<=", to_date]

	sheets = frappe.get_all(
		"Timesheet",
		filters=filters,
		fields=_PARENT_FIELDS,
		order_by="start_date asc, employee_name asc",
		limit_page_length=0,
	)

	rows = _serialize(sheets)

	by_employee: dict[str, dict] = {}
	for row in rows:
		entry = by_employee.setdefault(
			row["employee"],
			{"employee": row["employee"], "employee_name": row["employee_name"], "count": 0, "hours": 0},
		)
		entry["count"] += 1
		entry["hours"] = flt(entry["hours"] + row["hours"], 2)

	return {
		"department": department,
		"rows": rows,
		"total_hours": flt(sum(r["hours"] for r in rows), 2),
		"by_employee": sorted(by_employee.values(), key=lambda e: e["employee_name"] or ""),
	}


def _ensure_activity_type(doc) -> None:
	"""Fehlende Leistungsart nachtragen.

	ERPNext verlangt sie erst beim Buchen. Einträge, die vor dem Einrichten
	der Standard-Tätigkeit entstanden sind, blieben sonst dauerhaft
	unbuchbar -- mit einer Meldung, die dem Abteilungsleiter nichts sagt und
	die er selbst auch nicht beheben könnte.
	"""
	default = frappe.db.get_single_value("Ticket Billing Settings", "default_activity_type")
	if not default:
		return

	for row in doc.time_logs:
		if not row.activity_type:
			row.activity_type = default


@frappe.whitelist()
def submit_time_entries(names: str | list):
	"""Einträge buchen -- einzeln oder gesammelt.

	Fehlschläge brechen den Vorgang nicht ab, sondern werden je Eintrag
	gemeldet. Bei einer Mehrfachauswahl ist es sonst Zufall, welche Einträge
	noch durchgingen, bevor der erste Fehler alles beendete.
	"""
	if isinstance(names, str):
		names = frappe.parse_json(names)
	if not names:
		return {"submitted": [], "failed": []}

	submitted, failed = [], []

	for name in names:
		# Savepoint je Eintrag: Ein abgelehnter Beleg soll die bereits
		# gebuchten nicht mitreißen.
		frappe.db.savepoint("tb_submit")
		try:
			doc = _load_draft(name, require_lead=True)
			_ensure_activity_type(doc)
			doc.submit()
			submitted.append(name)
		except Exception as e:
			frappe.db.rollback(save_point="tb_submit")
			failed.append({"name": name, "error": str(e)})

	return {"submitted": submitted, "failed": failed}


@frappe.whitelist()
def get_entry(name: str):
	"""Einzelheiten eines Eintrags -- für die Ansicht vor dem Buchen."""
	doc = frappe.get_doc("Timesheet", name)

	if not is_unrestricted():
		employee = get_employee()
		own = bool(employee) and doc.employee == employee
		in_scope = is_lead() and doc.department in get_scope_departments()
		if not (own or in_scope):
			raise frappe.PermissionError

	return _serialize([{f: doc.get(f) for f in _PARENT_FIELDS}])[0]
