from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Header, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from . import __version__
from .catalogue import AmbiguousSymbolError, CatalogueError, UnknownSymbolError
from .models import InvalidSidcError, Sidc
from .renderer import RenderError
from .service import SymbolService


class ResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terms: str = ""
    identity: str | None = None
    symbol_set: str | None = None
    entity: str | None = None
    context: str | None = None
    status: str | None = None


class RenderRequest(ResolveRequest):
    pass


def problem(status: int, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"type": "about:blank", "title": title, "status": status, "detail": detail},
        media_type="application/problem+json",
    )


def create_app(service: SymbolService | None = None) -> FastAPI:
    symbol_service = service or SymbolService()
    app = FastAPI(
        title="NATO Symbol Generator",
        version=__version__,
        description="Resolve 20-digit SIDCs and compose military symbols as SVG.",
    )
    app.state.symbol_service = symbol_service

    @app.exception_handler(InvalidSidcError)
    async def invalid_sidc_handler(_request: object, error: InvalidSidcError) -> JSONResponse:
        return problem(400, "Invalid SIDC", str(error))

    @app.exception_handler(UnknownSymbolError)
    async def unknown_symbol_handler(_request: object, error: UnknownSymbolError) -> JSONResponse:
        return problem(404, "Unknown symbol", str(error))

    @app.exception_handler(AmbiguousSymbolError)
    async def ambiguous_symbol_handler(
        _request: object, error: AmbiguousSymbolError
    ) -> JSONResponse:
        return problem(422, "Ambiguous symbol name", str(error))

    @app.exception_handler(RenderError)
    async def render_error_handler(_request: object, error: RenderError) -> JSONResponse:
        return problem(422, "Symbol cannot be rendered", str(error))

    @app.exception_handler(CatalogueError)
    async def catalogue_error_handler(_request: object, error: CatalogueError) -> JSONResponse:
        return problem(422, "Invalid symbol request", str(error))

    def svg_response(sidc: Sidc, if_none_match: str | None = None) -> Response:
        cached = symbol_service.render(sidc)
        headers = {
            "ETag": cached.etag,
            "Cache-Control": "public, max-age=86400",
            "X-SIDC": str(sidc),
            "X-Symbol-Fragments": str(len(cached.rendered.fragments)),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        }
        if if_none_match == cached.etag:
            return Response(status_code=304, headers=headers)
        return Response(
            content=cached.rendered.svg,
            media_type="image/svg+xml",
            headers=headers,
        )

    @app.get("/v1/symbols/{sidc}")
    def get_symbol(
        sidc: str,
        if_none_match: Annotated[str | None, Header()] = None,
    ) -> Response:
        return svg_response(Sidc(sidc), if_none_match)

    @app.get("/v1/symbols/{sidc}/metadata")
    def get_metadata(sidc: str) -> dict[str, object]:
        return symbol_service.describe(Sidc(sidc))

    @app.post("/v1/symbols/resolve")
    def resolve_symbol(request: ResolveRequest) -> dict[str, object]:
        sidc, _definition = symbol_service.resolve(
            request.terms,
            identity=request.identity,
            symbol_set=request.symbol_set,
            entity=request.entity,
            context=request.context,
            status=request.status,
        )
        result = symbol_service.describe(sidc)
        result["render_url"] = f"/v1/symbols/{sidc}"
        return result

    @app.post("/v1/symbols/render")
    def render_symbol(request: RenderRequest) -> Response:
        sidc, _definition = symbol_service.resolve(
            request.terms,
            identity=request.identity,
            symbol_set=request.symbol_set,
            entity=request.entity,
            context=request.context,
            status=request.status,
        )
        return svg_response(sidc)

    @app.get("/v1/catalogue")
    def get_catalogue(
        q: str = "",
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
    ) -> dict[str, object]:
        items = symbol_service.catalogue.search(q, limit)
        return {"items": items, "count": len(items)}

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict[str, object]:
        return {
            "status": "ready",
            "entities": len(symbol_service.catalogue.entities),
            "symbol_sets": len(symbol_service.catalogue.symbol_sets),
            "cache": symbol_service.cache.stats(),
        }

    return app


app = create_app()

