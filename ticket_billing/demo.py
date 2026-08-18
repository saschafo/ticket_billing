"""Demo-Daten anlegen und restlos wieder entfernen.

**Nur für Demonstration und Test.** Die Demo-Benutzer haben ein bekanntes
Passwort, und solange die Daten installiert sind, bietet die Anmeldeseite
Schnell-Logins für sie an. Auf einer Anlage mit echten Daten hat das nichts
zu suchen.

Der Kern ist die Nachverfolgung: Jeder angelegte Datensatz wird in
``Ticket Billing Demo Record`` vermerkt, und nur was dort steht, wird beim
Entfernen gelöscht. Ein Abgleich über Namen oder Muster wäre gefährlich --
ein echtes Ticket mit demselben Betreff verschwände mit.
"""

import random

import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, flt, get_datetime, now_datetime

from ticket_billing.constants import (
	CLOSED_STATUSES,
	DEFAULT_ACTIVITY_TYPE,
	FIELD_ASSIGNEE,
	FIELD_DEPARTMENT,
	FIELD_FIRST_RESPONSE,
	FIELD_ORIGIN,
	FIELD_RESOLVED,
	ORIGIN_EXTERNAL,
	ORIGIN_INTERNAL,
	ROLE_EMPLOYEE,
	ROLE_LEAD,
	ROLE_MANAGEMENT,
)

TRACKER = "Ticket Billing Demo Record"

#: Bekanntes Passwort. Es steht hier im Klartext, weil es genau dafür da ist:
#: eine Demo, in die man ohne Zugangsdaten hineinkommt.
DEMO_PASSWORD = "demo1234"

DEMO_DEPARTMENTS = ["Support", "Buchhaltung"]

DEMO_USERS = [
	{
		"email": "anna@demo.local",
		"first_name": "Anna",
		"last_name": "Berger",
		"roles": [ROLE_EMPLOYEE],
		"department": "Support",
		"role_label": "Mitarbeiterin Support",
	},
	{
		"email": "ben@demo.local",
		"first_name": "Ben",
		"last_name": "Krause",
		"roles": [ROLE_EMPLOYEE],
		"department": "Support",
		"role_label": "Mitarbeiter Support",
	},
	{
		"email": "lea@demo.local",
		"first_name": "Lea",
		"last_name": "Hoffmann",
		"roles": [ROLE_EMPLOYEE, ROLE_LEAD],
		"department": "Support",
		"role_label": "Abteilungsleiterin Support",
	},
	{
		"email": "carl@demo.local",
		"first_name": "Carl",
		"last_name": "Ziegler",
		"roles": [ROLE_EMPLOYEE, ROLE_LEAD],
		"department": "Buchhaltung",
		"role_label": "Abteilungsleiter Buchhaltung",
	},
	{
		"email": "gabi@demo.local",
		"first_name": "Gabi",
		"last_name": "Sommer",
		"roles": [ROLE_MANAGEMENT],
		"department": None,
		"role_label": "Geschäftsführung",
	},
]

DEMO_CUSTOMERS = ["Nordlicht Handel GmbH", "Kanzlei Weber & Partner", "Stadtwerke Musterstadt"]

#: Stundensätze je Leistungsart -- **Platzhalter für Demo und Test**.
#:
#: Der Satz hängt an der Leistungsart und nicht am Mitarbeiter. ERPNext sucht
#: beim Buchen zuerst einen ``Activity Cost`` für die Kombination aus
#: Mitarbeiter und Leistungsart und fällt erst dann auf die Sätze zurück, die
#: direkt am ``Activity Type`` stehen. Ein Activity Cost ohne Mitarbeiter
#: würde nie gefunden -- die Sätze gehören deshalb an die Leistungsart.
DEMO_ACTIVITY_RATES = [
	{"activity_type": DEFAULT_ACTIVITY_TYPE, "billing_rate": 75.0, "costing_rate": 45.0},
	{"activity_type": "Beratung", "billing_rate": 120.0, "costing_rate": 70.0},
]

#: Dienstleistungsartikel für die Rechnungsposition. ERPNext fragt ihn beim
#: Erzeugen einer Rechnung aus einem Timesheet ab.
DEMO_ITEM = {
	"item_code": "Support-Stunde",
	"item_name": "Support-Stunde (Demo)",
	"item_group": "Services",
	"stock_uom": "Hour",
	"description": "Platzhalter-Artikel aus den Demo-Daten. Vor echtem Einsatz ersetzen.",
}

