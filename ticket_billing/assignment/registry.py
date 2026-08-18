"""Verzeichnis der verfügbaren Zuweisungsregeln.

Regeln tragen sich per Dekorator ein. Der Rest der Anwendung kennt nur den
Schlüssel aus den Einstellungen und fragt hier nach der passenden Klasse --
es gibt also keine Stelle, an der die Regeln aufgezählt werden müssten.
"""

import frappe
from frappe import _

from ticket_billing.assignment.base import AssignmentStrategy

_STRATEGIES: dict[str, type[AssignmentStrategy]] = {}


def register(cls: type[AssignmentStrategy]) -> type[AssignmentStrategy]:
	"""Dekorator: Regel unter ihrem ``key`` verfügbar machen."""
	if not cls.key:
		raise ValueError(f"{cls.__name__} hat keinen 'key' gesetzt")

	_STRATEGIES[cls.key] = cls
	return cls


def _load() -> dict[str, type[AssignmentStrategy]]:
	"""Regelmodule importieren, damit die Dekoratoren gelaufen sind.

	Der Import steht bewusst in der Funktion: Beim Laden von registry.py sind
	die Strategie-Module noch nicht da (sie importieren ja diese Datei).
	"""
	if not _STRATEGIES:
		from ticket_billing.assignment import strategies  # noqa: F401

	return _STRATEGIES


def get_strategy(key: str) -> AssignmentStrategy:
	strategies = _load()
	cls = strategies.get(key)

	if not cls:
		frappe.throw(
			_("Unknown assignment strategy {0}. Available: {1}").format(
				key, ", ".join(sorted(strategies)) or "-"
			)
		)

	return cls()


def list_strategies() -> list[dict]:
	"""Alle registrierten Regeln -- für Einstellungen und Oberfläche."""
	return [{"key": cls.key, "label": cls.label} for cls in _load().values()]


def is_registered(key: str) -> bool:
	return key in _load()
