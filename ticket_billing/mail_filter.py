"""Rückläufer und andere Systemmeldungen aus dem Posteingang aussortieren.

Ein Zustellfehler kommt als Mail vom Mailsystem zurück. Ohne Zutun legt
Frappe dafür ein neues Ticket an und die automatische Zuweisung schiebt es
einem Mitarbeiter in die Liste -- die Störungsmeldung sieht dann aus wie eine
Kundenanfrage.

Verworfen wird sie trotzdem nicht: Dass eine Antwort den Empfänger nicht
erreicht hat, gehört an das ursprüngliche Ticket. Nur das leere Ticket, das
Frappe nebenbei angelegt hat, fällt weg.
"""

import re

import frappe

# Verglichen wird nur der Teil vor dem @: Der Hostname wechselt je nach
# Mailserver ("mailer-daemon@mail.example.org", "MAILER-DAEMON@gmail.com").
SYSTEM_LOCAL_PARTS = frozenset(
	{
		"mailer-daemon",
		"postmaster",
		"no-reply",
		"noreply",
		"do-not-reply",
		"bounce",
		"bounces",
	}
)

# Der Ticketname steht im Rückläufer, weil die zitierte Originalmail den
# Abmeldelink mit "...&name=ISS-..." enthält. Das ist ein systemseitiger
# Anker, kein Zufallsfund im Text.
TICKET_NAME = re.compile(r"\bISS-\d{4}-\d+\b")


def is_system_sender(address: str | None) -> bool:
	"""Steckt hinter der Adresse ein Automat statt eines Menschen?"""
	local = (address or "").split("@")[0].strip().strip("<>").lower()
	return local in SYSTEM_LOCAL_PARTS


def route_system_mail(doc, method=None) -> None:
	"""Hook für ``after_insert`` auf Communication.

	Fehler werden geloggt, nicht geworfen: Ein Rückläufer darf den Abruf des
	ganzen Postfachs nicht blockieren. Im schlimmsten Fall bleibt ein
	überflüssiges Ticket stehen -- sichtbar und von Hand aufräumbar.
	"""
	if doc.sent_or_received != "Received" or doc.reference_doctype != "Issue":
		return
	if not is_system_sender(doc.sender):
		return

	try:
		_route(doc)
	except Exception:
		frappe.log_error(
			title="ticket_billing: Rückläufer konnte nicht zugeordnet werden",
			message=frappe.get_traceback(),
		)


def _route(doc) -> None:
	placeholder = doc.reference_name
	original = _original_ticket(doc, exclude=placeholder)

	if original:
		# db_set statt save(): Der Verlauf soll umgehängt werden, ohne die
		# Hooks auf Communication erneut auszulösen.
		doc.db_set("reference_name", original, update_modified=False)
		_discard(placeholder)
	else:
		_park(placeholder)


def _original_ticket(doc, exclude: str | None) -> str | None:
	"""Das Ticket, dessen Antwort an den Aussteller zurückkam.

	Die Adresse des Ausstellers muss im Rückläufer vorkommen, sonst ging die
	gescheiterte Mail an jemand anderen. Ohne diese Bedingung landete auch
	eine fehlgeschlagene interne Benachrichtigung im Kundenverlauf -- der
	Bearbeiter läse dort eine Störung, die den Kunden nie betraf.
	"""
	content = doc.content or ""
	for name in TICKET_NAME.findall(content):
		if name == exclude or not frappe.db.exists("Issue", name):
			continue

		aussteller = frappe.db.get_value("Issue", name, "raised_by")
		if aussteller and aussteller.lower() in content.lower():
			return name
	return None


def _discard(name: str | None) -> None:
	"""Das nebenbei angelegte Ticket entfernen, sofern es leer geblieben ist."""
	if not name or not frappe.db.exists("Issue", name):
		return

	# Hängt noch etwas anderes daran, war es doch kein reiner Rückläufer.
	if frappe.db.count("Communication", {"reference_doctype": "Issue", "reference_name": name}):
		_park(name)
		return

	frappe.delete_doc("Issue", name, ignore_permissions=True, delete_permanently=True)


def _park(name: str | None) -> None:
	"""Nicht zuzuordnen: schließen, damit es in keiner Arbeitsliste steht."""
	if not name or not frappe.db.exists("Issue", name):
		return

	frappe.db.set_value("Issue", name, "status", "Closed", update_modified=False)
	for todo in frappe.get_all(
		"ToDo",
		filters={"reference_type": "Issue", "reference_name": name, "status": "Open"},
		pluck="name",
	):
		frappe.db.set_value("ToDo", todo, "status", "Cancelled", update_modified=False)