SUBJECTS = {
	"Support": [
		"Anmeldung schlägt fehl",
		"Drucker wird nicht gefunden",
		"Export bricht mit Fehler ab",
		"Bitte um Zugriff auf das Projektlaufwerk",
		"Rechner startet sehr langsam",
		"E-Mail-Weiterleitung einrichten",
		"Passwort zurücksetzen",
		"Neue Arbeitsstation einrichten",
		"VPN-Verbindung instabil",
		"Software-Update einspielen",
		"Bildschirm bleibt schwarz",
		"Telefonanlage nimmt keine Anrufe an",
		"Freigabe für Netzlaufwerk erweitern",
		"Backup ist nicht durchgelaufen",
		"Zwei-Faktor-Anmeldung einrichten",
		"Dateien aus Papierkorb wiederherstellen",
		"Lizenz läuft ab",
		"Neuer Mitarbeiter braucht Zugänge",
	],
	"Buchhaltung": [
		"Rechnung doppelt gestellt",
		"Mahnung trotz Zahlung erhalten",
		"Kontierung einer Eingangsrechnung unklar",
		"Umsatzsteuervoranmeldung prüfen",
		"Reisekostenabrechnung nachreichen",
		"Zahlungsziel anpassen",
		"Gutschrift wurde nicht verrechnet",
		"Skonto falsch berechnet",
		"Bankverbindung des Kunden geändert",
		"Offene Posten abstimmen",
		"Rechnungsanschrift korrigieren",
		"Dauerauftrag einrichten",
	],
}


# ---------------------------------------------------------------------------
# Nachverfolgung
# ---------------------------------------------------------------------------


def _silence_notifications(user: str) -> None:
	"""Demo-Benutzer bekommen keine E-Mail.

	Die Adressen enden auf @demo.local und existieren nicht. Jede
	Benachrichtigung an sie kommt als Rückläufer zurück, landet im
	Posteingang und muss dort wieder aussortiert werden -- Aufwand ohne
	jeden Nutzen.
	"""
	frappe.db.set_value("User", user, {"thread_notify": 0, "send_me_a_copy": 0})

	settings = frappe.db.exists("Notification Settings", user)
	if settings:
		frappe.db.set_value("Notification Settings", settings, "enabled", 0)


def _track(doctype: str, name: str, order: int) -> None:
	"""Einen Satz als Eigentum der Demo vermerken.

	Doppelte Einträge werden übersprungen: Ein abgebrochener Installations-
	lauf kann Sätze hinterlassen haben, die ein zweiter Anlauf erneut
	vermerken will.
	"""
	if frappe.db.exists(TRACKER, {"ref_doctype": doctype, "ref_name": name}):
		return

	frappe.get_doc(
		{
			"doctype": TRACKER,
			"ref_doctype": doctype,
			"ref_name": name,
			"sort_order": order,
			"batch": "demo",
		}
	).insert(ignore_permissions=True)


def is_installed() -> bool:
	"""Steht noch irgendetwas aus der Demo im System?

	Maßgeblich für die Warnung und die Schnell-Logins: Solange auch nur ein
	Demo-Benutzer existiert, kommt jemand ohne Passwort herein.
	"""
	return bool(frappe.db.count(TRACKER))


# Ausdrückliche Marke statt Rückschluss aus den Daten: Beim Entfernen bleibt
# liegen, woran echte Daten hängen -- ein Mitarbeiter auf einem echten
# Ticket, ein Kunde mit Rechnung. Selbst ein Demo-Ticket kann überleben,
# wenn eine gebuchte Zeit daran hängt. Zählte man solche Reste als
# "installiert", käme man nie wieder in einen sauberen Zustand: Entfernen
# räumt nichts mehr weg, Installieren verweigert den Dienst.
DEMO_MARKE = "ticket_billing_demo_vollstaendig"


def is_complete() -> bool:
	"""Wurde eine vollständige Installation durchgeführt und nicht entfernt?"""
	return frappe.db.get_default(DEMO_MARKE) == "1"


