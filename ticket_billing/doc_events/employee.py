"""Abteilungszuordnung eines Mitarbeiters in eine User Permission spiegeln.

Die User Permission ist es, die Frappe automatisch auf **jede** Abfrage
anwendet -- Liste, Report, REST. Sie von Hand zu pflegen wäre eine
Fehlerquelle: Wer die Abteilung wechselt, hätte sonst weiter Zugriff auf die
alte.
"""

import frappe

from ticket_billing.utils.context import is_unrestricted


def sync_department_permission(doc, method=None):
	user = doc.get("user_id")
	if not user or not frappe.db.exists("User", user):
		return

	# Geschäftsführung und System Manager sehen abteilungsübergreifend. Eine
	# User Permission würde sie einschränken -- auch System Manager sind
	# davon nicht ausgenommen, das ist ein verbreiteter Irrtum.
	if is_unrestricted(user):
		return

	wanted = {doc.get("department")} if doc.get("department") else set()

	existing = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": "Department"},
		fields=["name", "for_value"],
	)
	have = {row.for_value for row in existing}

	for row in existing:
		if row.for_value not in wanted:
			frappe.delete_doc("User Permission", row.name, ignore_permissions=True, force=True)

	for department in wanted - have:
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": user,
				"allow": "Department",
				"for_value": department,
				"apply_to_all_doctypes": 1,
			}
		).insert(ignore_permissions=True)
