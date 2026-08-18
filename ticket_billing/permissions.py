"""Zeilenweise Rechteprüfung für Tickets und Zeiterfassung.

Frappe kennt zwei Ebenen, und beide werden hier bedient:

* ``permission_query_conditions`` hängt eine WHERE-Bedingung an **jede**
  Listenabfrage -- Desk-Liste, Report, ``frappe.get_list``, REST-API. Damit
  ist die Filterung nicht Sache der Oberfläche.
* ``has_permission`` prüft einzelne Dokumente, also den direkten Zugriff auf
  einen bekannten Namen.

Beide leiten sich aus derselben Funktion in ``utils.context`` ab. Liefen sie
auseinander, wäre die Liste gefiltert, der Direktzugriff aber offen -- genau
die Art Lücke, die niemandem auffällt.

Wichtig: Diese Hooks können Rechte nur **einschränken**, nie erweitern. Was
eine Rolle grundsätzlich darf, steht in den DocPerms (siehe ``setup.py``).
Deshalb genügt es hier, die Sichtbarkeit zu verengen.
"""

import frappe

from ticket_billing.constants import FIELD_ASSIGNEE, FIELD_DEPARTMENT
from ticket_billing.utils.context import (
	get_access_level,
	get_employee,
	get_scope_departments,
)


def _in_list(values: list[str]) -> str:
	return ", ".join(frappe.db.escape(v) for v in values)


# ---------------------------------------------------------------------------
# Issue
# ---------------------------------------------------------------------------


def issue_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	user = user or frappe.session.user
	level = get_access_level(user)

	if level == "all":
		return ""

	if level == "department":
		departments = get_scope_departments(user)
		if not departments:
			return "1=0"
		return f"`tabIssue`.`{FIELD_DEPARTMENT}` in ({_in_list(departments)})"

	# Mitarbeiter: die eigenen zugewiesenen Tickets -- plus die selbst
	# angelegten. Ohne den zweiten Teil verliert man ein intern gestelltes
	# Ticket in dem Moment aus den Augen, in dem es zugewiesen wird.
	employee = get_employee(user)
	own = f"`tabIssue`.`owner` = {frappe.db.escape(user)}"
	if not employee:
		return own

	return f"(`tabIssue`.`{FIELD_ASSIGNEE}` = {frappe.db.escape(employee)} or {own})"


def issue_has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	user = user or frappe.session.user

	# Anlegen wird nicht über die Zuordnung entschieden: Ein neues Ticket hat
	# noch keine Zuweisung, und interne Anfragen gehen bewusst an fremde
	# Abteilungen. Ob die Abteilung stimmt, prüft validate() im Doc-Hook.
	if ptype == "create":
		return True

	level = get_access_level(user)
	if level == "all":
		return True

	if level == "department":
		return doc.get(FIELD_DEPARTMENT) in get_scope_departments(user)

	if doc.get("owner") == user:
		return True

	employee = get_employee(user)
	return bool(employee) and doc.get(FIELD_ASSIGNEE) == employee


# ---------------------------------------------------------------------------
# Timesheet
# ---------------------------------------------------------------------------


def timesheet_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	user = user or frappe.session.user
	level = get_access_level(user)

	if level == "all":
		return ""

	if level == "department":
		departments = get_scope_departments(user)
		if not departments:
			return "1=0"
		return f"`tabTimesheet`.`department` in ({_in_list(departments)})"

	employee = get_employee(user)
	if not employee:
		return "1=0"

	return f"`tabTimesheet`.`employee` = {frappe.db.escape(employee)}"


def timesheet_has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	user = user or frappe.session.user

	if ptype == "create":
		return True

	level = get_access_level(user)
	if level == "all":
		return True

	if level == "department":
		return doc.get("department") in get_scope_departments(user)

	employee = get_employee(user)
	return bool(employee) and doc.get("employee") == employee
