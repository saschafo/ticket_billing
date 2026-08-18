"""Feste Werte, die an mehreren Stellen gebraucht werden.

An einem Ort, weil Rollennamen und Statuslisten sonst in Rechteprüfung,
Zuweisung, API und Fixtures auseinanderlaufen.
"""

# Rollen. Die Namen stehen so auch in den Fixtures (fixtures/role.json) --
# wer sie hier ändert, muss sie dort mitziehen.
ROLE_EMPLOYEE = "Mitarbeiter"
ROLE_LEAD = "Abteilungsleiter"
ROLE_MANAGEMENT = "Geschäftsführung"

TICKET_ROLES = (ROLE_EMPLOYEE, ROLE_LEAD, ROLE_MANAGEMENT)

# Rollen, die grundsätzlich alles sehen dürfen -- ohne Einschränkung auf
# Abteilung oder Zuweisung.
UNRESTRICTED_ROLES = ("System Manager", "Administrator", ROLE_MANAGEMENT)

# Als "offen" zählt alles, was nicht abgeschlossen ist. Diese Definition
# steuert sowohl die Auslastungsberechnung der Zuweisung als auch die
# Kennzahlen der Auswertungen -- deshalb genau eine Quelle dafür.
CLOSED_STATUSES = ("Resolved", "Closed")
OPEN_STATUSES = ("Open", "Replied", "On Hold")

# Herkunft eines Tickets. Kanonisch englisch gespeichert, übersetzt wird bei
# der Anzeige (Frappe über translations/, die Oberfläche über vue-i18n).
ORIGIN_INTERNAL = "Internal"
ORIGIN_EXTERNAL = "External"
ORIGINS = (ORIGIN_INTERNAL, ORIGIN_EXTERNAL)

# Custom-Field-Namen auf Fremd-Doctypes. Präfix "tb_", damit sie sich nie mit
# Feldern aus Frappe oder ERPNext beißen.
FIELD_DEPARTMENT = "tb_department"
FIELD_ORIGIN = "tb_origin"
FIELD_ASSIGNEE = "tb_assigned_employee"
FIELD_TIMESHEET_ISSUE = "tb_issue"
FIELD_EMAIL_DEPARTMENT = "tb_department"

# Eigene Zeitstempel für die Kennzahlen. ERPNext führt zwar
# first_responded_on und sla_resolution_date, füllt sie aber nur über die
# SLA-Funktion -- ohne konfiguriertes Service Level Agreement bleiben sie
# leer. Diese beiden hängen an nichts weiter als dem Statuswechsel.
FIELD_FIRST_RESPONSE = "tb_first_response_on"
FIELD_RESOLVED = "tb_resolved_on"

# Leistungsart, die neuen Zeiteinträgen mitgegeben wird. ERPNext verlangt sie
# beim Buchen, und der Stundensatz hängt daran (siehe Activity Type).
DEFAULT_ACTIVITY_TYPE = "Ticket-Support"
