from fastapi.testclient import TestClient

from nato_symbol_generator.api import create_app
from nato_symbol_generator.service import SymbolService


def test_resolve_and_render_api() -> None:
    client = TestClient(create_app(SymbolService()))
    resolved = client.post("/v1/symbols/resolve", json={"terms": "friendly air drone"})
    assert resolved.status_code == 200
    sidc = resolved.json()["sidc"]
    assert sidc == "10030100001103000000"

    rendered = client.get(f"/v1/symbols/{sidc}")
    assert rendered.status_code == 200
    assert rendered.headers["content-type"].startswith("image/svg+xml")
    assert rendered.headers["etag"]

    not_modified = client.get(
        f"/v1/symbols/{sidc}", headers={"If-None-Match": rendered.headers["etag"]}
    )
    assert not_modified.status_code == 304


def test_health_and_problem_details() -> None:
    client = TestClient(create_app(SymbolService()))
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["entities"] > 100

    invalid = client.get("/v1/symbols/not-a-sidc")
    assert invalid.status_code == 400
    assert invalid.headers["content-type"].startswith("application/problem+json")

