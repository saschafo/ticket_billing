"""Einrichtung: Custom Fields, Rollen und Rechte.

Läuft bei ``after_install`` und bei jedem ``after_migrate``. Alles hier ist
idempotent -- mehrfaches Ausführen ändert nichts.

Warum nicht komplett als Fixtures: Rollen sind reine Stammdaten und liegen
deshalb als Fixture (``fixtures/role.json``) im Repository. Custom Fields und
Rechte auf **fremden** Doctypes (Issue, Timesheet, ...) sind dagegen als
Fixture heikel -- eine Änderung an der Feldreihenfolge in ERPNext genügt, und
der Import schlägt fehl oder überschreibt fremde Anpassungen. Als Code sind
sie versioniert, nachvollziehbar und robust gegen Änderungen im Upstream.
"""

import json

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from ticket_billing.constants import (
	DEFAULT_ACTIVITY_TYPE,
	FIELD_ASSIGNEE,
	FIELD_DEPARTMENT,
	FIELD_EMAIL_DEPARTMENT,
	FIELD_FIRST_RESPONSE,
	FIELD_ORIGIN,
	FIELD_RESOLVED,
	FIELD_TIMESHEET_ISSUE,
	ORIGIN_EXTERNAL,
	ORIGIN_INTERNAL,
	ROLE_EMPLOYEE,
	ROLE_LEAD,
	ROLE_MANAGEMENT,
)

# ---------------------------------------------------------------------------
# Custom Fields
# ---------------------------------------------------------------------------

CUSTOM_FIELDS = {
	"Issue": [
		{
			"fieldname": FIELD_DEPARTMENT,
			"label": "Responsible department",
			"fieldtype": "Link",
			"options": "Department",
			"insert_after": "subject",
			"reqd": 1,
			"in_standard_filter": 1,
			"in_list_view": 1,
			"description": "Determines who can see the ticket and who it is assigned to.",
		},
		{
			"fieldname": FIELD_ORIGIN,
			"label": "Origin",
			"fieldtype": "Select",
			"options": f"{ORIGIN_INTERNAL}\n{ORIGIN_EXTERNAL}",
			"default": ORIGIN_EXTERNAL,
			"insert_after": FIELD_DEPARTMENT,
			"reqd": 1,
			"in_standard_filter": 1,
		},
		{
			"fieldname": FIELD_ASSIGNEE,
			"label": "Assigned employee",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "customer",
			"in_standard_filter": 1,
			"in_list_view": 1,
			# ERPNext legt zu jedem Employee mit Benutzerkonto automatisch
			# eine User Permission "Employee: <eigener Datensatz>" an, damit
			# niemand fremde Personalakten sieht. Frappe wendet die auf JEDES
			# Link-Feld nach Employee an -- also auch auf dieses. Ohne diese
			# Zeile sähe ein Abteilungsleiter nur die Tickets, die auf ihn
			# selbst laufen, statt alle seiner Abteilung.
			#
			# Die Abteilungsgrenze bleibt davon unberührt: Sie hängt an
			# tb_department und der User Permission auf Department. Wer welche
			# Tickets darin sieht, entscheidet permissions.py.
			"ignore_user_permissions": 1,
			"description": "Set automatically. The department lead can reassign at any time.",
		},
		# Zeitstempel für die Kennzahlen. Sie entstehen aus dem Statusverlauf
		# und werden nicht von Hand gepflegt -- deshalb schreibgeschützt.
		{
			"fieldname": FIELD_FIRST_RESPONSE,
			"label": "First response at",
			"fieldtype": "Datetime",
			"insert_after": "opening_time",
			"read_only": 1,
			"description": "First status change after the ticket was created.",
		},
		{
			"fieldname": FIELD_RESOLVED,
			"label": "Resolved at",
			"fieldtype": "Datetime",
			"insert_after": FIELD_FIRST_RESPONSE,
			"read_only": 1,
			"description": "Set when the ticket reaches Resolved or Closed; cleared if it is reopened.",
		},
	],
	"Timesheet Detail": [
		{
			"fieldname": FIELD_TIMESHEET_ISSUE,
			"label": "Ticket",
			"fieldtype": "Link",
			"options": "Issue",
			"insert_after": "task",
		},
	],
	"Email Account": [
		{
			"fieldname": FIELD_EMAIL_DEPARTMENT,
			"label": "Department for incoming tickets",
			"fieldtype": "Link",
			"options": "Department",
			"insert_after": "append_to",
			"depends_on": "eval:doc.enable_incoming",
			"description": (
				"Tickets from this mailbox get this department. "
				"Without an entry the default department from Ticket Billing Settings applies."
			),
		},
	],
}


