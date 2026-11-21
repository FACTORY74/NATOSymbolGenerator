"""End-to-end HTTP test harness for the NATO Symbol Generator service."""

from __future__ import annotations

import argparse
import html
import json
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import IO
from xml.etree import ElementTree

import httpx


@dataclass(slots=True)
class Result:
    sidc: str
    ok: bool
    status_code: int
    entity: str = ""
    symbol_set: str = ""
    svg_file: str = ""
    bytes: int = 0
    etag: str = ""
    error: str = ""


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def build_sidc(symbol_set: str, entity: str, identity: str, planned: bool) -> str:
    status = "1" if planned else "0"
    value = f"10" f"0" f"{identity}" f"{symbol_set}" f"{status}" f"0" f"00" f"{entity}" f"00" f"00"
    if len(value) != 20 or not value.isdigit():
        raise ValueError(f"Catalogue produced an invalid SIDC: {value}")
    return value


def sidcs_from_catalogue(client: httpx.Client, count: int) -> list[str]:
    response = client.get("/v1/catalogue", params={"limit": min(500, max(count * 3, 50))})
    response.raise_for_status()
    items = [item for item in response.json()["items"] if item.get("graphic") not in {None, "NA"}]
    identities = ("3", "6", "4", "1")
    sidcs = []
    for index, item in enumerate(items):
        sidcs.append(
            build_sidc(
                item["symbol_set"],
                item["entity"],
                identities[index % len(identities)],
                planned=index % 7 == 6,
            )
        )
        if len(sidcs) >= count:
            break
    if len(sidcs) < count:
        raise RuntimeError(f"Catalogue returned only {len(sidcs)} renderable entries")
    return sidcs


def sidcs_from_file(path: Path) -> list[str]:
    values = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        if len(value) != 20 or not value.isascii() or not value.isdigit():
            raise ValueError(f"Invalid SIDC on line {line_number}: {value!r}")
        values.append(value)
    if not values:
        raise ValueError(f"No SIDCs were found in {path}")
    return values


@contextmanager
def running_service(project_root: Path, output: Path, port: int) -> Iterator[str]:
    log_path = output / "service.log"
    log_stream: IO[str] = log_path.open("w", encoding="utf-8")
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "nato_symbol_generator.api:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    process = subprocess.Popen(
        command,
        cwd=project_root,
        stdout=log_stream,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    f"Service exited with code {process.returncode}; see {log_path}"
                )
            try:
                response = httpx.get(f"{base_url}/health/ready", timeout=1)
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        else:
            raise TimeoutError(f"Service was not ready within 20 seconds; see {log_path}")
        yield base_url
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        log_stream.close()


def exercise(client: httpx.Client, sidcs: list[str], svg_dir: Path) -> list[Result]:
    results = []
    for sidc in sidcs:
        try:
            metadata_response = client.get(f"/v1/symbols/{sidc}/metadata")
            metadata_response.raise_for_status()
            metadata = metadata_response.json()
            svg_response = client.get(f"/v1/symbols/{sidc}")
            svg_response.raise_for_status()
            if not svg_response.headers.get("content-type", "").startswith("image/svg+xml"):
                raise ValueError("Response does not have the image/svg+xml media type")
            root = ElementTree.fromstring(svg_response.content)
            if root.tag.rsplit("}", 1)[-1] != "svg":
                raise ValueError("Response document root is not SVG")
            svg_path = svg_dir / f"{sidc}.svg"
            svg_path.write_bytes(svg_response.content)
            results.append(
                Result(
                    sidc=sidc,
                    ok=True,
                    status_code=svg_response.status_code,
                    entity=str(metadata["entity"]),
                    symbol_set=str(metadata["symbol_set"]),
                    svg_file=f"svgs/{svg_path.name}",
                    bytes=len(svg_response.content),
                    etag=svg_response.headers.get("etag", ""),
                )
            )
        except (httpx.HTTPError, KeyError, ValueError, ElementTree.ParseError) as error:
            status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else 0
            results.append(Result(sidc=sidc, ok=False, status_code=status, error=str(error)))
    return results


def write_report(output: Path, base_url: str, results: list[Result], elapsed: float) -> None:
    passed = sum(result.ok for result in results)
    report = {
        "service": base_url,
        "requested": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "elapsed_seconds": round(elapsed, 3),
        "results": [asdict(result) for result in results],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    cards = []
    for result in results:
        if result.ok:
            cards.append(
                '<article class="pass">'
                f'<img src="{html.escape(result.svg_file)}" alt="{html.escape(result.sidc)}">'
                f"<code>{html.escape(result.sidc)}</code>"
                f"<strong>{html.escape(result.entity)}</strong>"
                f"<span>{html.escape(result.symbol_set)} · {result.bytes} bytes</span>"
                "</article>"
            )
        else:
            cards.append(
                '<article class="fail">'
                f"<code>{html.escape(result.sidc)}</code>"
                f"<strong>FAILED ({result.status_code})</strong>"
                f"<span>{html.escape(result.error)}</span>"
                "</article>"
            )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>NATO Symbol Generator test gallery</title>
<style>
body{{font:15px system-ui;margin:2rem;background:#f4f6f8;color:#18202a}}
header{{margin-bottom:1.5rem}}
.gallery{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:1rem}}
article{{display:grid;gap:.45rem;background:white;border:1px solid #ccd3da;
border-radius:.5rem;padding:1rem}}
article img{{width:100%;height:210px;object-fit:contain;background:#fafafa}}
article code{{font-size:.8rem;overflow-wrap:anywhere}}
article span{{color:#52606d;font-size:.85rem}}
.pass{{border-top:4px solid #16803c}} .fail{{border-top:4px solid #c62828}}
</style></head><body><header><h1>NATO Symbol Generator test gallery</h1>
<p>{passed} of {len(results)} passed in {elapsed:.3f} seconds.</p></header>
<main class="gallery">{"".join(cards)}</main></body></html>"""
    (output / "index.html").write_text(document, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=50, help="Number of catalogue SIDCs")
    parser.add_argument("--sidc-file", type=Path, help="Text file containing one SIDC per line")
    parser.add_argument(
        "--output", type=Path, default=Path("output/harness"), help="Report directory"
    )
    parser.add_argument("--port", type=int, default=0, help="Service port; 0 selects a free port")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.count < 1:
        raise ValueError("--count must be at least 1")
    project_root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    svg_dir = output / "svgs"
    svg_dir.mkdir(parents=True, exist_ok=True)
    port = args.port or free_port()
    started = time.monotonic()
    with running_service(project_root, output, port) as base_url:
        with httpx.Client(base_url=base_url, timeout=10) as client:
            sidcs = (
                sidcs_from_file(args.sidc_file)
                if args.sidc_file
                else sidcs_from_catalogue(client, args.count)
            )
            results = exercise(client, sidcs, svg_dir)
        elapsed = time.monotonic() - started
        write_report(output, base_url, results, elapsed)
    passed = sum(result.ok for result in results)
    print(f"{passed}/{len(results)} symbols passed")
    print(f"HTML: {output / 'index.html'}")
    print(f"JSON: {output / 'report.json'}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

