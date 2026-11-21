from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from .models import Sidc
from .service import SymbolService

app = typer.Typer(
    name="nato-symbol",
    help="Resolve SIDCs and compose military symbols from SVG fragments.",
    no_args_is_help=True,
)


def _service() -> SymbolService:
    return SymbolService()


@app.command()
def resolve(
    terms: Annotated[list[str], typer.Argument(help="Names such as 'friendly air drone'.")],
    identity: Annotated[str | None, typer.Option()] = None,
    symbol_set: Annotated[str | None, typer.Option("--symbol-set")] = None,
    entity: Annotated[str | None, typer.Option()] = None,
    context: Annotated[str | None, typer.Option()] = None,
    status: Annotated[str | None, typer.Option()] = None,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print decoded JSON metadata.")
    ] = False,
) -> None:
    service = _service()
    sidc, _definition = service.resolve(
        " ".join(terms),
        identity=identity,
        symbol_set=symbol_set,
        entity=entity,
        context=context,
        status=status,
    )
    if as_json:
        typer.echo(json.dumps(service.describe(sidc), indent=2))
    else:
        typer.echo(str(sidc))


@app.command()
def describe(sidc: Annotated[str, typer.Argument(help="A 20-digit SIDC.")]) -> None:
    typer.echo(json.dumps(_service().describe(Sidc(sidc)), indent=2))


@app.command()
def render(
    value: Annotated[
        list[str], typer.Argument(help="A 20-digit SIDC or constituent names.")
    ],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    service = _service()
    text = " ".join(value)
    sidc = Sidc(text) if len(value) == 1 and text.isdigit() else service.resolve(text)[0]
    rendered = service.render(sidc).rendered
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(rendered.svg)
        typer.echo(str(output))
    else:
        typer.echo(rendered.svg.decode("utf-8"))


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000, min=1, max=65535),
    reload: bool = typer.Option(False, help="Reload when source files change."),
) -> None:
    import uvicorn

    uvicorn.run("nato_symbol_generator.api:app", host=host, port=port, reload=reload)

