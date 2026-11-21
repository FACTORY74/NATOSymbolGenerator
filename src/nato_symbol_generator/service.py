from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from .catalogue import EntityDefinition, SymbolCatalogue
from .models import Sidc
from .renderer import RenderedSymbol, SvgRenderer


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class CachedRender:
    rendered: RenderedSymbol
    etag: str


class ByteBoundedRenderCache:
    def __init__(self, max_bytes: int = 16 * 1024 * 1024, max_entries: int = 512) -> None:
        self.max_bytes = max_bytes
        self.max_entries = max_entries
        self._items: OrderedDict[str, CachedRender] = OrderedDict()
        self._bytes = 0
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> CachedRender | None:
        with self._lock:
            value = self._items.get(key)
            if value is None:
                self.misses += 1
                return None
            self._items.move_to_end(key)
            self.hits += 1
            return value

    def put(self, key: str, value: CachedRender) -> None:
        size = len(value.rendered.svg)
        if size > self.max_bytes:
            return
        with self._lock:
            previous = self._items.pop(key, None)
            if previous:
                self._bytes -= len(previous.rendered.svg)
            self._items[key] = value
            self._bytes += size
            while self._bytes > self.max_bytes or len(self._items) > self.max_entries:
                _, removed = self._items.popitem(last=False)
                self._bytes -= len(removed.rendered.svg)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "entries": len(self._items),
                "bytes": self._bytes,
                "hits": self.hits,
                "misses": self.misses,
            }


class SymbolService:
    def __init__(
        self,
        asset_root: Path | None = None,
        catalogue_root: Path | None = None,
        cache: ByteBoundedRenderCache | None = None,
    ) -> None:
        root = project_root()
        self.catalogue = SymbolCatalogue(catalogue_root or root / "symbol_catalogue")
        self.renderer = SvgRenderer(asset_root or root / "symbol_fragments_svg", self.catalogue)
        self.cache = cache or ByteBoundedRenderCache()
        self._render_lock = threading.RLock()

    def resolve(self, text: str = "", **fields: str | None) -> tuple[Sidc, EntityDefinition]:
        return self.catalogue.resolve(text, **fields)

    def describe(self, sidc: Sidc | str) -> dict[str, object]:
        value = sidc if isinstance(sidc, Sidc) else Sidc(sidc)
        return self.catalogue.describe(value)

    def render(self, sidc: Sidc | str) -> CachedRender:
        value = sidc if isinstance(sidc, Sidc) else Sidc(sidc)
        key = str(value)
        cached = self.cache.get(key)
        if cached:
            return cached
        with self._render_lock:
            cached = self.cache.get(key)
            if cached:
                return cached
            rendered = self.renderer.render(value)
            digest = hashlib.sha256(rendered.svg).hexdigest()
            cached = CachedRender(rendered=rendered, etag=f'"{digest}"')
            self.cache.put(key, cached)
            return cached