def _require_admin() -> None:
	"""Nur Administratoren. Die Funktion legt Benutzer an und löscht Daten."""
	if "System Manager" not in frappe.get_roles(frappe.session.user):
		frappe.throw(
			_("Only administrators can manage demo data."), frappe.PermissionError
		)


# ---------------------------------------------------------------------------
# Anlegen
# ---------------------------------------------------------------------------


def _company() -> tuple[str, str]:
	company = frappe.db.get_value("Company", {}, "name")
	if not company:
		frappe.throw(
			_("No company exists. Run the ERPNext setup wizard first."),
			title=_("Setup incomplete"),
		)
	return company, frappe.db.get_value("Company", company, "abbr")


def _create_departments(company: str, abbr: str, counter) -> dict[str, str]:
	result = {}
	for name in DEMO_DEPARTMENTS:
		full = f"{name} - {abbr}"
		if not frappe.db.exists("Department", full):
			doc = frappe.get_doc(
				{
					"doctype": "Department",
					"department_name": name,
					"company": company,
					"is_group": 0,
				}
			).insert(ignore_permissions=True)
			_track("Department", doc.name, next(counter))
			full = doc.name
		result[name] = full
	return result


def _create_users(company: str, departments: dict, counter) -> dict[str, str]:
	"""Benutzer und Mitarbeiterdatensätze anlegen.

	Der Employee-Hook spiegelt die Abteilung anschließend in eine User
	Permission -- die entsteht also von selbst und wird über das Löschen des
	Employees wieder mit abgeräumt.
	"""
	from frappe.utils.password import update_password

	employees = {}

	for spec in DEMO_USERS:
		# Auch schon vorhandene Demo-Benutzer werden vermerkt. Ein
		# abgebrochener Lauf hinterlässt sonst Waisen: Benutzer, die die
		# Demo angelegt hat, die aber niemand mehr entfernen kann, weil sie
		# in keiner Liste stehen.
		if frappe.db.exists("User", spec["email"]):
			_track("User", spec["email"], next(counter))

		if not frappe.db.exists("User", spec["email"]):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": spec["email"],
					"first_name": spec["first_name"],
					"last_name": spec["last_name"],
					"send_welcome_email": 0,
					"user_type": "System User",
					"roles": [{"role": r} for r in spec["roles"]],
				}
			)
			user.flags.ignore_permissions = True
			user.insert()
			_track("User", user.name, next(counter))
			_silence_notifications(user.name)

		update_password(spec["email"], DEMO_PASSWORD)

		# Frappe legt zu jedem Benutzer automatisch einen Kontakt an. Der
		# verweist auf den Benutzer und verhindert dessen Löschung -- ohne
		# ihn mitzuerfassen bliebe jeder Demo-Benutzer stehen.
		for contact in _contacts_of(spec["email"]):
			_track("Contact", contact, next(counter))

		if not spec["department"]:
			continue

		# Ein Mitarbeiter kann eine frühere Entfernung überlebt haben, weil
		# ein echtes Ticket auf ihn zeigt. Dann wird er weiterverwendet:
		# ERPNext lässt pro Benutzer ohnehin nur einen zu, und ein zweiter
		# Anlauf bräche die ganze Installation ab.
		vorhanden = frappe.db.get_value("Employee", {"user_id": spec["email"]}, "name")
		if vorhanden:
			employee_name = vorhanden
			frappe.db.set_value(
				"Employee",
				vorhanden,
				{"status": "Active", "department": departments[spec["department"]]},
			)
		else:
			employee_name = frappe.get_doc(
				{
					"doctype": "Employee",
					"first_name": spec["first_name"],
					"last_name": spec["last_name"],
					"gender": "Other",
					"date_of_birth": "1990-01-01",
					"date_of_joining": "2024-01-01",
					"company": company,
					"status": "Active",
					"user_id": spec["email"],
					"department": departments[spec["department"]],
				}
			).insert(ignore_permissions=True).name

		_track("Employee", employee_name, next(counter))
		employees[spec["email"]] = employee_name

		# ERPNext und unser eigener Hook legen zum Mitarbeiter User
		# Permissions an (Company, Employee, Department). Sie entstehen erst
		# beim Speichern, werden also hier eingesammelt -- und weil sie nach
		# dem Mitarbeiter erfasst werden, verschwinden sie beim Entfernen
		# vor ihm. Andersherum blockierten sie seine Löschung.
		for permission in frappe.get_all(
			"User Permission", filters={"user": spec["email"]}, pluck="name"
		):
			_track("User Permission", permission, next(counter))

	return employees


