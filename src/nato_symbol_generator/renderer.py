from __future__ import annotations

import copy
import html
import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as StdET

from defusedxml import ElementTree as ET

from .catalogue import EntityDefinition, SymbolCatalogue, UnknownSymbolError
from .models import Sidc

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
StdET.register_namespace("", SVG_NS)
StdET.register_namespace("xlink", XLINK_NS)


class RenderError(ValueError):
    """Raised when a symbol cannot be rendered safely."""


@dataclass(frozen=True, slots=True)
class RenderedSymbol:
    sidc: Sidc
    svg: bytes
    fragments: tuple[str, ...]


class SvgRenderer:
    def __init__(self, asset_root: Path, catalogue: SymbolCatalogue) -> None:
        if not asset_root.is_dir():
            raise RenderError(f"SVG asset directory does not exist: {asset_root}")
        self.asset_root = asset_root
        self.catalogue = catalogue
        self._appendix_index: dict[tuple[str, str], Path] = {}
        self._fallback_index: dict[str, list[Path]] = {}
        for path in asset_root.rglob("*.svg"):
            relative = path.relative_to(asset_root)
            self._fallback_index.setdefault(path.name, []).append(path)
            if len(relative.parts) >= 3 and relative.parts[0] == "Appendices":
                self._appendix_index[(relative.parts[1], path.name)] = path

    def render(self, sidc: Sidc) -> RenderedSymbol:
        entity = self.catalogue.entity_for(sidc)
        fragments = self._fragment_paths(sidc, entity)
        if not fragments:
            raise RenderError(f"No fragments found for SIDC {sidc}")
        layer_markup = []
        source_names = []
        for index, path in enumerate(fragments):
            source_names.append(path.relative_to(self.asset_root).as_posix())
            content = self._safe_fragment(path, f"f{index}-")
            source = html.escape(source_names[-1], quote=True)
            layer_markup.append(f'<g id="layer-{index}" data-fragment="{source}">{content}</g>')
        title = html.escape(f"Military symbol {sidc}")
        description = html.escape(
            f"{entity.symbol_set_name}: {entity.label}; identity "
            f"{sidc.identity}; status {sidc.status}"
        )
        metadata = html.escape(
            f'{{"sidc":"{sidc}","source":"Esri JMSML 2525d1-svgs",'
            f'"renderer":"0.1.0"}}'
        )
        document = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="{SVG_NS}" xmlns:xlink="{XLINK_NS}" '
            'viewBox="0 0 612 792" role="img" aria-labelledby="title description">'
            f'<title id="title">{title}</title><desc id="description">{description}</desc>'
            f'<metadata>{metadata}</metadata>{"".join(layer_markup)}</svg>'
        )
        return RenderedSymbol(
            sidc=sidc,
            svg=document.encode("utf-8"),
            fragments=tuple(source_names),
        )

    def _fragment_paths(self, sidc: Sidc, entity: EntityDefinition) -> list[Path]:
        paths: list[Path] = []
        frame_name = f"{sidc.context}_{sidc.identity}{sidc.symbol_set}_{sidc.status}.svg"
        frame = self.asset_root / "Frames" / frame_name
        if not frame.is_file():
            raise RenderError(f"Frame fragment is missing: Frames/{frame_name}")
        paths.append(frame)
        if sidc.hq_task_force_dummy != "0":
            path = self.asset_root / "HQTFFD" / (
                f"{sidc.identity}{sidc.symbol_set}{sidc.hq_task_force_dummy}.svg"
            )
            if path.is_file():
                paths.append(path)
        if sidc.amplifier != "00":
            folder = "Echelon" if sidc.symbol_set in {"10", "11"} else "Amplifier"
            path = self.asset_root / folder / f"{sidc.identity}{sidc.amplifier}.svg"
            if path.is_file():
                paths.append(path)
        if entity.graphic and entity.graphic != "NA":
            paths.append(self._find_appendix(entity.asset_group, entity.graphic))
        for sector in (1, 2):
            modifier = self.catalogue.modifier_for(sidc, sector)
            if modifier and modifier.graphic and modifier.graphic != "NA":
                paths.append(self._find_appendix(modifier.asset_group, modifier.graphic))
        if sidc.status not in {"0", "1"}:
            condition = self.asset_root / "OCA" / (
                f"{sidc.context}{sidc.identity}{sidc.symbol_set}{sidc.status}2.svg"
            )
            if condition.is_file():
                paths.append(condition)
        return paths

    def _find_appendix(self, group: str, graphic: str) -> Path:
        match = self._appendix_index.get((group, graphic))
        if match:
            return match
        matches = self._fallback_index.get(graphic, [])
        appendix_matches = [path for path in matches if "Appendices" in path.parts]
        if len(appendix_matches) == 1:
            return appendix_matches[0]
        if matches:
            return matches[0]
        raise UnknownSymbolError(f"Referenced SVG fragment is missing: {graphic}")

    @staticmethod
    def _safe_fragment(path: Path, prefix: str) -> str:
        raw = path.read_text(encoding="utf-8-sig")
        if re.search(r"<\s*(script|foreignObject)\b|<!ENTITY", raw, flags=re.IGNORECASE):
            raise RenderError(f"Unsafe SVG content in {path}")
        root = ET.fromstring(raw)
        children = [copy.deepcopy(child) for child in root]
        children = [child for child in children if child.get("display") != "none"]
        id_map: dict[str, str] = {}
        for child in children:
            for element in child.iter():
                for attribute in element.attrib:
                    local = attribute.rsplit("}", 1)[-1]
                    if local.lower().startswith("on"):
                        raise RenderError(f"Unsafe event attribute in {path}")
                old_id = element.get("id")
                if old_id:
                    new_id = prefix + old_id
                    id_map[old_id] = new_id
                    element.set("id", new_id)
        for child in children:
            for element in child.iter():
                for attribute, value in list(element.attrib.items()):
                    if value.startswith(("http://", "https://", "//")):
                        raise RenderError(f"External SVG reference in {path}")
                    for old_id, new_id in id_map.items():
                        value = value.replace(f"url(#{old_id})", f"url(#{new_id})")
                        if value == f"#{old_id}":
                            value = f"#{new_id}"
                    element.set(attribute, value)
                if element.text:
                    for old_id, new_id in id_map.items():
                        element.text = element.text.replace(f"url(#{old_id})", f"url(#{new_id})")
        return "".join(StdET.tostring(child, encoding="unicode") for child in children)

