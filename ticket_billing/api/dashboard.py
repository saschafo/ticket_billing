"""Kennzahlen für die drei Sichten.

Die Abfragen laufen mit ``frappe.get_all`` bzw. direktem SQL und umgehen damit
die Zeilenfilter. Das ist Absicht -- eine Auswertung muss zählen, was der
Aufrufer nicht einzeln sehen darf. Genau deshalb steht **vor** jeder Abfrage
eine ausdrückliche Prüfung, wer das darf; ohne die wäre das hier eine
Hintertür an den Rechten vorbei.
"""

import frappe
from frappe import _
from frappe.utils import add_days, flt, nowdate

from ticket_billing.constants import (
	CLOSED_STATUSES,
	FIELD_ASSIGNEE,
	FIELD_DEPARTMENT,
	FIELD_ORIGIN,
	OPEN_STATUSES,
)
from ticket_billing.utils.context import (
	get_employee,
	get_scope_departments,
	is_lead,
	is_unrestricted,
)


def _hours_by(group_field: str, filters_sql: str, values: dict) -> dict[str, float]:
	"""Gebuchte Stunden, gruppiert nach einem Feld des Timesheets."""
	rows = frappe.db.sql(
		f"""
		select ts.`{group_field}` as grp, sum(td.hours) as hours
		from `tabTimesheet Detail` td
		inner join `tabTimesheet` ts on ts.name = td.parent
		where ts.docstatus < 2 and td.`tb_issue` is not null and {filters_sql}
		group by ts.`{group_field}`
		""",
		values,
		as_dict=True,
	)
	return {r.grp: flt(r.hours, 2) for r in rows if r.grp}


def _count_by(field: str, where: str = "1=1", values: dict | None = None) -> dict[str, int]:
	"""Tickets zählen, gruppiert nach einem Feld.

	Direktes SQL, weil Aggregatfunktionen in ``frappe.get_all`` nur noch über
	eine Dict-Schreibweise erlaubt sind, die Alias und group_by nicht sauber
	abbildet. ``field`` kommt ausschließlich aus ``constants.py``, die Werte
	gehen parametrisiert hinein.
	"""
	rows = frappe.db.sql(
		f"""
		select `{field}` as grp, count(name) as cnt
		from `tabIssue`
		where {where}
		group by `{field}`
		""",
		values or {},
		as_dict=True,
	)
	return {r.grp: r.cnt for r in rows if r.grp}


@frappe.whitelist()
def get_my_stats():
	"""Kennzahlen des angemeldeten Mitarbeiters."""
	employee = get_employee()
	if not employee:
		return {"employee": None, "open": 0, "closed": 0, "by_status": {}, "hours_7d": 0}

	by_status = _count_by(
		"status", f"`{FIELD_ASSIGNEE}` = %(employee)s", {"employee": employee}
	)

	since = add_days(nowdate(), -7)
	hours = frappe.db.sql(
		"""
		select sum(td.hours)
		from `tabTimesheet Detail` td
		inner join `tabTimesheet` ts on ts.name = td.parent
		where ts.docstatus < 2 and ts.employee = %(employee)s
		  and td.`tb_issue` is not null and td.from_time >= %(since)s
		""",
		{"employee": employee, "since": since},
	)

	return {
		"employee": employee,
		"open": sum(v for k, v in by_status.items() if k in OPEN_STATUSES),
		"closed": sum(v for k, v in by_status.items() if k in CLOSED_STATUSES),
		"by_status": by_status,
		"hours_7d": flt(hours[0][0] if hours and hours[0][0] else 0, 2),
	}