def _contacts_of(user: str) -> list[str]:
	"""Kontakte, die auf ein Benutzerkonto verweisen."""
	return frappe.get_all("Contact", filters={"user": user}, pluck="name")


def _create_billing_basics(counter) -> None:
	"""Leistungsarten mit Stundensatz und den Dienstleistungsartikel anlegen.

	Damit ist der ERPNext-Standardweg "Timesheet → Sales Invoice" ohne
	Zusatzaufwand begehbar: Die Leistungsart liefert den Satz, der Artikel die
	Rechnungsposition.

	Die Beträge sind ausdrücklich Platzhalter. Legt die Demo eine Leistungsart
	selbst an, verschwindet sie beim Entfernen wieder; bestand sie schon
	(``Ticket-Support`` kommt aus der Installation), wird nur der Satz gesetzt
	und beim Entfernen auf null zurückgestellt -- ein Demo-Satz darf nicht in
	einer echten Rechnung landen.
	"""
	for spec in DEMO_ACTIVITY_RATES:
		name = spec["activity_type"]

		if not frappe.db.exists("Activity Type", name):
			doc = frappe.get_doc({"doctype": "Activity Type", "activity_type": name}).insert(
				ignore_permissions=True
			)
			_track("Activity Type", doc.name, next(counter))

		frappe.db.set_value(
			"Activity Type",
			name,
			{"billing_rate": spec["billing_rate"], "costing_rate": spec["costing_rate"]},
		)

	if not frappe.db.exists("Item", DEMO_ITEM["item_code"]):
		item = frappe.get_doc({"doctype": "Item", "is_stock_item": 0, **DEMO_ITEM})
		item.insert(ignore_permissions=True)
		_track("Item", item.name, next(counter))


def _reset_billing_rates() -> None:
	"""Demo-Stundensätze zurücksetzen.

	Betrifft nur Leistungsarten, die die Demo nicht selbst angelegt hat --
	die anderen sind zu diesem Zeitpunkt bereits gelöscht.
	"""
	for spec in DEMO_ACTIVITY_RATES:
		if frappe.db.exists("Activity Type", spec["activity_type"]):
			frappe.db.set_value(
				"Activity Type",
				spec["activity_type"],
				{"billing_rate": 0, "costing_rate": 0},
			)


def _create_customers(counter) -> list[str]:
	names = []
	for name in DEMO_CUSTOMERS:
		if frappe.db.exists("Customer", name):
			names.append(name)
			continue

		doc = frappe.get_doc(
			{"doctype": "Customer", "customer_name": name, "customer_type": "Company"}
		).insert(ignore_permissions=True)
		_track("Customer", doc.name, next(counter))
		names.append(doc.name)
	return names


#: Zeitraum der Demo-Daten. Eine Woche mehr als die zwölf, die das
#: Kennzahlen-Dashboard voreingestellt zeigt -- sonst ist der erste Punkt der
#: Kurve angeschnitten und fällt optisch ab.
DEMO_WEEKS = 13

#: Tickets je Mitarbeiter und Woche. Die Gewichtung erzeugt eine
#: Schwankung um vier bis fünf herum, mit gelegentlichen Ausreißern nach
#: oben. Ein fester Wert ergäbe eine gerade Linie, eine Gleichverteilung ein
#: Zickzack -- beides sieht nicht nach Betrieb aus.
TICKETS_PER_WEEK = ([2, 3, 4, 5, 6, 7, 8], [3, 5, 6, 6, 4, 2, 1])


def _status_for_age(weeks_ago: int, rng) -> str:
	"""Je älter ein Vorgang, desto wahrscheinlicher ist er erledigt.

	Ohne diesen Zusammenhang lägen frische und alte Tickets gleich häufig
	offen -- die Lösungszeit wäre dann Zufall statt Kennzahl.
	"""
	if weeks_ago >= 3:
		roll = rng.random()
		return rng.choice(CLOSED_STATUSES) if roll < 0.88 else "On Hold"

	if weeks_ago >= 1:
		roll = rng.random()
		if roll < 0.5:
			return rng.choice(CLOSED_STATUSES)
		return "Replied" if roll < 0.8 else "Open"

	roll = rng.random()
	if roll < 0.2:
		return rng.choice(CLOSED_STATUSES)
	return "Replied" if roll < 0.5 else "Open"


