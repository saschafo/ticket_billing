"""Zuweisung nach Auslastung -- die Startregel."""

from ticket_billing.assignment.base import AssignmentStrategy, Candidate
from ticket_billing.assignment.registry import register


@register
class LeastOpenTicketsStrategy(AssignmentStrategy):
	"""Wer die wenigsten offenen Tickets hat, bekommt das neue.

	Bei Gleichstand entscheidet der Name. Das ist willkürlich, aber
	vorhersagbar -- und weil der Zähler mit jeder Zuweisung steigt, verteilt
	sich die Last trotzdem: Wer eins bekommt, ist beim nächsten Ticket nicht
	mehr vorn.
	"""

	key = "by_workload"
	label = "Nach Auslastung (wenigste offene Tickets)"

	def select(self, issue, candidates: list[Candidate]) -> str | None:
		if not candidates:
			return None

		best = min(candidates, key=lambda c: (c.open_tickets, c.employee))
		return best.employee
