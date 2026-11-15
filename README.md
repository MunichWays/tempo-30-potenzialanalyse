[![Tests](https://github.com/MunichWays/tempo-30-potenzialanalyse/actions/workflows/tests.yml/badge.svg)](https://github.com/MunichWays/tempo-30-potenzialanalyse/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/github/license/MunichWays/tempo-30-potenzialanalyse)](LICENSE)

# Tempo-30-Potenzialanalyse

Automatisierte Suche nach Straßenabschnitten, bei denen eine Reduzierung der Höchstgeschwindigkeit auf Tempo 30 sinnvoll ist und nach novellierter StVO Chancen auf Umsetzung hat.

## Repository-Struktur

- [DataRetrieval](DataRetrieval/): Ruft Straßen, Zebrastreifen und Einrichtungen aus OpenStreetMap über die Overpass API ab und speichert die Antworten lokal zwischen.
- [PotentialCalculation](PotentialCalculation/): Prüft Straßenabschnitte auf Potenzial durch nahegelegene Einrichtungen, Zebrastreifen oder Lücken zwischen Tempo-30-Abschnitten.
- [DataOutput](DataOutput/): Erstellt GeoJSON-Ebenen für die Karte sowie eine Textausgabe und eine grafische Übersicht der Ergebnisse.
- [data](data/): Enthält die Regionenkonfigurationen mit Namen und, soweit vorhanden, Begrenzungsrahmen für die Analyse.
- Tests und Messung der Testabdeckung sind in der [Testdokumentation](tests/README.md) beschrieben.
