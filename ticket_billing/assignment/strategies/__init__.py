"""Sammelstelle der Zuweisungsregeln.

Eine neue Regel wird hier importiert -- damit ist sie registriert. Das ist
die einzige Zeile außerhalb der Regel selbst, die dafür nötig ist.
"""

from ticket_billing.assignment.strategies import by_workload  # noqa: F401
