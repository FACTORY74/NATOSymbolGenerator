from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from defusedxml import ElementTree as ET

from .models import Sidc

NS = "{http://disa.mil/JointMilSyML.xsd}"


class CatalogueError(ValueError):
    """Base error for catalogue lookup failures."""


class UnknownSymbolError(CatalogueError):
    """Raised when no catalogue entry matches a code or name."""


class AmbiguousSymbolError(CatalogueError):
    """Raised when a name resolves to more than one equally good entry."""


@dataclass(frozen=True, slots=True)
class EntityDefinition:
    symbol_set: str
    symbol_set_name: str
    code: str
    identifier: str
    label: str
    graphic: str | None
    asset_group: str
    terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModifierDefinition:
    symbol_set: str
    sector: int
    code: str
    label: str
    graphic: str | None
    asset_group: str


IDENTITIES = {
    "pending": "0",
    "unknown": "1",
    "assumed friend": "2",
    "assumed friendly": "2",
    "friend": "3",
    "friendly": "3",
    "neutral": "4",
    "suspect": "5",
    "joker": "5",
    "hostile": "6",
    "enemy": "6",
    "faker": "6",
}
IDENTITY_LABELS = {
    "0": "Pending",
    "1": "Unknown",
    "2": "Assumed Friend",
    "3": "Friend",
    "4": "Neutral",
    "5": "Suspect/Joker",
    "6": "Hostile/Faker",
    "9": "Extension",
}
CONTEXTS = {"reality": "0", "real": "0", "exercise": "1", "simulation": "2"}
CONTEXT_LABELS = {"0": "Reality", "1": "Exercise", "2": "Simulation"}
STATUSES = {"present": "0", "planned": "1", "anticipated": "1"}
STATUS_LABELS = {"0": "Present", "1": "Planned/Anticipated"}

TOKEN_ALIASES = {
    "drone": "uav",
    "uas": "uav",
    "rpv": "uav",
    "unmanned aerial vehicle": "uav",
    "friendly": "friend",
    "enemy": "hostile",
}


def _normalise(value: str) -> str:
    value = value.casefold().replace("_", "-")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _code(element: ET.Element, child_name: str) -> str:
    node = element.find(f"{NS}{child_name}")
    if node is None:
        return "00"
    digits = [child.text or "" for child in node if child.tag.startswith(NS)]
    return "".join(digits) or "00"


def _asset_group(filename: str) -> str:
    if filename.startswith("Land_") or filename == "Unknown.xml":
        return "Land"
    if filename.startswith("Air"):
        return "Air"
    if filename.startswith("Space"):
        return "Space"
    if filename.startswith("Sea_Surface"):
        return "SeaSurface"
    if filename.startswith("Sea_Subsurface") or filename.startswith("Mine_Warfare"):
        return "SeaSubsurface"
    if filename.startswith("SIGINT"):
        return "SigInt"
    if filename.startswith("Control_Measure"):
        return "ControlMeasures"
    if filename.startswith("Activity"):
        return "Activities"
    if filename.startswith("Cyber"):
        return "Cyberspace"
    if filename.startswith(("Atmospheric", "Meteorological", "Oceanographic")):
        return "METOC"
    return "Land"


