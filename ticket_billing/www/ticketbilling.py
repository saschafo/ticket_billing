"""Einstiegsseite der Vue-Oberfläche.

Liefert das leere HTML-Gerüst aus und legt die Startwerte in ``window``, damit
die SPA ohne einen ersten API-Aufruf rendern kann.
"""

import json

import frappe

no_cache = 1


def get_context(context):
	user = frappe.session.user

	context.session_user = user
	context.roles_json = json.dumps([] if user == "Guest" else frappe.get_roles(user))

	# Von Frappe aufgelöste Sprache der Sitzung (User-Einstellung, sonst
	# Accept-Language, sonst Systemsprache). Die Vue-Seite übernimmt den Wert
	# als Startsprache -- so stimmen Server- und Oberflächensprache überein.
	context.lang = frappe.local.lang or "de"
	context.csrf_token = frappe.session.csrf_token

	return context
