app_name = "ticket_billing"
app_title = "Ticket Billing"
app_publisher = "Sascha Böhm"
app_description = "Ticket- und Abrechnungsverwaltung auf Basis von ERPNext"
app_email = "service@industrie-4-0.org"
app_license = "agpl-3.0"

# Erforderliche Apps. bench prueft das beim Installieren -- ohne ERPNext
# bricht "bench install-app ticket_billing" mit einer klaren Meldung ab,
# statt spaeter an fehlenden Doctypes zu scheitern.
# Schreibweise "<org>/<repo>" wie bei hrms.
required_apps = ["frappe/erpnext"]

# Rollen als Fixture -- reine Stammdaten, gehören ins Repository.
# Custom Fields und DocPerms auf fremden Doctypes stehen bewusst nicht hier,
# sondern in setup.py; siehe die Begründung dort.
fixtures = [
	{
		"dt": "Role",
		"filters": [["name", "in", ["Mitarbeiter", "Abteilungsleiter", "Geschäftsführung"]]],
	},
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/ticket_billing/css/ticket_billing.css"
# app_include_js = "/assets/ticket_billing/js/ticket_billing.js"

# include js, css files in header of web template
# web_include_css = "/assets/ticket_billing/css/ticket_billing.css"
# web_include_js = "/assets/ticket_billing/js/ticket_billing.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "ticket_billing/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "ticket_billing/public/icons.svg"

# Website Routing
# ---------------

# Die Oberflaeche ist eine Vue-SPA im History-Mode mit der Basis
# "/ticketbilling" (siehe frontend/src/router/index.js). Ohne diese Regel
# liefert Frappe nur "/ticketbilling" aus; jeder Reload, jedes Lesezeichen und
# jeder geteilte Link auf eine Unterroute landet im 404. Die Regel leitet
# alles unterhalb von /ticketbilling auf die Seite www/ticketbilling.html,
# das Routing uebernimmt danach der Vue-Router im Browser.
website_route_rules = [
	{"from_route": "/ticketbilling/<path:app_path>", "to_route": "ticketbilling"},
]

# Home Pages
# ----------

# Die SPA ist die Standard-Oberflaeche, nicht das Frappe-Desk. Damit landet
# "/" in der Vue-App. Das Desk bleibt unter /app erreichbar.
home_page = "ticketbilling"

# Kachel im App-Umschalter des Desk. Ohne diesen Eintrag ist die Anwendung
# nur ueber die Adresse erreichbar -- wer aus ERPNext kommt, findet sie
# nicht. Der Weg fuehrt in die Vue-Oberflaeche, nicht ins Desk.
add_to_apps_screen = [
	{
		"name": "ticket_billing",
		"logo": "/assets/ticket_billing/images/ticket-billing-logo.svg",
		"title": "Ticket Billing",
		"route": "/ticketbilling",
		"has_permission": "ticket_billing.check_app_permission",
	}
]

# Rollenabhaengige Startseiten -- sobald es eigene Rollen gibt, hier eintragen:
# role_home_page = {
# 	"Ticket Agent": "ticketbilling/tickets",
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "ticket_billing.utils.jinja_methods",
# 	"filters": "ticket_billing.utils.jinja_filters"
# }

# Installation
# ------------

after_install = "ticket_billing.setup.after_install"

# Nach jeder Migration nachziehen, damit neue Felder und Rechte einer neuen
# App-Version ohne Handgriff auf bestehende Sites kommen.
after_migrate = "ticket_billing.setup.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "ticket_billing.uninstall.before_uninstall"
# after_uninstall = "ticket_billing.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "ticket_billing.utils.before_app_install"
# after_app_install = "ticket_billing.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "ticket_billing.utils.before_app_uninstall"
# after_app_uninstall = "ticket_billing.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "ticket_billing.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "ticket_billing.notifications.get_notification_config"

# Permissions
# -----------
# Zeilenweise Sichtbarkeit. permission_query_conditions hängt an JEDER
# Listenabfrage (Desk, Report, REST, frappe.get_list), has_permission prüft
# den Einzelzugriff. Beide in ticket_billing/permissions.py -- aus derselben
# Quelle, damit Liste und Einzelzugriff nicht auseinanderlaufen.
permission_query_conditions = {
	"Issue": "ticket_billing.permissions.issue_query_conditions",
	"Timesheet": "ticket_billing.permissions.timesheet_query_conditions",
}

has_permission = {
	"Issue": "ticket_billing.permissions.issue_has_permission",
	"Timesheet": "ticket_billing.permissions.timesheet_has_permission",
}

# Document Events
# ---------------
doc_events = {
	"Issue": {
		# before_validate füllt Pflichtfelder (Abteilung, Herkunft), bevor
		# Frappe sie prüft -- sonst scheitert jedes per E-Mail erzeugte
		# Ticket am Pflichtfeld Abteilung.
		"before_validate": "ticket_billing.doc_events.issue.before_validate",
		"validate": "ticket_billing.doc_events.issue.validate",
		# after_insert statt validate: Die Zuweisung braucht den Namen des
		# Dokuments, und sie soll auch für Tickets aus dem Posteingang
		# laufen.
		"after_insert": "ticket_billing.assignment.auto_assign_on_insert",
		# Realtime: meldet Status- und Zuweisungswechsel an alle Betroffenen.
		"on_update": "ticket_billing.realtime.on_issue_update",
	},
	# Rueckläufer vom Mailsystem sollen kein eigenes Ticket bleiben.
	"Communication": {
		"after_insert": [
			# Reihenfolge zaehlt: erst umhaengen, dann melden -- sonst
			# ginge die Meldung an das Ticket, das gleich geloescht wird.
			"ticket_billing.mail_filter.route_system_mail",
			"ticket_billing.realtime.on_inbound_communication",
		],
	},
	"Employee": {
		"after_insert": "ticket_billing.doc_events.employee.sync_department_permission",
		"on_update": "ticket_billing.doc_events.employee.sync_department_permission",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"ticket_billing.tasks.notify_pending_timesheets",
	],
}

# Testing
# -------

# before_tests = "ticket_billing.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "ticket_billing.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "ticket_billing.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["ticket_billing.utils.before_request"]
# after_request = ["ticket_billing.utils.after_request"]

# Job Events
# ----------
# before_job = ["ticket_billing.utils.before_job"]
# after_job = ["ticket_billing.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"ticket_billing.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# Serverseitige Texte werden ausschliesslich ueber frappe._() erzeugt, damit
# "bench get-untranslated" sie einsammeln kann. Die Uebersetzungen liegen in
# ticket_billing/translations/<sprachkuerzel>.csv; zusaetzlich lassen sie sich
# zur Laufzeit ueber den Doctype "Translation" im Desk pflegen.
#
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
