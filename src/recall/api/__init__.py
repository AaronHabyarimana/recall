"""HTTP-Zugriff auf die Lerndatenbank.

Eine dünne Schicht über `recall.review.db`: die Abfragen liegen dort und sind dort
getestet, hier kommt nur die Übersetzung nach HTTP dazu. Die Pipeline (PDF -> Karten
-> Critic) bleibt wie bei der Oberfläche in der CLI, sie läuft Minuten und braucht
einen API-Key.

Hier wird bewusst nichts aus `app` importiert. `recall.cli` laedt dieses Paket beim
Start, und ein Import von FastAPI an dieser Stelle wuerde die komplette CLI
lahmlegen, sobald jemand ohne die Gruppe `api` installiert. Genau dafuer prueft
`cli.run` erst zur Laufzeit, ob uvicorn da ist.
"""