def _create_tickets(departments: dict, customers: list, counter) -> list[dict]:
	"""Tickets über die letzten Wochen streuen, je Mitarbeiter mehrere pro Woche.

	Der Bearbeiter wird bewusst schon beim Anlegen gesetzt: Die
	Zuweisungsregel verteilt nach Auslastung und käme damit auf eine sehr
	gleichmäßige Verteilung -- für eine Demo wäre das eine Kurvenschar, die
	übereinanderliegt. Ein gesetzter Bearbeiter lässt ``assign_issue`` sofort
	zurückkehren, was nebenbei einige hundert Abfragen spart.

	Datum und Status werden nach dem Anlegen zurückdatiert; über die
	Oberfläche ginge das nicht, weil die Felder schreibgeschützt sind.
	"""
	from ticket_billing.assignment import get_candidates

	rng = random.Random(20260817)
	created = []
	now = now_datetime()

	for dept_key, department in departments.items():
		subjects = SUBJECTS[dept_key]
		candidates = get_candidates(department)

		for candidate in candidates:
			for weeks_ago in range(DEMO_WEEKS):
				count = rng.choices(TICKETS_PER_WEEK[0], weights=TICKETS_PER_WEEK[1])[0]

				for _ in range(count):
					# Irgendwann in dieser Woche, zu einer Arbeitszeit.
					opened = add_to_date(
						now,
						days=-(weeks_ago * 7 + rng.randint(0, 6)),
						hours=-rng.randint(0, 9),
					)

					external = rng.random() < 0.6
					subject = rng.choice(subjects)

					doc = frappe.get_doc(
						{
							"doctype": "Issue",
							"subject": subject,
							FIELD_DEPARTMENT: department,
							FIELD_ORIGIN: ORIGIN_EXTERNAL if external else ORIGIN_INTERNAL,
							"customer": rng.choice(customers) if external else None,
							FIELD_ASSIGNEE: candidate.employee,
							"description": f"Demo-Vorgang: {subject}",
						}
					).insert(ignore_permissions=True)

					status = _status_for_age(weeks_ago, rng)
					response_after = rng.uniform(0.3, 16)
					resolve_after = response_after + rng.uniform(2, 80)

					values = {
						"creation": opened,
						"modified": opened,
						"opening_date": get_datetime(opened).date(),
						"status": status,
					}
					if status != "Open":
						values[FIELD_FIRST_RESPONSE] = add_to_date(opened, hours=response_after)
					if status in CLOSED_STATUSES:
						values[FIELD_RESOLVED] = add_to_date(opened, hours=resolve_after)
						values["modified"] = values[FIELD_RESOLVED]

					frappe.db.set_value("Issue", doc.name, values, update_modified=False)

					_track("Issue", doc.name, next(counter))
					created.append(
						{
							"name": doc.name,
							"department": department,
							"assignee": candidate.employee,
							"external": external,
							"opened": opened,
							"weeks_ago": weeks_ago,
						}
					)

	return created


