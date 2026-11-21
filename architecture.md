# NATO Symbol Generator architecture

## 1. Purpose and scope

NATOSymbolGenerator is a Python 3.15 service and library that builds NATO military
symbols as SVG. A caller may provide either a complete Symbol Identification Code
(SIDC), or a set of names such as `friendly`, `air`, and `drone`. The system resolves
those names to the corresponding SIDC fields, validates the combination, composes the
required SVG fragments, and returns a self-contained SVG document.

The same domain and rendering code will be usable directly from Python and through a
REST API. The first release should concentrate on point symbols. Tactical graphics,
which can require control points and geometry rather than a single icon, should be a
separate later feature sharing the catalogue and validation infrastructure.

## 2. Governing specification

The implementation must be tied to a named edition of APP-06, NATO Joint Military
Symbology, promulgated under STANAG 2019. It must never mean “whatever the latest
version is”: code tables and drawings can change between editions.

At project inception, the accessible primary reference is [APP-06 Edition E Version
1 (October 2023), hosted by NATO][app06-e1]. A newer Edition E Version 2 is listed by
standards catalogues, but is controlled/restricted. We should obtain the edition that
the project is legally entitled to use from the NATO Standardization Office, record
its provenance, and review its reproduction and distribution terms before deriving or
shipping artwork.

Reference documents should be handled as follows:

1. Store licensed source documents locally under `references/`, which is git-ignored
   unless their licence expressly permits redistribution.
2. Record the publication name, edition, version, publication date, source URL, date
   obtained, and SHA-256 digest in `references/manifest.toml`.
3. Put the selected edition in the generated catalogue metadata and expose it through
   the API.
4. Treat an edition upgrade as a versioned data migration with visual regression
   review, not as a document replacement.

The specification is authoritative. MIL-STD-2525 and existing open-source renderers
are useful comparison material but must not silently fill gaps where they differ from
the selected APP-06 edition.

[app06-e1]: https://coi.nato.int/EWCOI/EW%20COI%20Shared%20Documents/WGs/NEWWG/EW%20Info%20Exchange%20Requirements%20Panel%20%28IERP%29/01_Governing%20Documents/Publications/APP-06%20NATO%20Symbology/APP-06%20EDE%20V1%20E.pdf

## 3. Identifier model

Although an SIDC contains digits, it is an encoded, fixed-width identifier rather
than a number on which arithmetic is performed. The public API and Python types must
therefore represent it as a validated string. This preserves leading zeroes and makes
field boundaries explicit.

For the 20-digit coding scheme used by recent APP-06 editions, the conceptual fields
are:

| Positions | Meaning |
| --- | --- |
| 1–2 | coding scheme/version |
| 3 | context |
| 4 | standard identity/affiliation |
| 5–6 | symbol set |
| 7 | status |
| 8 | headquarters/task force/dummy indicator |
| 9–10 | amplifier, such as echelon or mobility |
| 11–16 | entity/type/subtype |
| 17–18 | modifier 1 |
| 19–20 | modifier 2 |

These positions are descriptive, not hard-coded policy: the catalogue for the pinned
APP-06 edition defines field widths, allowed codes, defaults, and compatibility rules.
An immutable `Sidc` value object owns parsing, formatting, and validation. It may
provide named accessors, but `str(sidc)` is the canonical wire and cache form.

Name-based construction uses a typed `SymbolQuery`, for example:

```json
{
  "identity": "friendly",
  "symbol_set": "air",
  "entity": "unmanned-aerial-vehicle"
}
```

Names are stable, lowercase slugs in our own namespace. Display labels and synonyms
are separate catalogue data. Resolution must reject ambiguous terms and invalid
combinations; it must not guess. Defaults such as present status are documented and
returned in the resolution result so a caller can see the complete SIDC that was
chosen.

## 4. High-level design

```text
HTTP client
    |
    v
REST adapter ──> request models / content negotiation
    |
    v
Symbol service ──> SIDC resolver ──> versioned catalogue
    |                    |
    |                    `── validation rules
    v
render cache ──miss──> composition plan ──> SVG renderer ──> SVG validator
    |                                             |
    `──────────────── SVG bytes <─────────────────'
```

Dependencies point inward: transport and storage depend on the application/domain
layers, while the domain has no dependency on the web framework. This keeps symbol
generation easy to test and usable without running a server.

### Domain layer

- `Sidc` — fixed-width identifier value object.
- `SymbolQuery` — named constituent fields supplied by a caller.
- `SymbolDefinition` — resolved catalogue entry and permitted modifiers.
- `RenderOptions` — size-independent styling choices such as colour mode and frame
  fill. Pixel dimensions belong at embedding time because SVG is scalable.
