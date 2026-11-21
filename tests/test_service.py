from nato_symbol_generator.models import Sidc
from nato_symbol_generator.service import SymbolService


def test_resolves_friendly_air_drone() -> None:
    service = SymbolService()
    sidc, definition = service.resolve("friendly air drone")
    assert sidc == Sidc("10030100001103000000")
    assert definition.identifier == "UAV"


def test_renders_standalone_svg_and_caches_it() -> None:
    service = SymbolService()
    first = service.render("10030100001103000000")
    second = service.render("10030100001103000000")
    assert first is second
    assert first.rendered.svg.startswith(b"<?xml")
    assert b"<svg" in first.rendered.svg
    assert b"data-fragment=\"Frames/0_301_0.svg\"" in first.rendered.svg
    assert b"data-fragment=\"Appendices/Air/01110300.svg\"" in first.rendered.svg
    assert service.cache.stats()["hits"] >= 1