# ---------------------------------------------------------------------------
# Rechte
#
# Was eine Rolle grundsätzlich darf. Die Einschränkung auf einzelne Zeilen
# (eigene Tickets bzw. eigene Abteilung) passiert getrennt davon in
# permissions.py -- diese Tabelle ist die Obergrenze.
# ---------------------------------------------------------------------------

READ = {"read": 1, "report": 1, "export": 1}
WRITE = {**READ, "write": 1, "create": 1, "email": 1, "share": 1}

PERMISSIONS = {
	# Kernobjekte
	"Issue": {
		ROLE_EMPLOYEE: WRITE,
		ROLE_LEAD: {**WRITE, "delete": 1},
		# Geschäftsführung liest abteilungsübergreifend, bearbeitet aber nicht.
		ROLE_MANAGEMENT: READ,
	},
	# Mitarbeiter dürfen löschen -- aber nur eigene Entwürfe: Die Zeile
	# darauf schränkt permissions.py ein, und gebuchte Belege schützt Frappe
	# selbst (löschen erst nach Stornierung). Buchen dürfen sie nicht, dafür
	# fehlt "submit" hier bewusst.
	"Timesheet": {
		ROLE_EMPLOYEE: {**WRITE, "delete": 1},
		ROLE_LEAD: {**WRITE, "delete": 1, "submit": 1, "cancel": 1},
		ROLE_MANAGEMENT: READ,
	},
	# Stammdaten, ohne die die Oberfläche keine Namen auflösen kann.
	"Employee": {
		ROLE_EMPLOYEE: READ,
		ROLE_LEAD: READ,
		ROLE_MANAGEMENT: READ,
	},
	"Department": {
		ROLE_EMPLOYEE: READ,
		ROLE_LEAD: READ,
		ROLE_MANAGEMENT: READ,
	},
	"Activity Type": {
		ROLE_EMPLOYEE: READ,
		ROLE_LEAD: READ,
	},
	"Issue Type": {
		ROLE_EMPLOYEE: READ,
		ROLE_LEAD: READ,
		ROLE_MANAGEMENT: READ,
	},
	"Issue Priority": {
		ROLE_EMPLOYEE: READ,
		ROLE_LEAD: READ,
		ROLE_MANAGEMENT: READ,
	},
	"Customer": {
		ROLE_EMPLOYEE: READ,
		ROLE_LEAD: READ,
		ROLE_MANAGEMENT: READ,
	},
}


def ensure_roles() -> None:
	"""Rollen anlegen, falls das Fixture noch nicht gelaufen ist.

	Die Rechtevergabe unten braucht sie -- auf die Reihenfolge von
	Fixture-Import und after_install zu bauen wäre unnötig fragil.
	"""
	for role in (ROLE_EMPLOYEE, ROLE_LEAD, ROLE_MANAGEMENT):
		if frappe.db.exists("Role", role):
			continue

		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role,
				"desk_access": 0,
				"is_custom": 1,
			}
		).insert(ignore_permissions=True)


def setup_custom_fields() -> None:
	create_custom_fields(CUSTOM_FIELDS, update=True)


def setup_property_setters() -> None:
	"""Anpassungen an Standardfeldern fremder Doctypes.

	``Timesheet.employee``: ERPNext legt zu jedem Employee mit Benutzerkonto
	eine User Permission auf sich selbst an, und Frappe wendet die auf jedes
	Link-Feld nach Employee an. Ohne diese Ausnahme käme ein Abteilungsleiter
	an die Zeiteinträge seiner Mitarbeiter nicht heran -- weder lesend noch
	zum Buchen -- und die Freigabe wäre unmöglich.

	Die Einschränkung geht dadurch nicht verloren, sie wandert nur: Wer welche
	Timesheets sieht und ändern darf, entscheidet permissions.py (eigene bzw.
	die der eigenen Abteilung).
	"""
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	make_property_setter(
		"Timesheet",
		"employee",
		"ignore_user_permissions",
		1,
		"Check",
		validate_fields_for_doctype=False,
	)

	# ``Issue.recipient_account_field``: Beim Anlegen eines Tickets aus einer
	# eingehenden E-Mail trägt Frappe das empfangende Postfach in genau das
	# Feld ein, das hier benannt ist (siehe _create_reference_document in
	# frappe/email/receive.py). ERPNext setzt die Eigenschaft nicht -- das Feld
	# email_account bleibt dadurch leer, obwohl es existiert.
	#
	# Ohne diese Zeile kann die Abteilung nicht aus dem Postfach abgeleitet
	# werden: Der Hook findet kein Konto und bricht mit "Abteilung fehlt" ab,
	# also genau beim Weg, für den die Zuordnung gedacht ist.
	make_property_setter(
		"Issue",
		None,
		"recipient_account_field",
		"email_account",
		"Data",
		for_doctype=True,
		validate_fields_for_doctype=False,
	)


