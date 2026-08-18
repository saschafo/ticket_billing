"""Posteingang auf Zuruf abrufen.

Der Zeitplan holt alle zehn Minuten. Wer auf eine Kundenantwort wartet,
will nicht so lange warten -- dafür gibt es diesen Aufruf.
"""

import frappe
from frappe import _

from ticket_billing.constants import TICKET_ROLES
from ticket_billing.utils.context import has_any_role

# Die Sperre gilt für alle gemeinsam, nicht je Benutzer: Belastet wird der
# Mailserver, und zehn Leute, die gleichzeitig klicken, sollen daraus nicht
# zehn Verbindungen machen. Zehn Sekunden reichen -- ein Abruf dauert
# gemessen 0,25 Sekunden je Postfach.
MIN_ABSTAND_SEKUNDEN = 10
SPERRE = "ticket_billing:letzter_mailabruf"


@frappe.whitelist()
def fetch_mail() -> dict:
	"""Alle Posteingänge abrufen und melden, was dazugekommen ist.

	Die Rechteprüfung steht hier und nicht in der Oberfläche: Ein
	ausgeblendeter Knopf ist keine Sperre.
	"""
	if not has_any_role(TICKET_ROLES):
		frappe.throw(
			_("Sie dürfen den Posteingang nicht abrufen."), frappe.PermissionError
		)

	cache = frappe.cache()
	if cache.get_value(SPERRE):
		return {"throttled": True, "new_messages": 0, "failed": []}

	cache.set_value(SPERRE, 1, expires_in_sec=MIN_ABSTAND_SEKUNDEN)

	from frappe.email.doctype.email_account.email_account import EmailAccount

	vorher = frappe.db.count("Communication", {"sent_or_received": "Received"})

	failed = []

	# Kein frappe.set_user hier: Es ueberschreibt session.sid und leert die
	# Sitzungsdaten. Innerhalb einer Anfrage macht das die Anmeldung des
	# Aufrufers ungueltig -- die naechste Anfrage kam als Guest zurueck,
	# mit 'User None not found'.
	#
	# Noetig war es ohnehin nicht: Dass ein Ticket in der Abteilung des
	# Postfachs landet und nicht in der des Abrufenden, stellt
	# set_department sicher -- dort hat das Postfach Vorrang vor der
	# Vorbelegung aus den Benutzerrechten.
	for name in frappe.get_all("Email Account", filters={"enable_incoming": 1}, pluck="name"):
		try:
			EmailAccount.find(name).receive()
		except Exception:
			# Ein unerreichbares Postfach haelt die anderen nicht auf.
			failed.append(name)
			frappe.log_error(
				title=f"ticket_billing: Abruf von {name} fehlgeschlagen",
				message=frappe.get_traceback(),
			)

	nachher = frappe.db.count("Communication", {"sent_or_received": "Received"})

	return {
		"throttled": False,
		"new_messages": max(0, nachher - vorher),
		"failed": failed,
	}
