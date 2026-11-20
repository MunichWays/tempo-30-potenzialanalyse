# uMap Integration

Die berechneten Potenziale werden per [uMap](https://umap.openstreetmap.de/) dargestellt.

Die Vorteile sind
- Vielfältige Interaktionsoptionen für Benutzer:innen
    - Ein- und ausblenden von Ebenen
    - Daten filtern
    - Dateninspektion
- Kollaborationsmöglichkeiten für Benutzer:innen
    - Potenziale positiv/negativ kommentieren
    - Potenziale nachtragen
    - gestellte Anträge dokumentieren
- Hosting und Datenschutz: Kein Stress mit DSGVO, Logins, Cookies, Speicherung von Kommentaren

## Tooling

Technisch gesehen werden die berechneten Potenziale als remote layers ("Ausgelagerte Daten") implementiert.
Das template kann für neue Regionen verwendet werden.

- `template.umap`: Ein Basiskarte mit Ebenenbeschreibungen, Ebenenberechtigungen, Darstellungsoptionen, etc.
- `build_umap_configuration.py`: Ein Skript, dass aus dem template eine Tempo 30 Potenzialkarte für eine bestimmte Region macht.

## Template-Übersicht

Die Kartenvorlage gruppiert die Daten wie folgt

- **Kontextdaten:** Aktuelle Geschwindigkeitsbegrenzungen als Kontext für die Potenzialanalyse.
- **Tempo 30 Indikatoren:** Lokale Gegebenheiten wie Schulen, Kitas und Zebrastreifen, die ein Tempolimit nahelegen. Die berechneten Potenziale sind Prüfhinweise, keine bestätigten Anordnungen.
- **Tempo 30 Potenziale:** Straßenabschnitte mit Potenzial für eine Geschwindigkeitsbegrenzung.
- **Deine Ergänzungen:** Trage Hinweise und Ergänzungen zu den Potenzialen hier ein.

Berechtigungen: **Deine Ergänzungen** ist standardmäßig editierbar (`permissions.edit_status=1`).
Einstellungen und ausgelagerte Daten sind nur standardmäßig owner-only (`edit_status=3`) editierbar.