def _create_time_entries(tickets: list, counter) -> None:
	"""Zeiteinträge in beiden Zuständen: Entwurf und gebucht.

	Gebucht wird über den regulären Weg (docstatus 1), damit die Demo auch
	die Freigabeansicht mit Inhalt füllt -- und nicht nur mit Entwürfen.
	"""
	rng = random.Random(4711)
	activity = frappe.db.get_single_value("Ticket Billing Settings", "default_activity_type")

	for ticket in tickets:
		# Nicht auf jedem Ticket wurde Zeit erfasst -- das ist auch im Betrieb
		# so, und bei 200 Vorgängen wären 200 Belege weder realistisch noch
		# übersichtlich.
		if not ticket["assignee"] or rng.random() > 0.3:
			continue

		employee = frappe.db.get_value(
			"Employee", ticket["assignee"], ["name", "company", "department"], as_dict=True
		)
		hours = round(rng.uniform(0.25, 4), 2)
		start = add_to_date(ticket["opened"], hours=rng.uniform(1, 30))
		customer = frappe.db.get_value("Issue", ticket["name"], "customer")

		sheet = frappe.get_doc(
			{
				"doctype": "Timesheet",
				"title": frappe.db.get_value("Issue", ticket["name"], "subject"),
				"employee": employee.name,
				"company": employee.company,
				"department": employee.department,
				"customer": customer,
				"time_logs": [
					{
						"activity_type": activity,
						"from_time": start,
						"to_time": add_to_date(start, hours=hours),
						"hours": hours,
						# Wie in der Anwendung: Zeit an einem externen Ticket
						# ist abrechenbar, sonst blockiert ERPNext später den
						# Weg zur Rechnung.
						"is_billable": 1 if customer else 0,
						"description": "Demo-Erfassung",
						"tb_issue": ticket["name"],
					}
				],
			}
		)
		sheet.insert(ignore_permissions=True)
		_track("Timesheet", sheet.name, next(counter))

		# Ältere Zeiten sind gebucht, frische warten noch auf die Freigabe.
		# So sieht die Freigabesicht aus wie ein normaler Wochenrückstand und
		# nicht wie ein zufälliges Gemisch aus allen Monaten.
		if ticket["weeks_ago"] >= 3 or rng.random() < 0.35:
			sheet.submit()


# ---------------------------------------------------------------------------
# Öffentliche Schnittstelle
# ---------------------------------------------------------------------------


@frappe.whitelist()
def install_demo_data():
	_require_admin()

	if is_complete():
		frappe.throw(
			_("Demo data is already installed. Remove it first."),
			title=_("Already installed"),
		)

	counter = iter(range(1, 100000))
	company, abbr = _company()

	departments = _create_departments(company, abbr, counter)
	_create_users(company, departments, counter)
	_create_billing_basics(counter)
	customers = _create_customers(counter)
	tickets = _create_tickets(departments, customers, counter)
	_create_time_entries(tickets, counter)

	frappe.db.set_default(DEMO_MARKE, "1")
	frappe.db.commit()

	return {
		"installed": True,
		"records": frappe.db.count(TRACKER),
		"tickets": len(tickets),
	}


@frappe.whitelist()
def remove_demo_data():
	"""Alles wieder entfernen, was die Installation angelegt hat.

	In umgekehrter Reihenfolge: Zuerst die Vorgänge, zuletzt Abteilungen und
	Benutzer. Andersherum blockierten Verweise das Löschen.
	"""
	_require_admin()

	records = frappe.get_all(
		TRACKER, fields=["name", "ref_doctype", "ref_name"], order_by="sort_order desc"
	)

	removed, failed = 0, []

	# Frappe reiht zu jedem gelöschten Dokument einen Aufräumjob ein
	# (delete_dynamic_links) -- und lehnt ab einer gewissen Warteschlangenlänge
	# neue Jobs ab. Bei ein paar hundert Datensätzen bricht das Entfernen
	# deshalb mittendrin ab, mit einer Meldung über Hintergrundjobs, die mit
	# der eigentlichen Sache nichts zu tun hat.
	#
	# ``now=frappe.in_test`` an der Enqueue-Stelle ist Frappes eigener
	# Schalter für "sofort statt später". Für einen Aufräumlauf ist genau das
	# richtig: Er dauert dadurch etwas länger, läuft aber vollständig durch.
	was_in_test = frappe.in_test
	frappe.in_test = True

	try:
		removed, failed = _delete_tracked(records)
	finally:
		frappe.in_test = was_in_test

	_reset_billing_rates()
	frappe.db.commit()

	# Die Marke faellt immer, auch wenn Saetze liegen blieben: Was hier
	# uebrig ist, haengt an echten Daten und wird nie mehr verschwinden.
	# Bliebe die Marke stehen, waere eine Neuinstallation fuer immer
	# gesperrt.
	frappe.db.set_default(DEMO_MARKE, "")
	frappe.db.commit()

	return {"removed": removed, "failed": failed, "remaining": frappe.db.count(TRACKER)}


