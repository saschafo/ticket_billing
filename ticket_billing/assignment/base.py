"""Schnittstelle für Zuweisungsregeln.

Eine Regel bekommt ein Ticket und die in Frage kommenden Mitarbeiter und
liefert genau einen davon zurück -- oder None, wenn sie nicht entscheiden
kann oder will. None ist kein Fehler: Es bedeutet "bleibt unzugewiesen, der
Abteilungsleiter entscheidet". Genau darüber lässt sich später eine Regel
"manuelle Bestätigung durch den Leiter" bauen, ohne irgendetwas anderes
anzufassen.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
	"""Ein zuweisbarer Mitarbeiter samt der Zahlen, die Regeln brauchen.

	Die Kennzahlen werden einmal zentral ermittelt und hier hereingereicht,
	damit nicht jede Regel ihre eigenen Datenbankabfragen baut.
	"""

	employee: str
	employee_name: str
	user: str
	department: str
	open_tickets: int


class AssignmentStrategy:
	"""Basisklasse für Zuweisungsregeln.

	Eine neue Regel braucht drei Dinge: von dieser Klasse erben, ``key`` und
	``label`` setzen, ``select`` implementieren. Registriert wird sie mit dem
	Dekorator ``@register`` aus ``ticket_billing.assignment.registry``; damit
	steht sie in den Einstellungen zur Auswahl. Am übrigen Code ändert sich
	dafür nichts.
	"""

	#: Technischer Schlüssel, wird in den Einstellungen gespeichert.
	key: str = ""
	#: Sprechender Name für die Oberfläche.
	label: str = ""

	def select(self, issue, candidates: list[Candidate]) -> str | None:
		"""Einen Mitarbeiter auswählen.

		:param issue: das Ticket (Frappe-Document, noch nicht zugewiesen)
		:param candidates: aktive Mitarbeiter der zuständigen Abteilung,
		    die die Rolle für Ticketbearbeitung haben
		:returns: Employee-ID oder None für "nicht zuweisen"
		"""
		raise NotImplementedError