@frappe.whitelist()
def get_team_stats(department: str | None = None, days: int | str = 30):
	"""Auswertung einer Abteilung -- für die Leitung."""
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

	days = frappe.utils.cint(days) or 30
	since = add_days(nowdate(), -days)

	from ticket_billing.assignment import get_candidates, get_open_ticket_counts

	candidates = get_candidates(department)
	employee_ids = [c.employee for c in candidates]

	open_counts = get_open_ticket_counts(employee_ids)

	resolved = (
		_count_by(
			FIELD_ASSIGNEE,
			f"`{FIELD_ASSIGNEE}` in %(employees)s and status in %(statuses)s and modified >= %(since)s",
			{
				"employees": employee_ids,
				"statuses": list(CLOSED_STATUSES),
				"since": since,
			},
		)
		if employee_ids
		else {}
	)

	hours = (
		_hours_by(
			"employee",
			"ts.employee in %(employees)s and td.from_time >= %(since)s",
			{"employees": employee_ids, "since": since},
		)
		if employee_ids
		else {}
	)

	members = [
		{
			"employee": c.employee,
			"employee_name": c.employee_name,
			"open_tickets": open_counts.get(c.employee, 0),
			"resolved_tickets": resolved.get(c.employee, 0),
			"hours": hours.get(c.employee, 0),
		}
		for c in sorted(candidates, key=lambda c: c.employee_name)
	]

	dept_where = f"`{FIELD_DEPARTMENT}` = %(department)s"
	dept_values = {"department": department}

	# Unzugewiesene Tickets sind das, was der Leitung am ehesten entgeht --
	# deshalb eigens ausgewiesen statt in der Summe zu verschwinden.
	unassigned = frappe.db.sql(
		f"""
		select count(name) from `tabIssue`
		where `{FIELD_DEPARTMENT}` = %(department)s
		  and (`{FIELD_ASSIGNEE}` is null or `{FIELD_ASSIGNEE}` = '')
		  and status in %(statuses)s
		""",
		{"department": department, "statuses": list(OPEN_STATUSES)},
	)[0][0]

	by_status = _count_by("status", dept_where, dept_values)

	return {
		"department": department,
		"members": members,
		"by_status": by_status,
		"by_origin": _count_by(FIELD_ORIGIN, dept_where, dept_values),
		"open": sum(v for k, v in by_status.items() if k in OPEN_STATUSES),
		"closed": sum(v for k, v in by_status.items() if k in CLOSED_STATUSES),
		"unassigned": unassigned,
		"total_hours": flt(sum(hours.values()), 2),
		"days": days,
	}


@frappe.whitelist()
def get_company_stats(days: int | str = 90):
	"""Abteilungsübergreifende Kennzahlen -- für die Geschäftsführung."""
	if not is_unrestricted():
		frappe.throw(
			_("This evaluation is restricted to management."), frappe.PermissionError
		)

	days = frappe.utils.cint(days) or 90
	since = add_days(nowdate(), -days)

	by_department_open = _count_by(
		FIELD_DEPARTMENT, "status in %(statuses)s", {"statuses": list(OPEN_STATUSES)}
	)
	by_department_closed = _count_by(
		FIELD_DEPARTMENT,
		"status in %(statuses)s and modified >= %(since)s",
		{"statuses": list(CLOSED_STATUSES), "since": since},
	)
	hours_by_department = _hours_by(
		"department", "td.from_time >= %(since)s", {"since": since}
	)

	departments = sorted(
		set(by_department_open) | set(by_department_closed) | set(hours_by_department)
	)

	rows = [
		{
			"department": d,
			"open": by_department_open.get(d, 0),
			"closed": by_department_closed.get(d, 0),
			"hours": hours_by_department.get(d, 0),
		}
		for d in departments
	]

	# Verlauf: angelegte gegen erledigte Tickets je Woche. Erst im Nebeneinander
	# wird sichtbar, ob ein Rückstand wächst oder abgebaut wird.
	trend = frappe.db.sql(
		"""
		select date_format(creation, '%%x-KW%%v') as week,
		       count(name) as created,
		       sum(case when status in ('Resolved', 'Closed') then 1 else 0 end) as closed
		from `tabIssue`
		where creation >= %(since)s
		group by week
		order by min(creation) asc
		""",
		{"since": since},
		as_dict=True,
	)

	return {
		"departments": rows,
		"by_status": _count_by("status"),
		"by_origin": _count_by(FIELD_ORIGIN),
		"open_total": sum(r["open"] for r in rows),
		"closed_total": sum(r["closed"] for r in rows),
		"hours_total": flt(sum(r["hours"] for r in rows), 2),
		"trend": trend,
		"days": days,
	}
