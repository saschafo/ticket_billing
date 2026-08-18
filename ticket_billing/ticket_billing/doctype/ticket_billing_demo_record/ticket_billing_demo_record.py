from frappe.model.document import Document


class TicketBillingDemoRecord(Document):
	"""Ein von der Demo-Installation angelegter Datensatz.

	Nur was hier steht, wird beim Entfernen gelöscht. Damit kann echte, später
	eingegebene Arbeit nicht versehentlich mitgehen -- auch dann nicht, wenn
	sie zufällig genauso heißt wie ein Demo-Datensatz.
	"""

	pass
