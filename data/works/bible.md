---
id: work:bible
type: work
title:
  de: Bibel
  en: Bible
summary:
  de: Heilige Schrift des Christentums (Altes und Neues Testament).
traditions:
  - tradition:monotheism/divine/christianity
citation:
  standard: OSIS
  locus_pattern: '^(?:[1-4])?[A-Z][A-Za-z]+\.\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?$'
  example: Matt.7.12
  explanation:
    de: OSIS-Buchkürzel.Kapitel.Vers, Bereiche mit Bindestrich (Matt.7.12-14).
editions:
  - id: kjv
    lang: en
    title: King James Version (1611/1769)
    license: public-domain
    license_note: Außerhalb des Vereinigten Königreichs gemeinfrei (dort Crown Copyright).
    in_corpus: true
  - id: luther1912
    lang: de
    title: Lutherbibel 1912
    license: public-domain
    in_corpus: false
  - id: luther2017
    lang: de
    title: Lutherbibel 2017
    license: reference-only
    license_note: Urheberrechtlich geschützt – nur Stellenangaben, kein Volltext.
    in_corpus: false
review_status: draft
---
# Bibel

Die hebräische Bibel als jüdischer Kanon (Tanach) wird als eigenes Werk geführt,
weil Kanon, Reihenfolge und Zählung abweichen. Gemeinsame Stellen werden über
`relations: same-as` verknüpft.