def setup_permissions() -> None:
	for doctype, roles in PERMISSIONS.items():
		if not frappe.db.exists("DocType", doctype):
			# Etwa Activity Type ohne installiertes Projects-Modul.
			continue

		for role, rights in roles.items():
			add_permission(doctype, role, 0)
			for right, value in rights.items():
				update_permission_property(doctype, role, 0, right, value, validate=False)


def _ensure_activity_type() -> str:
	"""Eine Tätigkeit für Zeiteinträge festlegen.

	ERPNext verlangt beim **Buchen** eines Timesheets zwingend eine
	Leistungsart. Fehlt sie, entstehen Entwürfe ganz normal -- und erst die
	Freigabe scheitert, also an der Stelle, an der es am meisten stört. Darum
	wird sie hier von vornherein gesetzt: eine vorhandene, sonst eine neue.
	"""
	# Bewusst keine beliebige vorhandene Tätigkeit: ERPNext liefert Werte wie
	# "Communication" oder "Proposal Writing" mit, und irgendeine davon zu
	# greifen ergäbe eine Auswertung, die niemand versteht. Lieber eine eigene,
	# die sagt, worum es geht.
	#
	# Ohne Stundensatz: Der ist eine Preisentscheidung und gehört nicht in
	# eine Installationsroutine. Bis jemand einen einträgt, entstehen
	# Rechnungen mit Betrag 0 -- sichtbar falsch statt still falsch.
	if frappe.db.exists("Activity Type", DEFAULT_ACTIVITY_TYPE):
		return DEFAULT_ACTIVITY_TYPE

	doc = frappe.get_doc(
		{"doctype": "Activity Type", "activity_type": DEFAULT_ACTIVITY_TYPE}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def ensure_settings() -> None:
	"""Einstellungen mit sinnvollen Startwerten füllen.

	Läuft auch bei jeder Migration: Ein neues Feld bekommt in einem bereits
	bestehenden Single-Doctype **nicht** automatisch den Default aus der
	Feldbeschreibung -- es stünde sonst auf 0 bzw. leer. Gefüllt wird nur,
	was leer ist; bewusst gesetzte Werte bleiben unangetastet.
	"""
	settings = frappe.get_single("Ticket Billing Settings")

	if not settings.assignment_strategy:
		settings.assignment_strategy = "by_workload"
	if settings.auto_assign is None:
		settings.auto_assign = 1
	if not settings.timer_warning_hours:
		settings.timer_warning_hours = 4
	if not settings.draft_reminder_days:
		settings.draft_reminder_days = 3
	if not settings.default_activity_type:
		settings.default_activity_type = _ensure_activity_type()

	settings.flags.ignore_permissions = True
	settings.save(ignore_permissions=True)


def allow_overlapping_time_entries() -> None:
	"""ERPNexts Überlappungsprüfung für Zeiteinträge abschalten.

	ERPNext lehnt zwei Zeiteinträge desselben Mitarbeiters ab, deren
	Zeiträume sich überschneiden. Das passt zu einer Erfassung, in der die
	Uhrzeiten die tatsächliche Arbeitszeit abbilden.

	Hier sind sie das nicht: Erfasst wird eine **Dauer** -- per Timer oder von
	Hand nachgetragen -- und die Uhrzeiten sind nur der Rahmen, in den sie
	geschrieben wird. Zwei Buchungen mit überlappendem Rahmen sind damit
	normal: eine nachgetragene Stunde neben einem gelaufenen Timer, oder eine
	Dauer, die beim Korrigieren über den nächsten Eintrag hinausreicht. Mit
	der Prüfung schlüge das mit einer Meldung fehl, die im Zusammenhang
	dieser Anwendung nicht zu verstehen ist.

	Die Einstellung gilt für die ganze Site. Wer die Prüfung zurück will,
	entfernt in den Projects Settings den Haken -- dann müssen sich die
	Zeiträume aber tatsächlich vertragen.
	"""
	if frappe.db.get_single_value("Projects Settings", "ignore_employee_time_overlap"):
		return

	frappe.db.set_single_value("Projects Settings", "ignore_employee_time_overlap", 1)



def setup_workspace() -> None:
	"""Arbeitsbereich im Desk anlegen oder aktualisieren.

	Als Code statt als Fixture, aus demselben Grund wie die Custom Fields:
	Ein Fixture wird beim Import stumpf ueberschrieben und traegt Verweise
	mit, die auf einer anderen Anlage nicht existieren.

	Der Bereich richtet sich an Administratoren, die im Desk arbeiten. Die
	taegliche Arbeit findet in der Vue-Oberflaeche statt -- dorthin fuehrt
	die Kachel im App-Umschalter.
	"""
	verknuepfungen = [
		# (Beschriftung, Doctype, Farbe)
		(_("Tickets"), "Issue", "Blue"),
		(_("Time Entries"), "Timesheet", "Green"),
		(_("Settings"), "Ticket Billing Settings", "Grey"),
	]

	karten = [
		(
			_("Cases"),
			[
				("Issue", "DocType"),
				("Ticket Timer", "DocType"),
				("Department", "DocType"),
				("Employee", "DocType"),
			],
		),
		(
			_("Billing"),
			[
				("Timesheet", "DocType"),
				("Activity Type", "DocType"),
				("Sales Invoice", "DocType"),
				("Customer", "DocType"),
			],
		),
		(
			_("Administration"),
			[
				("Ticket Billing Settings", "DocType"),
				("Email Account", "DocType"),
				("Ticket Billing Demo Record", "DocType"),
			],
		),
	]

	inhalt = [
		{
			"id": "tb_kopf",
			"type": "header",
			"data": {"text": f'<span class="h4">{_("Ticket Billing")}</span>', "col": 12},
		}
	]
	for i, (label, _dt, _farbe) in enumerate(verknuepfungen):
		inhalt.append(
			{"id": f"tb_sc_{i}", "type": "shortcut", "data": {"shortcut_name": label, "col": 4}}
		)
	inhalt.append({"id": "tb_luft", "type": "spacer", "data": {"col": 12}})
	for i, (label, _eintraege) in enumerate(karten):
		inhalt.append(
			{"id": f"tb_card_{i}", "type": "card", "data": {"card_name": label, "col": 4}}
		)

	if frappe.db.exists("Workspace", "Ticket Billing"):
		doc = frappe.get_doc("Workspace", "Ticket Billing")
	else:
		doc = frappe.new_doc("Workspace")
		doc.name = "Ticket Billing"

	doc.label = "Ticket Billing"
	doc.title = "Ticket Billing"
	doc.module = "Ticket Billing"
	doc.icon = "support"
	doc.public = 1
	doc.sequence_id = 30
	doc.content = json.dumps(inhalt)

	doc.set("shortcuts", [])
	for label, doctype, farbe in verknuepfungen:
		doc.append(
			"shortcuts",
			{"label": label, "type": "DocType", "link_to": doctype, "color": farbe},
		)

	# Die Kartenueberschrift ist selbst eine Zeile vom Typ "Card Break"; die
	# Eintraege darunter gehoeren so lange dazu, bis die naechste folgt.
	doc.set("links", [])
	for label, eintraege in karten:
		doc.append(
			"links",
			{"label": label, "type": "Card Break", "link_count": len(eintraege), "hidden": 0},
		)
		for ziel, art in eintraege:
			doc.append(
				"links",
				{
					"label": _(ziel),
					"type": "Link",
					"link_type": art,
					"link_to": ziel,
					"hidden": 0,
					"is_query_report": 0,
					"onboard": 0,
				},
			)

	doc.flags.ignore_permissions = True
	doc.flags.ignore_links = True
	doc.save()


def setup_app_icon() -> None:
	"""Kachel im App-Umschalter anlegen.

	Frappe wertet den Hook ``add_to_apps_screen`` nur beim Installieren der
	App aus und legt daraus einen ``Desktop Icon`` an. Kommt der Hook
	spaeter dazu -- oder wurde die App vor seiner Einfuehrung installiert --,
	entsteht nie ein Symbol, und die App fehlt im Umschalter, obwohl der
	Hook korrekt registriert ist.

	Aufgerufen wird nur die Routine fuer Apps: Sie ueberspringt, was schon
	ein Symbol hat, ist also wiederholbar. Das Gegenstueck fuer
	Arbeitsbereiche prueft das nicht und legt bei jedem Lauf neue Saetze an.
	"""
	try:
		from frappe.desk.doctype.desktop_icon.desktop_icon import (
			create_desktop_icons_from_installed_apps,
		)
	except ImportError:
		# Aeltere Frappe-Fassungen kennen den Mechanismus nicht.
		return

	create_desktop_icons_from_installed_apps()

def after_install() -> None:
	ensure_roles()
	setup_custom_fields()
	setup_property_setters()
	setup_permissions()
	ensure_settings()
	setup_workspace()
	setup_app_icon()
	allow_overlapping_time_entries()
	frappe.db.commit()


def after_migrate() -> None:
	"""Nach jeder Migration nachziehen.

	Neue Felder und Rechte aus einer neuen App-Version landen damit ohne
	Handgriff auf bestehenden Sites.
	"""
	ensure_roles()
	setup_custom_fields()
	setup_property_setters()
	setup_permissions()
	ensure_settings()
	setup_workspace()
	setup_app_icon()
	allow_overlapping_time_entries()
	frappe.db.commit()
