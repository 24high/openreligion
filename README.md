# OpenReligion

Offene Datenbasis für öffentlichen religiösen Diskurs: Aussagen aus Religionen und
Wissenschaft, mit Quellen belegt, einander gegenübergestellt und gemeinsam bewertet –
mit dem Ziel eines übergreifend akzeptierten Konsenses oder eines fair beschriebenen Dissenses.

| Schicht | Inhalt |
|---|---|
| **Daten** | Markdown + JSON in diesem Repository, geprüft durch JSON-Schemas |
| **Religion** | Monotheismus (göttliche Instanz / Widersacher), Polytheismus, Sonstiges, Belegte Fakten (Wissenschaft) |
| **Konsens** | Vorschläge, Argumente und Stimmen; Konsens nur, wenn jede Gruppe zustimmt |

## Dokumentation

- [Konzept und Evaluation](docs/konzept.md) – Optionen, Bewertung, Empfehlungen, Fahrplan
- [Datenmodell](docs/datenmodell.md) – IDs, Felder, Beispiele, generierte Daten
- [Mitmachen](docs/beitragen.md) – Einträge anlegen und abstimmen
- [`llms.txt`](llms.txt) – Einstieg für KI-Systeme

## Struktur

```
config/consensus.json      Gruppen und Schwellen der Konsensberechnung
schema/*.schema.json       verbindliche Datenstruktur
data/traditions/           Religionsschicht (Baum)
data/works/, data/texts/   Werke und Volltexte
data/claims/               Aussagen
data/interpretations/      Auslegungen
data/arguments/            Pro/Contra
data/consensus/            Konsensvorschläge
data/participants/         eine Datei pro Person mit ihren Stimmen
templates/                 Vorlagen für neue Einträge
scripts/build.py           Validierung, Auszählung, Export nach dist/
```

## Prüfen und bauen

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python scripts/build.py
```

Ergebnis: Fehlerliste, Statustabelle aller Abstimmungen, `dist/index.jsonl` und `dist/tallies.json`.

Die Beispieldaten (`demo-*`) sind erfunden und dienen nur der Demonstration.
