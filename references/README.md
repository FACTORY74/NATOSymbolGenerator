# Reference standards

This directory is for local copies of standards used during implementation. PDF
files are deliberately ignored by Git: their redistribution terms and currency must
be checked independently of this project's source-code licence.

## APP-06 source

The implementation target identified during initial research is:

- **NATO APP-06, Edition E, Version 1, October 2023**
- Promulgated 11 October 2023 under STANAG 2019
- Official catalogue record: <https://nso.nato.int/nso/nsdd/main/standards/ap-details/3169/EN>
- NATO-hosted PDF: <https://coi.nato.int/EWCOI/EW%20COI%20Shared%20Documents/WGs/NEWWG/EW%20Info%20Exchange%20Requirements%20Panel%20%28IERP%29/01_Governing%20Documents/Publications/APP-06%20NATO%20Symbology/APP-06%20EDE%20V1%20E.pdf>
- Public mirror record: <https://en.wikipedia.org/wiki/File:APP-06_E_1.pdf>

Edition E Version 1 is no longer the current edition. Edition E Version 2 was
promulgated in October 2025 and is listed as controlled/restricted by public standards
catalogues. Confirm the required target edition before treating E1 as normative.

## Download status

On 21 November 2026, the NATO document catalogue was reachable and the full E1 PDF
was indexed and readable by search services. Direct downloads from the NATO file host
were rejected with HTTP 403. A complete PDF was also indexed at Wikimedia, but that
mirror rejected the build environment with HTTP 429. No partial or error response has
been retained as a PDF.

The separately supplied MPSOTC link was downloaded and verified. Despite the generic
URL, it is **APP-6A, Military Symbols for Land Based Systems, October 1998**, not
APP-06 Edition E Version 1. It has 403 pages and is retained locally as
`APP-6A-Military-Symbols-Land-Based-Systems-1998.pdf`. Its cover states that release
outside NATO requires prior NATO approval. It is therefore git-ignored and must not be
redistributed from this repository. It is useful historical material but is not the
normative source for the proposed 20-digit APP-06(E) implementation.

The intended local filename is:

```text
references/APP-06-Edition-E-Version-1-2023.pdf
```

After obtaining it interactively from the official catalogue or a national
standardization authority, verify that it is a PDF, record its SHA-256 digest, page
count, source, and retrieval date in `manifest.toml`, and keep the PDF uncommitted.

## Visual guide

`Military-Symbology-Guide.svg` is a multilingual Canadian/NATO quick-reference chart
downloaded from Wikimedia Commons. It is an author's own work rather than an official
NATO standard and is licensed CC BY-SA 4.0. Keep its author attribution and licence
when redistributing it. Extracting or adapting its graphics may impose share-alike
terms on the resulting assets, so use it primarily for research and visual comparison.

