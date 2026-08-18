# Übersetzungen (Backend)

Frappe liest hier `<sprachkürzel>.csv` ein — zwei Spalten, ohne Kopfzeile:

```csv
Quelltext,Übersetzung
```

Quelltext ist die englische Zeichenkette aus dem `_()`-Aufruf im Python-Code.
Enthält ein Feld ein Komma, muss es in Anführungszeichen stehen.

## Ablauf für eine neue Sprache

Es ist keine Code-Änderung nötig — Voraussetzung ist nur, dass jeder
nutzersichtbare Text im Python-Code durch `frappe._()` läuft.

```bash
# 1. Noch nicht übersetzte Zeichenketten der App einsammeln
./ticket.sh bench --site ticketbilling.localhost get-untranslated fr /tmp/fr-todo.csv --app ticket_billing

# 2. Datei übersetzen und zurückspielen
./ticket.sh bench --site ticketbilling.localhost update-translations fr /tmp/fr-fertig.csv --app ticket_billing
```

Alternativ lassen sich einzelne Texte im Desk über den Doctype **Translation**
pflegen (`/app/translation`). Das wirkt sofort und ohne neuen Build — sinnvoll
für Korrekturen im laufenden Betrieb. Was dauerhaft gelten soll, gehört
hierher in die CSV-Datei, damit es im Repository liegt.

Die Sprachen der Oberfläche liegen getrennt davon unter
`ticket_billing/frontend/src/i18n/locales/`.
