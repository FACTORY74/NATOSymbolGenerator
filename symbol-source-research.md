# Open-source symbol asset research

Research performed 21 November 2026. Counts are repository-tree observations rather
than claims of APP-06 conformance. Every imported asset must retain the upstream
licence and attribution and must be tested against the selected edition of APP-06.

## Recommended starting point

### Python-Military-Symbols

- Repository: <https://github.com/nwroyer/Python-Military-Symbols>
- Licence: MIT
- Status at review: active; 34 stars; last push 24 August 2026
- Claimed support: APP-06(E), 20-digit SIDCs, names such as `friendly infantry
  platoon`, frames, modifiers, mobility, echelon, and SVG output
- Asset form: drawing primitives and SVG path `d` values embedded in JSON schemas,
  split by symbol set; not thousands of individual `.svg` files
- Limitation: control-measure graphics are explicitly not implemented

This is the closest match to this project's proposed product and data model. Its JSON
contains both canonical/synonym names and fragment geometry. It should be evaluated as
an upstream dependency or a source of properly attributed data before independently
recreating the same engine. Importing code or data requires carrying its MIT copyright
notice.

## Best collection of discrete SVG fragments

### Esri Joint Military Symbology XML (JMSML)

- Repository: <https://github.com/Esri/joint-military-symbology-xml>
- Most relevant asset branch: <https://github.com/Esri/joint-military-symbology-xml/tree/2525d1-svgs/svg>
- Machine-readable mappings: <https://github.com/Esri/joint-military-symbology-xml/tree/2525d1-svgs/instance>
- Licence: Apache-2.0, including `svg/license.txt`
- Status at review: archived since 2024; 191 stars
- Stated standard coverage: MIL-STD-2525D and NATO APP-06(C), with legacy APP-06(B)
  mappings
- Asset form: discrete SVGs plus machine-readable XML schema and instances
- The `2525d1-svgs` branch contains 4,781 SVGs: 52 amplifier, 537 frame, 196
  HQ/task-force/feint-dummy, 56 echelon, 150 operational-condition/amplifier, 757
  legacy, and 3,028 appendix assets, plus bounding-octagon templates
- Appendix assets on that branch include 1,069 Land, 619 Control Measures, 359
  METOC, 242 Signals Intelligence, 185 Sea Subsurface, 180 Activities, 134 Sea
  Surface, 129 Air, 65 Space, and 45 Cyberspace SVGs
- The companion `instance/*.xml` files divide the catalogue into Air, Land Unit,
  Land Equipment, Land Installation, Sea Surface, Sea Subsurface, Space, Cyberspace,
  SIGINT, Control Measure, and other symbol sets and reference the required SVG pieces

This is the most useful source for the desired physical fragment-library layout and
for SIDC lookup data. Its geometry cannot be assumed to conform to APP-06(E), so use it
as a migration seed and comparison corpus. The SVGs are described by the project as
DISA-provided MIL-STD-2525 graphics; JMSML models MIL-STD-2525D and APP-06, but this
branch name specifically denotes 2525D Change 1. NATO-specific differences must be
checked against the pinned APP-06 edition. Apache-2.0 redistribution requirements,
including notices for modified files, apply.

### Esri military-features-data

- Repository: <https://github.com/Esri/military-features-data>
- Licence: Apache-2.0, with a separate SVG copy of the licence
- Status at review: archived since August 2024
- Stated standard coverage includes APP-06(D) study-draft data and derived SVG files
- Asset form: ArcGIS-oriented schemas, metadata, style sources, and SVG-derived data

This is newer than JMSML's advertised APP-06(C) coverage but is geared toward building
ArcGIS products. It is useful for cross-checking APP-06(D) code tables and graphics,
not as a drop-in Python renderer.

## Useful implementation references

### milsymbol

- Repository: <https://github.com/spatialillusions/milsymbol>
- Licence: MIT
- Status at review: active; 825 stars; last push 18 November 2026
- Claimed support: APP-06 B/D/E, MIL-STD-2525 variants, SVG and Canvas output
- Asset form: JavaScript drawing instructions and code rather than a clean directory of
  independent SVG fragments

This is the mature reference implementation and a good source for behavioural and
visual differential tests. Since version 3 it deliberately normalizes rendering toward
the newest standards, so it is not an exact historical-edition oracle.

### missioncommand/mil-sym-java

- Repository: <https://github.com/missioncommand/mil-sym-java>
- Licence: Apache-2.0
- Claimed support: APP-06(D) and partial APP-06(E) Version 2 icons, plus SVG rendering
- Asset form: Java renderer resources; only a handful of standalone pattern-fill SVGs

This is valuable for code-table and output comparison, especially the recent partial
E2 work. It is not a convenient source of standalone icon SVG fragments.

## Lower-priority findings

- [Military Symbology Guide](https://commons.wikimedia.org/wiki/File:Military_Symbology_Guide.svg)
  is a useful multilingual Canadian/NATO quick-reference chart. The single 321 KB SVG
  contains 681 paths and 225 language-switch groups but no element IDs, so individual
  symbols are not directly addressable fragments. It is the author's own work under CC
  BY-SA 4.0 rather than an official specification; use it for visual comparison unless
  share-alike licensing is acceptable for derived assets.
- [QGISFMV](https://github.com/All4Gis/QGISFMV) contains a small set of “APP-06D
  inspired” military SVGs. It is GPL-3.0 and does not claim strict conformance, making
  it a poor asset source for this library.
- [NATO-Joint-Military-Symbology](https://github.com/pdebie/NATO-Joint-Military-Symbology)
  is a four-commit HTML experiment with no substantial catalogue.
- [MilSymb](https://github.com/ralphieraccoon/MilSymb) implements APP-06(C) using
  LaTeX/TikZ under CC BY-SA 4.0. It is useful as a visual comparison, but its format,
  older edition, and share-alike licence make reuse less attractive.

## Recommended evaluation spike

1. Use `Python-Military-Symbols` to render a representative matrix of E1 20-digit
   SIDCs and inspect how much of the desired resolver and renderer already exists.
2. Compare those outputs with `milsymbol` and the corresponding APP-06(E)(1) figures.
3. Import a small, clearly attributed subset of Esri JMSML fragments into the proposed
   common coordinate system and measure the conversion work required.
4. Record divergences by SIDC and APP-06 table/figure; do not combine libraries by
   silently choosing whichever output looks best.
5. Decide whether this project should wrap/fork the MIT Python implementation or build
   a fresh engine using the open datasets only after that evidence is available.