- Domain exceptions — malformed SIDC, unknown name, ambiguous name, unsupported
  combination, and unsupported standard edition.

### Catalogue layer

Human-reviewed source data should live in declarative YAML or TOML split by symbol
set. A build step validates it and compiles it into deterministic JSON or SQLite for
fast runtime lookup. The source data contains:

- SIDC field codes and canonical names;
- aliases and human-readable descriptions;
- valid parent/child and modifier relationships;
- references to the relevant specification table or figure;
- references to SVG fragment IDs;
- standard edition and local data-schema version.

Never encode the whole taxonomy in Python conditionals. Catalogue compilation should
fail on duplicate codes, duplicate canonical names, dangling fragment references,
invalid field widths, ambiguous aliases, or impossible combinations. Generated files
are reproducible and include a digest of all inputs.

### SVG fragment library

Fragments are small, reviewed SVG assets grouped by their role:

- frames and identity-dependent geometry;
- main entity icons;
- modifiers and amplifiers;
- status, echelon, headquarters, task-force, and mobility indicators;
- optional text/amplifier placement definitions.

All fragments use a common, documented coordinate system and anchor names rather than
pixel offsets scattered through code. Each fragment carries metadata including its
role, bounding box, anchors, compatible symbol sets, source citation, and revision.
Files must contain geometry only: no scripts, event handlers, external URLs, foreign
objects, or unreviewed CSS.

Composition is driven by a `CompositionPlan`. It chooses a frame, layers fragments in
a defined z-order, applies transforms at named anchors, computes the final view box,
and emits stable element IDs. Identity colours and line/fill rules are style tokens,
not duplicated artwork. Where APP-06 defines alternative unframed, monochrome, or
operational-condition displays, those are explicit render profiles.

The result is a standalone SVG with a `viewBox`, accessible `title` and `desc`, and
metadata containing the canonical SIDC, specification edition, catalogue revision,
and renderer version. Output must be deterministic: identical normalized inputs and
versions produce byte-identical SVG.

### Application service

`SymbolService` coordinates resolution, validation, cache lookup, composition, and
rendering. Suggested public Python methods are:

```python
resolve(query: SymbolQuery) -> Sidc
describe(sidc: Sidc) -> SymbolDefinition
render(sidc: Sidc, options: RenderOptions = RenderOptions()) -> RenderedSymbol
render_query(query: SymbolQuery, options: RenderOptions = RenderOptions()) -> RenderedSymbol
```

`RenderedSymbol` contains SVG bytes plus SIDC, media type, ETag, standard edition,
and catalogue/renderer revisions. The service should be free of global mutable state;
dependencies are provided at application startup.

## 5. REST API

Version the HTTP contract independently from the APP-06 edition. A small first API is:

- `GET /v1/symbols/{sidc}` — validate and return `image/svg+xml`.
- `POST /v1/symbols/resolve` — accept constituent names and return the canonical SIDC,
  normalized fields, defaults applied, description, and a render URL.
- `POST /v1/symbols/render` — accept constituent names plus render options and return
  SVG; useful when constructing a URL is inconvenient.
- `GET /v1/symbols/{sidc}/metadata` — return decoded fields and catalogue metadata.
- `GET /v1/catalogue` — discover valid canonical terms, filterable by field or symbol
  set, with pagination.
- `GET /health/live` and `GET /health/ready` — process and catalogue readiness.

Successful SVG responses include `Content-Type: image/svg+xml; charset=utf-8`, a
strong `ETag`, and an immutable or revalidation-oriented `Cache-Control` policy. Honour
`If-None-Match` with `304 Not Modified`. JSON errors use RFC 9457 Problem Details and
identify the invalid field without leaking internals. Malformed input is `400`, unknown
catalogue entries are `404`, invalid field combinations are `422`, and unsupported
media or editions are explicit errors.

Request size, catalogue page size, and query complexity are bounded. The server never
accepts arbitrary SVG, XML, CSS, file paths, or fragment markup from an API caller.
Framework choice belongs in implementation planning; the domain design does not rely
on FastAPI, Litestar, or another particular adapter. Dependency support for Python
3.15 must be verified before selection.

## 6. Caching and concurrency

Use an in-process, size-bounded least-recently-used render cache for the initial
deployment. A cache key is a canonical tuple of:

```text
(sidc, normalized_render_options, app06_edition,
 catalogue_digest, fragment_digest, renderer_version)
```

