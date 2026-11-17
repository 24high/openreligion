---
# Datei: data/claims/<tradition-kurz>/<slug>.md – die id MUSS dem Pfad entsprechen
id: claim:<tradition-kurz>/<slug>
type: claim
tradition: tradition:<pfad/der/tradition>
perspective: internal        # internal | external | scholarly
claim_type: normative        # descriptive | normative | metaphysical | empirical | historical
epistemic_basis: [scripture] # scripture | tradition | reason | experience | empirical
statement:
  de: <Ein Satz, ohne "laut X" – die Zuschreibung ergibt sich aus tradition + perspective>
sources:
  - ref: work:<werk>#<locus>
# evidence:                  # Pflicht, wenn epistemic_basis "empirical" enthält
#   level: supported         # established | supported | preliminary | contested | refuted
relations: []
review_status: draft
---
# <Titel>

<Optionale Erläuterung in Markdown.>
