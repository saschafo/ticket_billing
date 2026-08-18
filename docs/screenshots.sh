#!/usr/bin/env bash
#
# Erzeugt die Bildschirmfotos unter docs/screenshots/ neu.
#
# Aufgenommen wird mit dem headless Chromium, das im Frappe-Abbild ohnehin
# steckt -- es braucht also keinen Browser auf dem Rechner und keine
# Handarbeit. Damit veralten die Bilder nicht still: Nach einer Aenderung an
# der Oberflaeche laesst sich alles in einem Zug neu aufnehmen.
#
# Voraussetzungen:
#   - laufender Stack mit installierten Demo-Daten
#   - die Aufnahmen entstehen mit den Demo-Benutzern, nie mit echten Daten
#
# Aufruf aus dem Verzeichnis des Docker-Setups:
#   SITE=meine.site PORT=8080 apps-local/ticket_billing/docs/screenshots.sh

set -euo pipefail

SITE="${SITE:-ticketbilling.localhost}"
PORT="${PORT:-8080}"
ZIEL="${ZIEL:-apps-local/ticket_billing/docs/screenshots}"
BREITE="${BREITE:-1440}"
HOEHE="${HOEHE:-900}"

mkdir -p "$ZIEL"

anmelden() {
  curl -s -i -H 'Content-Type: application/json' -H "Host: ${SITE}" \
    -d "{\"user\":\"$1\"}" "http://localhost:${PORT}/api/method/ticket_billing.demo.demo_login" \
    | grep -i '^set-cookie: sid=' | sed 's/.*sid=\([^;]*\).*/\1/'
}

aufnehmen() { # name pfad sid wartezeit-ms
  # virtual-time-budget statt fester Wartezeit: Chromium laesst die Uhr
  # vorlaufen und nimmt erst auf, wenn nichts mehr nachlaedt. Diagramme
  # brauchen laenger als Tabellen, deshalb je Seite ein eigener Wert.
  docker compose exec -T backend sh -c \
    "chromium-headless-shell --headless --disable-gpu --no-sandbox --hide-scrollbars \
     --window-size=${BREITE},${HOEHE} --virtual-time-budget=$4 \
     --screenshot=/tmp/$1.png 'http://frontend:8080$2?sid=$3' >/dev/null 2>&1"
  docker compose cp "backend:/tmp/$1.png" "${ZIEL}/$1.png" >/dev/null
  printf "   %-28s %s\n" "$1.png" "$(du -h "${ZIEL}/$1.png" | cut -f1)"
}

LEA=$(anmelden lea@demo.local)
GABI=$(anmelden gabi@demo.local)
[[ -z "$LEA" || -z "$GABI" ]] && { echo "FEHLER: Anmeldung fehlgeschlagen. Sind Demo-Daten installiert?" >&2; exit 1; }

echo "Nehme auf ..."
aufnehmen 01-meine-tickets         /ticketbilling/tickets                "$LEA"   8000
aufnehmen 02-meine-zeiten          /ticketbilling/zeiten                 "$LEA"   8000
aufnehmen 03-abteilung             /ticketbilling/abteilung              "$LEA"   9000
aufnehmen 04-abteilung-kennzahlen  /ticketbilling/abteilung/kennzahlen   "$LEA"  12000
aufnehmen 05-zeiten-buchen         /ticketbilling/zeiten-buchen          "$LEA"   8000
aufnehmen 06-auswertung            /ticketbilling/auswertung             "$GABI" 14000
aufnehmen 07-anmeldung             /ticketbilling/anmelden               ""       6000

echo "Fertig: ${ZIEL}"