This prevents stale artwork after a catalogue, fragment, renderer, or standard
upgrade. The value is the final immutable SVG bytes and response metadata. Bound the
cache by total bytes as well as entry count because SVG sizes vary. Cache statistics
(hit, miss, eviction, render duration, and current bytes) are observable but SIDCs
should not be high-cardinality metric labels.

Concurrent misses for the same key are coalesced so only one render occurs. Rendering
is CPU-local and should not perform filesystem access after startup: catalogue and
fragment assets are loaded and validated once during readiness. Negative caching may
be used briefly for syntactically valid but unknown SIDCs, but malformed requests are
not cached.

The process-local cache is intentionally disposable. HTTP caching handles clients and
proxies. If measurements later show repeated work across multiple service instances,
a shared cache can be added behind a `RenderCache` protocol; it is not needed for the
first release.

## 7. Proposed repository layout

```text
NATOSymbolGenerator/
├── pyproject.toml
├── architecture.md
├── references/
│   ├── README.md
│   └── manifest.toml
├── catalogue/
│   ├── schema/
│   └── app06-e1/
├── fragments/
│   └── app06-e1/
├── src/nato_symbol_generator/
│   ├── domain/
│   ├── catalogue/
│   ├── rendering/
│   ├── application/
│   └── api/
├── scripts/
│   ├── compile_catalogue.py
│   └── validate_assets.py
└── tests/
    ├── unit/
    ├── contract/
    ├── conformance/
    └── golden/
```

The distribution package should include only the compiled catalogue and fragments
whose distribution is permitted. Reference PDFs are inputs for maintainers, not
runtime dependencies.

## 8. Validation and testing

Correctness is more important than rendering speed. Testing has several layers:

- unit tests for every SIDC field, round-trip encoding, defaults, aliases, validation
  rules, anchor transforms, and deterministic serialization;
- catalogue tests that exhaustively construct every declared symbol and modifier
  combination that the data marks valid;
- XML/SVG checks for well-formed output, safe elements/attributes, internal-only
  references, finite geometry, and a valid view box;
- golden SVG tests for stable structure, plus rasterized visual snapshots at multiple
  scales to catch layout changes;
- conformance fixtures traced to specific APP-06 tables/figures and reviewed by a
  subject-matter expert;
- REST contract tests for status codes, media types, caching headers, error documents,
  and conditional requests;
- property tests for arbitrary digit strings and name combinations, ensuring bad input
  fails predictably rather than producing partial symbols;
- load tests for cache behaviour, same-key request coalescing, and memory bounds.

Golden-image changes require an explicit review. A visually plausible symbol is not
necessarily a conforming symbol, so comparison with the pinned standard and traceable
catalogue citations is part of acceptance.

## 9. Security and operational concerns

SVG is active content in browsers. Output is assembled exclusively from trusted,
validated project assets. At build and startup, reject scripts, external resources,
entity declarations, event attributes, `foreignObject`, and unsafe URL-bearing
attributes. Escape all metadata and text. Serve a restrictive Content Security Policy
where the deployment permits it, and add `X-Content-Type-Options: nosniff`.

Log a request ID, normalized SIDC, outcome, timing, and cache result. Do not log entire
request bodies. Publish the selected standard edition, catalogue digest, fragment
digest, and application version through structured startup logs and a version endpoint
or response headers so any rendered symbol can be reproduced.

## 10. Delivery sequence

1. Acquire and pin the permitted APP-06 edition; create its provenance manifest and
   clarify derived-artwork licensing.
2. Implement `Sidc`, field tables, catalogue schema/compiler, and validation before
   drawing assets.
3. Prove the coordinate, anchor, style-token, and composition model with a narrow
   vertical slice such as friendly/hostile air UAV symbols.
4. Add deterministic SVG serialization, safety validation, and conformance/golden
   tests for that slice.
5. Add `SymbolService`, the bounded cache, and the REST adapter with conditional HTTP
   caching.
6. Expand one symbol set at a time, requiring catalogue validation, source citations,
   and visual review for each increment.
7. Measure before adding a shared cache or pre-rendered symbol store.

## 11. Decisions still requiring confirmation

- Which APP-06 edition the project is authorized and required to implement.
- Whether “numeric ID” specifically means the recent 20-digit SIDC or compatibility
  with older 15-character schemes is also required.
- Which symbol sets and render profiles define the first releasable subset.
- Whether the API is public, which determines authentication, rate limiting, and CDN
  policy.
- The redistribution rights for the derived SVG fragment library.

