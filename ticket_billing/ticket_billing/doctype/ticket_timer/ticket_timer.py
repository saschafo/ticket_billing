import frappe
from frappe import _
from frappe.model.document import Document


class TicketTimer(Document):
	"""Ein laufender Timer.

	Existiert nur, solange die Zeit läuft: Beim Stoppen entsteht daraus ein
	Zeiteintrag und der Datensatz wird gelöscht. Der Zustand liegt bewusst
	auf dem Server statt im Browser -- sonst wäre eine angefangene Erfassung
	nach einem Neuladen oder auf einem anderen Gerät verloren.
	"""

	def validate(self):
		self.validate_single_running_timer()

	def validate_single_running_timer(self):
		"""Pro Mitarbeiter nur ein Timer gleichzeitig.

		Zwei parallel laufende Timer wären in der erfassten Zeit nicht mehr
		auseinanderzuhalten -- die Summe wäre höher als die tatsächlich
		gearbeitete Zeit.

		Die eigentliche Absicherung ist der eindeutige Index auf ``employee``
		(``unique`` im Doctype). Diese Prüfung liefert nur die verständliche
		Meldung: Zwei fast gleichzeitige Anfragen -- zwei Geräte, ein
		Doppelklick -- könnten beide an dieser Stelle vorbeikommen, bevor eine
		von ihnen schreibt. Am Index kommt die zweite trotzdem nicht vorbei.
		"""
		existing = frappe.db.exists(
			"Ticket Timer",
			{"employee": self.employee, "name": ["!=", self.name or ""]},
		)
		if existing:
			running_issue = frappe.db.get_value("Ticket Timer", existing, "issue")
			frappe.throw(
				_("A timer is already running for ticket {0}. Stop it first.").format(
					running_issue
				),
				title=_("Timer already running"),
			)
