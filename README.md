# NATO Symbol Generator

Resolve 20-digit military Symbol Identification Codes (SIDCs) from constituent names
and compose their SVG fragments through a Python CLI or REST API.

The current asset catalogue originates from Esri's archived JMSML
`2525d1-svgs` branch. It targets MIL-STD-2525D Change 1 and is an implementation seed,
not yet a claim of complete APP-06(E) conformance.

## Setup

```powershell
.\setup_env.ps1
.\.venv\Scripts\Activate.ps1
```

## CLI

```powershell
nato-symbol resolve friendly air drone
nato-symbol describe 10030100001103000000
nato-symbol render friendly air drone --output drone.svg
nato-symbol serve
```

## REST API

With the server running, interactive OpenAPI documentation is available at
<http://127.0.0.1:8000/docs>.

```text
POST /v1/symbols/resolve
POST /v1/symbols/render
GET  /v1/symbols/{sidc}
GET  /v1/symbols/{sidc}/metadata
GET  /v1/catalogue
GET  /health/live
GET  /health/ready
```

Example:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/v1/symbols/resolve `
  -ContentType application/json `
  -Body '{"terms":"friendly air drone"}'
```

## End-to-end test harness

The harness starts a real service on a free local port, obtains SIDCs from the
catalogue, requests their metadata and SVG over HTTP, validates and saves every SVG,
then writes an HTML gallery and JSON result report.

```powershell
.\.venv\Scripts\python.exe scripts\symbol_test_harness.py --count 100
```

Open `output/harness/index.html` to inspect the generated symbols. To test a fixed
regression set instead, place one 20-digit SIDC per line in a text file:

```powershell
.\.venv\Scripts\python.exe scripts\symbol_test_harness.py `
  --sidc-file tests\sample_sidcs.txt `
  --output output\regression
```
