"""Wer ist der aktuelle Nutzer, und was darf er sehen?

Jede Rechteprüfung, jeder API-Endpunkt und die Zuweisung fragen dieselben
Fragen: Welcher Employee gehört zum angemeldeten User, in welcher Abteilung
sitzt er, und mit welcher Rolle schaut er auf die Daten. Genau einmal
beantwortet -- sonst driften Listenfilter und Einzelprüfung auseinander, und
solche Abweichungen sind Rechtelücken.
"""

import frappe

from ticket_billing.constants import (
	ROLE_LEAD,
	UNRESTRICTED_ROLES,
)


def _user(user: str | None = None) -> str:
	return user or frappe.session.user


def get_employee(user: str | None = None) -> str | None:
	"""Employee-ID des Users, oder None.

	Ein User ohne Employee-Datensatz ist kein Ticket-Bearbeiter. Die
	Rechteprüfung behandelt ihn deshalb wie jemanden ohne eigene Tickets --
	nicht wie jemanden, der alles sieht.
	"""
	u = _user(user)
	if u in ("Guest", ""):
		return None

	return frappe.db.get_value("Employee", {"user_id": u, "status": "Active"}, "name")


def get_employee_department(user: str | None = None) -> str | None:
	"""Abteilung des Users laut seinem Employee-Datensatz."""
	employee = get_employee(user)
	if not employee:
		return None

	return frappe.db.get_value("Employee", employee, "department")


def get_permitted_departments(user: str | None = None) -> list[str]:
	"""Abteilungen, auf die der User per User Permission eingeschränkt ist.

	Leere Liste heißt "keine Einschränkung hinterlegt" -- nicht "keine
	Abteilung". Die Aufrufer müssen das unterscheiden, deshalb wird hier
	nichts auf die Employee-Abteilung zurückgefallen.
	"""
	u = _user(user)
	if u in ("Guest", ""):
		return []

	rows = frappe.get_all(
		"User Permission",
		filters={"user": u, "allow": "Department"},
		pluck="for_value",
	)
	return sorted(set(rows))


def get_scope_departments(user: str | None = None) -> list[str]:
	"""Abteilungen, für die der User zuständig ist.

	Bevorzugt die hinterlegten User Permissions; fehlen sie, gilt die
	Abteilung aus dem Employee-Datensatz. Damit funktioniert die Anwendung
	auch, bevor jemand die Berechtigungen gepflegt hat -- ohne dabei mehr
	freizugeben als die eigene Abteilung.
	"""
	permitted = get_permitted_departments(user)
	if permitted:
		return permitted

	department = get_employee_department(user)
	return [department] if department else []


def has_any_role(roles: tuple[str, ...] | list[str], user: str | None = None) -> bool:
	return bool(set(roles) & set(frappe.get_roles(_user(user))))


def is_unrestricted(user: str | None = None) -> bool:
	"""Darf abteilungsübergreifend lesen (Geschäftsführung, System Manager)."""
	u = _user(user)
	if u == "Administrator":
		return True

	return has_any_role(UNRESTRICTED_ROLES, u)


def is_lead(user: str | None = None) -> bool:
	"""Abteilungsleiter -- sieht alle Tickets seiner Abteilung(en)."""
	return has_any_role((ROLE_LEAD,), user)


def get_access_level(user: str | None = None) -> str:
	"""Welche Sicht gilt für diesen User: 'all', 'department' oder 'own'.

	Die Reihenfolge ist bewusst absteigend: Wer mehrere Rollen hat, bekommt
	die weiteste davon.
	"""
	if is_unrestricted(user):
		return "all"
	if is_lead(user):
		return "department"

	return "own"