def _delete_tracked(records: list) -> tuple[int, list]:
	removed, failed = 0, []

	for record in records:
		# Jeden Erfolg sofort festschreiben. Ohne das reißt ein einziger
		# Fehlschlag die gesamte bisherige Arbeit mit: Beim Löschen eines
		# verknüpften Datensatzes rollt Frappe die ganze Transaktion zurück,
		# und die zuvor entfernten sind wieder da -- die Funktion meldete dann
		# "38 entfernt", und es standen trotzdem noch 29 da.
		#
		# Ein Savepoint reicht dafür nicht: Das Rollback verwirft ihn gleich
		# mit, und der Versuch, dorthin zurückzukehren, scheitert an einem
		# Savepoint, den es nicht mehr gibt.
		try:
			if frappe.db.exists(record.ref_doctype, record.ref_name):
				doc = frappe.get_doc(record.ref_doctype, record.ref_name)
				if doc.meta.is_submittable and doc.docstatus == 1:
					doc.cancel()
				# Bewusst OHNE force: Die Verweisprüfung muss greifen. Mit
				# force verschwände etwa ein Kunde, auf den eine echte
				# Rechnung zeigt -- die Rechnung bliebe mit einem Verweis ins
				# Leere zurück, und das fällt erst auf, wenn jemand sie
				# öffnet. Lieber stehen lassen und melden.
				frappe.delete_doc(
					record.ref_doctype,
					record.ref_name,
					ignore_permissions=True,
					delete_permanently=True,
				)
			frappe.delete_doc(TRACKER, record.name, force=True, ignore_permissions=True)
			frappe.db.commit()
			removed += 1
		except Exception as e:
			# Weitermachen statt abbrechen: Ein einzelner Datensatz, an dem
			# noch etwas hängt (etwa ein Artikel, auf den eine echte Rechnung
			# verweist), darf nicht dazu führen, dass der Rest stehen bleibt.
			# Der Verweis auf ihn bleibt in der Nachverfolgung, damit ein
			# zweiter Durchlauf es erneut versucht.
			frappe.db.rollback()
			failed.append({"doctype": record.ref_doctype, "name": record.ref_name, "error": str(e)})

	return removed, failed


@frappe.whitelist(allow_guest=True)
def get_demo_status():
	"""Sind Demo-Daten installiert, und welche Anmeldungen gibt es?

	Wird von der Anmeldeseite aufgerufen, also auch von Gästen. Ohne
	installierte Demo-Daten kommt eine leere Liste zurück -- die Schnell-
	Logins entstehen dadurch serverseitig und nicht dadurch, dass die
	Oberfläche etwas verbirgt.
	"""
	if not is_installed():
		return {"installed": False, "complete": False, "users": []}

	demo_users = set(
		frappe.get_all(
			TRACKER, filters={"ref_doctype": "User"}, pluck="ref_name"
		)
	)

	users = []
	for spec in DEMO_USERS:
		if spec["email"] not in demo_users:
			continue
		if not frappe.db.get_value("User", spec["email"], "enabled"):
			continue
		users.append(
			{
				"user": spec["email"],
				"name": f"{spec['first_name']} {spec['last_name']}",
				"role_label": spec["role_label"],
			}
		)

	return {"installed": True, "complete": is_complete(), "users": users}


@frappe.whitelist(allow_guest=True)
def demo_login(user: str):
	"""Ohne Passwort als Demo-Benutzer anmelden.

	Gilt ausschließlich für Benutzer, die die Demo-Installation selbst
	angelegt hat -- nachgewiesen über die Nachverfolgungstabelle. Ein echtes
	Konto lässt sich darüber nicht übernehmen, selbst wenn jemand die Adresse
	errät. Sind keine Demo-Daten installiert, gibt es hier nichts zu holen.
	"""
	if not is_installed():
		frappe.throw(_("No demo data is installed."), frappe.PermissionError)

	known = {spec["email"] for spec in DEMO_USERS}
	tracked = set(
		frappe.get_all(TRACKER, filters={"ref_doctype": "User"}, pluck="ref_name")
	)

	if user not in known or user not in tracked:
		frappe.throw(_("{0} is not a demo user.").format(user), frappe.PermissionError)

	if not frappe.db.get_value("User", user, "enabled"):
		frappe.throw(_("{0} is not a demo user.").format(user), frappe.PermissionError)

	frappe.local.login_manager.login_as(user)

	return {"user": user}