class SymbolCatalogue:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.entities: dict[tuple[str, str], EntityDefinition] = {}
        self.modifiers: dict[tuple[str, int, str], ModifierDefinition] = {}
        self.symbol_sets: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.root.is_dir():
            raise CatalogueError(f"Catalogue directory does not exist: {self.root}")
        for path in sorted(self.root.glob("*.xml")):
            tree = ET.parse(path)
            root = tree.getroot()
            if root.tag != f"{NS}SymbolSet":
                continue
            symbol_set = _code(root, "SymbolSetCode")
            symbol_set_name = root.get("Label", path.stem.replace("_", " "))
            group = _asset_group(path.name)
            self.symbol_sets[symbol_set] = symbol_set_name
            entities = root.find(f"{NS}Entities")
            if entities is not None:
                for entity in entities.findall(f"{NS}Entity"):
                    self._load_entity(symbol_set, symbol_set_name, group, entity)
            self._load_modifiers(root, symbol_set, group, 1, "SectorOneModifiers")
            self._load_modifiers(root, symbol_set, group, 2, "SectorTwoModifiers")
        if not self.entities:
            raise CatalogueError(f"No symbol definitions were loaded from {self.root}")

    def _definition(
        self,
        symbol_set: str,
        symbol_set_name: str,
        group: str,
        element: ET.Element,
        code: str,
        parent_terms: tuple[str, ...],
    ) -> EntityDefinition:
        identifier = element.get("ID", code)
        label = element.get("Label", identifier.replace("_", " ").title())
        aliases = element.get("LabelAlias", "")
        raw_terms = (*parent_terms, identifier, label, aliases)
        terms = tuple(dict.fromkeys(term for term in (_normalise(v) for v in raw_terms) if term))
        return EntityDefinition(
            symbol_set=symbol_set,
            symbol_set_name=symbol_set_name,
            code=code,
            identifier=identifier,
            label=label,
            graphic=element.get("Graphic"),
            asset_group=group,
            terms=terms,
        )

    def _load_entity(
        self,
        symbol_set: str,
        symbol_set_name: str,
        group: str,
        entity: ET.Element,
    ) -> None:
        entity_code = _code(entity, "EntityCode")
        definition = self._definition(
            symbol_set, symbol_set_name, group, entity, entity_code + "0000", ()
        )
        self.entities[(symbol_set, definition.code)] = definition
        entity_terms = definition.terms
        types = entity.find(f"{NS}EntityTypes")
        if types is None:
            return
        for entity_type in types.findall(f"{NS}EntityType"):
            type_code = _code(entity_type, "EntityTypeCode")
            type_definition = self._definition(
                symbol_set,
                symbol_set_name,
                group,
                entity_type,
                entity_code + type_code + "00",
                entity_terms,
            )
            self.entities[(symbol_set, type_definition.code)] = type_definition
            subtypes = entity_type.find(f"{NS}EntitySubTypes")
            if subtypes is None:
                continue
            for subtype in subtypes.findall(f"{NS}EntitySubType"):
                subtype_code = _code(subtype, "EntitySubTypeCode")
                subtype_definition = self._definition(
                    symbol_set,
                    symbol_set_name,
                    group,
                    subtype,
                    entity_code + type_code + subtype_code,
                    type_definition.terms,
                )
                self.entities[(symbol_set, subtype_definition.code)] = subtype_definition

    def _load_modifiers(
        self,
        root: ET.Element,
        symbol_set: str,
        group: str,
        sector: int,
        container_name: str,
    ) -> None:
        container = root.find(f"{NS}{container_name}")
        if container is None:
            return
        for modifier in container.findall(f"{NS}Modifier"):
            code = _code(modifier, "ModifierCode")
            self.modifiers[(symbol_set, sector, code)] = ModifierDefinition(
                symbol_set=symbol_set,
                sector=sector,
                code=code,
                label=modifier.get("Label", modifier.get("ID", code)),
                graphic=modifier.get("Graphic"),
                asset_group=group,
            )

    def entity_for(self, sidc: Sidc) -> EntityDefinition:
        try:
            return self.entities[(sidc.symbol_set, sidc.entity)]
        except KeyError as error:
            raise UnknownSymbolError(
                f"Unknown entity {sidc.entity} in symbol set {sidc.symbol_set}"
            ) from error

    def modifier_for(self, sidc: Sidc, sector: int) -> ModifierDefinition | None:
        code = sidc.modifier_one if sector == 1 else sidc.modifier_two
        if code == "00":
            return None
        return self.modifiers.get((sidc.symbol_set, sector, code))

    def resolve(
        self,
        text: str,
        *,
        identity: str | None = None,
        symbol_set: str | None = None,
        entity: str | None = None,
        context: str | None = None,
        status: str | None = None,
    ) -> tuple[Sidc, EntityDefinition]:
        query = _normalise(" ".join(filter(None, (text, entity or ""))))
        aliased_query = query
        for source, target in TOKEN_ALIASES.items():
            aliased_query = re.sub(rf"\b{re.escape(source)}\b", target, aliased_query)

        identity_code = self._resolve_named_code(identity, query, IDENTITIES, "identity", "3")
        context_code = self._resolve_named_code(context, query, CONTEXTS, "context", "0")
        status_code = self._resolve_named_code(status, query, STATUSES, "status", "0")
        symbol_set_code = self._resolve_symbol_set(symbol_set, query)

        ignored = set()
        for phrase in (*IDENTITIES, *CONTEXTS, *STATUSES):
            ignored.update(_normalise(phrase).split())
        for name in self.symbol_sets.values():
            ignored.update(_normalise(name).split())
        meaningful = {token for token in aliased_query.split() if token not in ignored}

        candidates: list[tuple[int, EntityDefinition]] = []
        for definition in self.entities.values():
            if symbol_set_code and definition.symbol_set != symbol_set_code:
                continue
            score = self._score(definition, aliased_query, meaningful)
            if score > 0:
                candidates.append((score, definition))
        if not candidates:
            raise UnknownSymbolError(f"No symbol entity matches {entity or text!r}")
        candidates.sort(key=lambda item: (item[0], item[1].code.count("0") * -1), reverse=True)
        best_score = candidates[0][0]
        best = [definition for score, definition in candidates if score == best_score]
        unique = {(definition.symbol_set, definition.code): definition for definition in best}
        if len(unique) > 1:
            labels = ", ".join(sorted({definition.label for definition in unique.values()})[:8])
            raise AmbiguousSymbolError(f"Name is ambiguous; matches include: {labels}")
        definition = next(iter(unique.values()))
        sidc = Sidc(
            "10"
            + context_code
            + identity_code
            + definition.symbol_set
            + status_code
            + "0"
            + "00"
            + definition.code
            + "00"
            + "00"
        )
        return sidc, definition

    @staticmethod
    def _score(definition: EntityDefinition, query: str, meaningful: set[str]) -> int:
        score = 0
        for term in definition.terms:
            aliased_term = term
            for source, target in TOKEN_ALIASES.items():
                aliased_term = re.sub(rf"\b{re.escape(source)}\b", target, aliased_term)
            term_tokens = set(aliased_term.split())
            if len(aliased_term) >= 3 and re.search(
                rf"(?:^|\s){re.escape(aliased_term)}(?:$|\s)", query
            ):
                score = max(score, 100 + len(term_tokens))
            if meaningful and meaningful <= term_tokens:
                score = max(score, 50 + len(meaningful))
            elif meaningful:
                score = max(score, len(meaningful & term_tokens) * 5)
        return score

    @staticmethod
    def _resolve_named_code(
        explicit: str | None,
        query: str,
        values: dict[str, str],
        field: str,
        default: str,
    ) -> str:
        if explicit:
            key = _normalise(explicit)
            if key not in values:
                raise UnknownSymbolError(f"Unknown {field}: {explicit}")
            return values[key]
        matches = [(len(name), code) for name, code in values.items() if name in query]
        return max(matches, default=(0, default))[1]

    def _resolve_symbol_set(self, explicit: str | None, query: str) -> str | None:
        if explicit:
            if explicit in self.symbol_sets:
                return explicit
            normal = _normalise(explicit)
            matches = [
                code for code, label in self.symbol_sets.items() if _normalise(label) == normal
            ]
            if len(matches) != 1:
                raise UnknownSymbolError(f"Unknown symbol set: {explicit}")
            return matches[0]
        matches = [
            (len(_normalise(label)), code)
            for code, label in self.symbol_sets.items()
            if _normalise(label) in query
        ]
        return max(matches, default=(0, None))[1]

    def describe(self, sidc: Sidc) -> dict[str, object]:
        entity = self.entity_for(sidc)
        return {
            "sidc": str(sidc),
            "fields": sidc.fields(),
            "context": CONTEXT_LABELS.get(sidc.context, "Unknown"),
            "identity": IDENTITY_LABELS.get(sidc.identity, "Unknown"),
            "status": STATUS_LABELS.get(sidc.status, "Other"),
            "symbol_set": entity.symbol_set_name,
            "entity": entity.label,
            "entity_id": entity.identifier,
            "graphic": entity.graphic,
        }

    def search(self, query: str = "", limit: int = 50) -> list[dict[str, str | None]]:
        normal = _normalise(query)
        results = []
        definitions = sorted(
            self.entities.values(), key=lambda item: (item.symbol_set, item.code)
        )
        for definition in definitions:
            if normal and not any(normal in term for term in definition.terms):
                continue
            results.append(
                {
                    "symbol_set": definition.symbol_set,
                    "symbol_set_name": definition.symbol_set_name,
                    "entity": definition.code,
                    "name": definition.label,
                    "id": definition.identifier,
                    "graphic": definition.graphic,
                }
            )
            if len(results) >= limit:
                break
        return results

