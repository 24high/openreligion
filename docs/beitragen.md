# Mitmachen

## Einen Eintrag anlegen

1. Passende Vorlage aus [`templates/`](../templates) kopieren.
2. Unter `data/<typ>/…` speichern – **die `id` muss dem Dateipfad entsprechen**
   (`claim:islam/tawhid` → `data/claims/islam/tawhid.md`).
3. Prüfen:
   ```bash
   .venv/bin/python scripts/build.py --check
   ```
4. Pull Request stellen. Kurator:innen der betroffenen Tradition prüfen die Darstellung.

Ohne Git: Auf GitHub im passenden Ordner „Add file → Create new file“ wählen,
Vorlage einfügen, „Propose changes“.

### Regeln für Aussagen

- **Ein Gedanke pro Aussage.** Lieber zwei Aussagen mit Relation als eine zusammengesetzte.
- **`statement` ohne „laut X“** – die Zuschreibung ergibt sich aus `tradition` und `perspective`.
- **Fremdbeschreibung kennzeichnen:** Wer nicht zur Tradition gehört, schreibt `perspective: external`.
- **Belegen:** Stellenangabe (`ref`) oder Literatur (`citation`). Empirische Aussagen brauchen beides: Quelle und `evidence.level`.
- **Keine geschützten Übersetzungen** als Volltext; bei Zitaten nur kurze Auszüge.

## Abstimmen

1. [`templates/participant.json`](../templates/participant.json) nach
   `data/participants/<dein-github-login>.json` kopieren.
2. Einwilligung setzen. **Hinweis:** Datei und Historie sind öffentlich; Zugehörigkeit und
   Stimmen können Rückschlüsse auf religiöse Überzeugungen zulassen. Pseudonyme Konten sind erlaubt.
3. Zugehörigkeit (freiwillig) und Stimmen eintragen:
   - `stance`: `agree` · `disagree` · `pass` – Stimme ich zu?
   - `accuracy`: `accurate` · `inaccurate` · `unsure` – Ist das korrekt dargestellt, auch wenn ich es nicht teile?
4. Pull Request stellen. CI akzeptiert nur Änderungen an deiner eigenen Datei.

## Diskutieren

Freie Diskussion in GitHub Discussions. Wenn daraus ein tragfähiges Argument entsteht,
wird es als `argument` mit `discussion_url` ins Repo übernommen.
