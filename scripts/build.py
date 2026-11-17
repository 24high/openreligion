#!/usr/bin/env python3
"""OpenReligion – Validierung, Konsensberechnung und KI-Export.

    python scripts/build.py            # prüfen und dist/ erzeugen
    python scripts/build.py --check    # nur prüfen

Prüft jede Datei unter data/ gegen ihr JSON-Schema, leitet IDs aus Dateipfaden ab,
prüft alle Verweise und Stellenangaben, berechnet die Abstimmungsergebnisse und
schreibt dist/index.jsonl (ein Datensatz pro Zeile, für RAG/KI) und dist/tallies.json.
Exit-Code 1 bei Fehlern.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCHEMA_DIR = ROOT / "schema"

# Entitätstyp -> Verzeichnis unter data/. ID "claim:a/b" liegt in data/claims/a/b.md
ENTITY_DIRS = {
    "tradition": "traditions",
    "work": "works",
    "claim": "claims",
    "interpretation": "interpretations",
    "argument": "arguments",
    "consensus": "consensus",
}
SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*"
ENTITY_ID_RE = re.compile(rf"^(?:{'|'.join(ENTITY_DIRS)}):{SLUG}$")
PASSAGE_RE = re.compile(rf"^(work:{SLUG})#(.+)$")
SYMMETRIC = {"parallels", "contradicts", "same-as"}


# --- YAML: nur JSON-kompatible Typen -----------------------------------------
class JsonCompatibleLoader(yaml.SafeLoader):
    """YAML-1.1-Fallen entschärfen: Datumswerte bleiben Strings, nur true/false sind Booleans."""


JsonCompatibleLoader.yaml_implicit_resolvers = {
    first: [(tag, rx) for tag, rx in resolvers
            if tag not in ("tag:yaml.org,2002:timestamp", "tag:yaml.org,2002:bool")]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
JsonCompatibleLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$"), list("tf"))

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---[ \t]*(?:\n(.*))?\Z", re.S)


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")


def load_validators() -> dict[str, Draft202012Validator]:
    registry: Registry = Registry()
    schemas = {}
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        schema.setdefault("$id", path.resolve().as_uri())  # relative $refs lösen gegen die Datei auf
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
        schemas[path.name.removesuffix(".schema.json")] = schema
    return {name: Draft202012Validator(s, registry=registry) for name, s in schemas.items()}


def schema_errors(validator: Draft202012Validator, doc: object, where: str, rep: Report) -> None:
    for e in sorted(validator.iter_errors(doc), key=lambda e: list(map(str, e.absolute_path))):
        loc = "/".join(map(str, e.absolute_path)) or "(Wurzel)"
        rep.error(where, f"{loc}: {e.message}")


def read_markdown(path: Path) -> tuple[object, str]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("Datei beginnt nicht mit YAML-Frontmatter (--- … ---)")
    return yaml.load(m.group(1), Loader=JsonCompatibleLoader), (m.group(2) or "").strip()


def text_of(lt: dict | None, lang: str) -> str | None:
    if not lt:
        return None
    return lt.get(lang) or lt.get("de") or lt.get("en") or next(iter(lt.values()))


# --- Laden ---------------------------------------------------------------------
def load_entities(validators, rep):
    entities: dict[str, dict] = {}
    for etype, dirname in ENTITY_DIRS.items():
        base = DATA / dirname
        for path in sorted(base.rglob("*.md")):
            rel = path.relative_to(ROOT).as_posix()
            try:
                meta, body = read_markdown(path)
            except (ValueError, yaml.YAMLError) as exc:
                rep.error(rel, str(exc))
                continue
            if not isinstance(meta, dict):
                rep.error(rel, "Frontmatter ist kein Objekt")
                continue
            schema_errors(validators[etype], meta, rel, rep)
            expected = f"{etype}:{path.relative_to(base).with_suffix('').as_posix()}"
            if meta.get("id") != expected:
                rep.error(rel, f"id muss '{expected}' lauten (aus dem Dateipfad abgeleitet), ist '{meta.get('id')}'")
            entities[expected] = {"meta": meta, "body": body, "path": rel, "type": etype}
    return entities


def load_texts(validators, entities, rep):
    passages = []
    base = DATA / "texts"
    for path in sorted(base.rglob("*.json")):
        rel = path.relative_to(ROOT).as_posix()
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            rep.error(rel, f"ungültiges JSON: {exc}")
            continue
        schema_errors(validators["text"], doc, rel, rep)
        if not isinstance(doc, dict):
            continue
        work_slug = path.parent.parent.relative_to(base).as_posix()
        exp = {"work": f"work:{work_slug}", "edition": path.parent.name, "division": path.stem}
        for key, val in exp.items():
            if doc.get(key) != val:
                rep.error(rel, f"{key} muss '{val}' lauten (aus dem Dateipfad), ist '{doc.get(key)}'")
        work = entities.get(exp["work"])
        if not work:
            rep.error(rel, f"Werk {exp['work']} existiert nicht")
            continue
        editions = {e["id"]: e for e in work["meta"].get("editions", [])}
        ed = editions.get(exp["edition"])
        if not ed:
            rep.error(rel, f"Ausgabe '{exp['edition']}' ist im Werk nicht deklariert")
            continue
        if ed.get("license") == "reference-only":
            rep.error(rel, "Ausgabe ist 'reference-only' – Volltext darf nicht im Repo liegen")
        if not ed.get("in_corpus"):
            rep.warn(rel, "Ausgabe hat Volltext, aber in_corpus ist nicht true")
        if doc.get("lang") != ed.get("lang"):
            rep.error(rel, f"lang '{doc.get('lang')}' passt nicht zur Ausgabe ('{ed.get('lang')}')")
        for seg in doc.get("segments", []):
            locus = seg.get("locus", "")
            if not locus.startswith(exp["division"] + "."):
                rep.error(rel, f"Locus '{locus}' liegt nicht in Division '{exp['division']}'")
            check_locus(work, locus, rel, rep)
            passages.append({"work": exp["work"], "edition": exp["edition"], "lang": doc.get("lang"),
                             "locus": locus, "text": seg.get("text"), "path": rel,
                             "license": ed.get("license")})
    return passages


def load_participants(validators, rep):
    people = []
    for path in sorted((DATA / "participants").glob("*.json")):
        rel = path.relative_to(ROOT).as_posix()
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            rep.error(rel, f"ungültiges JSON: {exc}")
            continue
        before = len(rep.errors)
        schema_errors(validators["participant"], doc, rel, rep)
        if isinstance(doc, dict) and doc.get("login") != path.stem:
            rep.error(rel, f"login '{doc.get('login')}' muss dem Dateinamen '{path.stem}' entsprechen")
        if len(rep.errors) == before:  # ungültige Dateien zählen nicht mit
            people.append({"doc": doc, "path": rel})
    return people


# --- Verweise ------------------------------------------------------------------
def check_locus(work: dict, locus: str, where: str, rep: Report) -> None:
    pattern = work["meta"].get("citation", {}).get("locus_pattern")
    if not pattern:
        return
    try:
        ok = re.fullmatch(pattern, locus)
    except re.error as exc:
        rep.error(work["path"], f"citation.locus_pattern ist kein gültiger Regex: {exc}")
        return
    if not ok:
        rep.error(where, f"Locus '{locus}' passt nicht zum Zitierschema von {work['meta']['id']} "
                         f"(Beispiel: {work['meta']['citation'].get('example')})")


def iter_strings(obj, keypath=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_strings(v, f"{keypath}/{k}" if keypath else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_strings(v, f"{keypath}/{i}")
    elif isinstance(obj, str):
        yield keypath, obj


def check_references(entities, people, rep):
    """Jeder String, der wie eine ID oder Stellenangabe aussieht, muss auflösbar sein."""
    def resolve(where, keypath, value):
        if keypath == "id":
            return
        m = PASSAGE_RE.match(value)
        if m:
            work = entities.get(m.group(1))
            if not work:
                rep.error(where, f"{keypath}: Werk {m.group(1)} existiert nicht")
            else:
                check_locus(work, m.group(2), where, rep)
        elif ENTITY_ID_RE.match(value) and value not in entities:
            rep.error(where, f"{keypath}: Verweis auf unbekannte ID {value}")

    for ent in entities.values():
        for keypath, value in iter_strings(ent["meta"]):
            resolve(ent["path"], keypath, value)
    for p in people:
        doc = p["doc"]
        for keypath, value in iter_strings(doc.get("affiliation", {}), "affiliation"):
            resolve(p["path"], keypath, value)
        for target in doc.get("votes", {}):
            resolve(p["path"], f"votes/{target}", target)


def tradition_ancestry(entities, rep):
    """tradition-id -> [selbst, parent, …, Wurzel]; meldet Zyklen und falsche Wurzeln."""
    chains = {}
    for tid, ent in entities.items():
        if ent["type"] != "tradition":
            continue
        chain, cur = [], tid
        while cur:
            if cur in chain:
                rep.error(ent["path"], f"Zyklus in parent-Kette: {' -> '.join(chain + [cur])}")
                break
            chain.append(cur)
            parent = entities.get(cur, {}).get("meta", {}).get("parent")
            if parent and entities.get(parent, {}).get("type") != "tradition":
                break  # unbekannter parent wird bereits von check_references gemeldet
            cur = parent
        root = entities.get(chain[-1], {}).get("meta", {})
        if root.get("kind") != "category":
            rep.error(ent["path"], f"Wurzel {chain[-1]} der Kette ist keine Kategorie")
        chains[tid] = chain
    return chains


# --- Konsens -------------------------------------------------------------------
def score(agree: int, disagree: int) -> float:
    """Laplace-geglättete Zustimmung: kleine Gruppen landen nahe 0.5 statt bei 0 oder 1."""
    return (agree + 1) / (agree + disagree + 2)


def classify(groups: dict, cfg: dict) -> tuple[str, float | None]:
    th = cfg["thresholds"]
    counted = {g: v for g, v in groups.items()
               if g in cfg["groups"] and v["agree"] + v["disagree"] >= cfg["min_group_votes"]}
    if len(counted) < cfg["min_counted_groups"]:
        return "insufficient-data", None
    scores = [v["score"] for v in counted.values()]
    bridge = min(scores)
    if max(scores) <= th["rejected"]:
        return "rejected", bridge
    if max(scores) >= th["polarized_high"] and bridge <= th["polarized_low"]:
        return "polarized", bridge
    if bridge >= th["consensus"]:
        return ("consensus" if len(counted) == len(cfg["groups"]) else "provisional-consensus"), bridge
    if bridge >= th["converging"]:
        return "converging", bridge
    return "contested", bridge


def compute_tallies(entities, people, chains, cfg, rep):
    for g in cfg["groups"]:
        if g not in entities:
            rep.error("config/consensus.json", f"Gruppe {g} existiert nicht")

    def group_of(tradition_id):
        for t in chains.get(tradition_id, []):
            if t in cfg["groups"]:
                return t
        return "unaffiliated"

    def blank():
        return {"agree": 0, "disagree": 0, "pass": 0}

    raw = defaultdict(lambda: {"stance": blank(), "groups": defaultdict(blank),
                               "accuracy": {"all": defaultdict(int), "self": defaultdict(int),
                                            "external": defaultdict(int)}})
    for p in people:
        doc = p["doc"]
        voter_trad = doc.get("affiliation", {}).get("tradition")
        group = group_of(voter_trad) if voter_trad else "unaffiliated"
        for target, vote in doc.get("votes", {}).items():
            if target not in entities:
                continue
            t = raw[target]
            if "stance" in vote:
                t["stance"][vote["stance"]] += 1
                t["groups"][group][vote["stance"]] += 1
            if "accuracy" in vote:
                acc = t["accuracy"]
                acc["all"][vote["accuracy"]] += 1
                subject = entities[target]["meta"].get("tradition")
                if subject:
                    inside = voter_trad is not None and subject in chains.get(voter_trad, [])
                    acc["self" if inside else "external"][vote["accuracy"]] += 1

    out = {}
    for target in sorted(raw):
        t = raw[target]
        groups = {}
        for g in [*cfg["groups"], "unaffiliated"]:
            v = dict(t["groups"].get(g, blank()))
            v["score"] = round(score(v["agree"], v["disagree"]), 3)
            v["counted"] = g in cfg["groups"] and v["agree"] + v["disagree"] >= cfg["min_group_votes"]
            groups[g] = v
        s = t["stance"]
        if sum(s.values()) == 0:
            status, bridge = "no-stance-votes", None  # nur Korrektheitsstimmen
        else:
            status, bridge = classify(groups, cfg)
        out[target] = {
            "type": entities[target]["type"],
            "status": status,
            "bridge_score": None if bridge is None else round(bridge, 3),
            "overall": {**s, "score": round(score(s["agree"], s["disagree"]), 3)},
            "missing_groups": [g for g in cfg["groups"] if not groups[g]["counted"]],
            "groups": groups,
            "accuracy": {k: dict(v) for k, v in t["accuracy"].items() if v},
        }
    return out


# --- KI-Export -----------------------------------------------------------------
FRAMES = {
    "de": {"internal": "Laut {t} (Selbstbeschreibung): {s}",
           "external": "Über {t} (Fremdbeschreibung): {s}",
           "scholarly": "Fachwissenschaftlich über {t}: {s}",
           "empirical": "Wissenschaftlicher Befund (Evidenzgrad: {lvl}): {s}",
           "interpretation": "Auslegung von {target} ({who}): {s}",
           "argument": "{stance}-Argument zu {target}: {s}",
           "consensus": "Konsensvorschlag ({ctype}, Status: {status}) zur Frage „{q}“: {s}",
           "tradition": "{s} – Eintrag der Religionsschicht, Bereich: {group}."},
    "en": {"internal": "According to {t} (self-description): {s}",
           "external": "About {t} (external description): {s}",
           "scholarly": "Scholarly description of {t}: {s}",
           "empirical": "Scientific finding (evidence level: {lvl}): {s}",
           "interpretation": "Interpretation of {target} ({who}): {s}",
           "argument": "{stance} argument on {target}: {s}",
           "consensus": "Consensus proposal ({ctype}, status: {status}) on the question \"{q}\": {s}",
           "tradition": "{s} – entry in the religion layer, domain: {group}."},
}


def framed(ent, entities, tallies, chains, cfg):
    """Selbsttragender Satz pro Sprache, der die Zuschreibung immer mitführt.

    Ein RAG-System, das nur diesen Satz abruft, kann eine Glaubensaussage nicht
    versehentlich als Tatsache wiedergeben.
    """
    m, etype = ent["meta"], ent["type"]
    langs = list((m.get("statement") or m.get("proposal") or m.get("name") or {"de": ""}).keys())
    result = {}
    for lang in langs:
        f = FRAMES.get(lang, FRAMES["en"])
        tname = text_of(entities.get(m.get("tradition"), {}).get("meta", {}).get("name"), lang) or "?"
        if etype == "claim":
            key = "empirical" if "empirical" in m.get("epistemic_basis", []) else m["perspective"]
            s = f[key].format(t=tname, s=text_of(m["statement"], lang),
                              lvl=m.get("evidence", {}).get("level", "?"))
        elif etype == "interpretation":
            who = f"{m['perspective']}, {tname}" if m.get("tradition") else m["perspective"]
            s = f["interpretation"].format(target=m["target"], who=who, s=text_of(m["statement"], lang))
        elif etype == "argument":
            s = f["argument"].format(stance=m["stance"].capitalize(), target=m["target"],
                                     s=text_of(m["statement"], lang))
        elif etype == "consensus":
            status = tallies.get(m["id"], {}).get("status", "no-votes")
            s = f["consensus"].format(ctype=m["consensus_type"], status=status,
                                      q=text_of(m["question"], lang), s=text_of(m["proposal"], lang))
        elif etype == "tradition":
            group = next((g for g in chains.get(m["id"], []) if g in cfg["groups"]), "-")
            s = f["tradition"].format(s=text_of(m["name"], lang), group=group)
        else:
            s = text_of(m.get("title"), lang)
        result[lang] = s
    return result


def build_index(entities, passages, tallies, chains, cfg):
    incoming = defaultdict(list)
    for eid, ent in entities.items():
        for rel in ent["meta"].get("relations", []):
            incoming[rel["target"]].append({"type": rel["type"], "source": eid})
    for eid, ent in entities.items():
        m = ent["meta"]
        targets = m.get("members", []) + ([m["target"]] if isinstance(m.get("target"), str) else [])
        for t in targets:
            incoming[t.split("#")[0]].append({"type": "member-of" if m.get("members") else "targeted-by", "source": eid})

    lines = []
    for eid in sorted(entities):
        ent = entities[eid]
        m = ent["meta"]
        rels = list(m.get("relations", []))
        # symmetrische Relationen auch in Gegenrichtung ausweisen
        rels += [{"type": r["type"], "target": r["source"], "inferred": True}
                 for r in incoming.get(eid, []) if r["type"] in SYMMETRIC]
        record = {
            "id": eid,
            "type": ent["type"],
            "path": ent["path"],
            "framed": framed(ent, entities, tallies, chains, cfg),
            "group": next((g for g in chains.get(m.get("tradition") or eid, []) if g in cfg["groups"]), None),
            "meta": m,
            "relations": rels,
            "referenced_by": [r for r in incoming.get(eid, []) if r["type"] not in SYMMETRIC],
            "tally": tallies.get(eid),
            "body": ent["body"] or None,
        }
        lines.append({k: v for k, v in record.items() if v not in (None, [], {})})
    for p in passages:
        lines.append({"id": f"{p['work']}#{p['locus']}@{p['edition']}", "type": "passage",
                      "path": p["path"], "framed": {p["lang"]: f"{p['work']}#{p['locus']} ({p['edition']}): {p['text']}"},
                      "meta": p})
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="nur prüfen, nichts schreiben")
    ap.add_argument("--out", default="dist", help="Ausgabeverzeichnis (Standard: dist)")
    args = ap.parse_args()

    rep = Report()
    cfg = json.loads((ROOT / "config" / "consensus.json").read_text(encoding="utf-8"))
    validators = load_validators()
    entities = load_entities(validators, rep)
    passages = load_texts(validators, entities, rep)
    people = load_participants(validators, rep)
    check_references(entities, people, rep)
    chains = tradition_ancestry(entities, rep)
    tallies = compute_tallies(entities, people, chains, cfg, rep)

    for w in rep.warnings:
        print(f"WARNUNG  {w}")
    for e in rep.errors:
        print(f"FEHLER   {e}")
    counts = defaultdict(int)
    for ent in entities.values():
        counts[ent["type"]] += 1
    print(f"\n{len(entities)} Entitäten ({', '.join(f'{k}: {v}' for k, v in sorted(counts.items()))}), "
          f"{len(passages)} Textsegmente, {len(people)} Teilnehmende")
    print(f"{len(rep.errors)} Fehler, {len(rep.warnings)} Warnungen\n")
    if tallies:
        print(f"{'Status':<24}{'Brücke':>7}  Ziel")
        for tid, t in tallies.items():
            b = "-" if t["bridge_score"] is None else f"{t['bridge_score']:.2f}"
            print(f"{t['status']:<24}{b:>7}  {tid}")

    if rep.errors:
        return 1
    if not args.check:
        out = ROOT / args.out
        out.mkdir(parents=True, exist_ok=True)
        index = build_index(entities, passages, tallies, chains, cfg)
        (out / "index.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in index), encoding="utf-8")
        (out / "tallies.json").write_text(
            json.dumps({"config": cfg, "targets": tallies}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nGeschrieben: {args.out}/index.jsonl ({len(index)} Zeilen), {args.out}/tallies.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
