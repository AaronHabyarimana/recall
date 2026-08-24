#!/usr/bin/env bash
# Probelauf des frisch gebauten Images, bevor es in die Registry darf.
#
# Deckt die drei Wege ab, auf denen jemand das Image benutzt: die CLI, die API und
# die Oberflaeche. Alle drei gegen dieselbe Datenbank auf einem Volume, denn genau
# dort faellt auf, wenn Rechte oder Pfade im Container nicht stimmen.
# Lokal unter Git Bash: MSYS_NO_PATHCONV=1 setzen, sonst macht MSYS aus /data/t.db
# einen Windows-Pfad. Und `docker compose down` vorher, die Ports 8000 und 8501
# muessen frei sein.
set -euo pipefail

IMAGE="${1:-recall:ci}"
VOLUME=recall-smoke
DB=/data/t.db
# Zwischendateien in ein Temp-Verzeichnis, damit der Lauf das Repo nicht vollmuellt.
ARBEIT="$(mktemp -d)"

aufraeumen() {
  docker rm -f recall-api recall-ui > /dev/null 2>&1 || true
  docker volume rm "$VOLUME" > /dev/null 2>&1 || true
  rm -rf "$ARBEIT"
}
trap aufraeumen EXIT

warte_auf() {
  local url=$1 versuche=$2
  for _ in $(seq 1 "$versuche"); do
    if curl -fsS "$url" > "$ARBEIT/antwort.txt" 2> /dev/null; then
      cat "$ARBEIT/antwort.txt"
      return 0
    fi
    sleep 1
  done
  echo "Zeitüberschreitung bei $url" >&2
  return 1
}

echo "== CLI: Demokarten importieren =="
# Die 17 Demokarten liegen im Image, es braucht keinen API-Key.
docker run --rm -v "$VOLUME":/data "$IMAGE" review import samples/demo_cards.json --db "$DB"
docker run --rm -v "$VOLUME":/data "$IMAGE" review stats --db "$DB" | tee "$ARBEIT/stats.txt"
grep -q "17 gesamt, 14 lernbar" "$ARBEIT/stats.txt"

echo "== API =="
docker run -d --name recall-api -v "$VOLUME":/data -p 8000:8000 "$IMAGE" \
  api --host 0.0.0.0 --port 8000 --db "$DB"
warte_auf http://localhost:8000/health 30
grep -qE '"cards": ?17' "$ARBEIT/antwort.txt"
curl -fsS "http://localhost:8000/due?limit=1" | grep -q card_id
# Eine unbekannte Karte muss 404 geben und nicht 500.
test "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/cards/gibtsnicht)" = 404
docker rm -f recall-api

echo "== Oberflaeche =="
# Wenn dieser Endpunkt nicht antwortet, schlaegt spaeter der HEALTHCHECK im Betrieb fehl.
docker run -d --name recall-ui -v "$VOLUME":/data -p 8501:8501 "$IMAGE" \
  ui --kein-browser --host 0.0.0.0 --port 8501 --db "$DB"
warte_auf http://localhost:8501/_stcore/health 60

echo "== alles durch =="
