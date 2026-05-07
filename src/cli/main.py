import signal
import traceback
from types import FrameType
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console

from src.cli.commands.check import check_app
from src.cli.commands.db import db_app
from src.cli.commands.download import download
from src.cli.commands.query import query
from src.cli.commands.status import status
from src.cli.commands.sync import sync
from src.cli.state import init_state, state
from src.exceptions import AssetPriceDBError

__version__ = "0.1.0"

app = typer.Typer(
    name="ohlcv",
    help="OHLCV market data store — download, store, and query candle data.",
    rich_markup_mode="rich",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

console = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        Console().print(f"ohlcv v{__version__}")
        raise typer.Exit()


@app.callback()
def callback(
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose",
            "-v",
            count=True,
            show_default=False,
            help="Increase verbosity (repeat for more: -v, -vv).",
            rich_help_panel="Global Options",
        ),
    ] = 0,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
            rich_help_panel="Global Options",
        ),
    ] = None,
) -> None:
    """OHLCV market data store — download, store, and query candle data."""
    init_state(verbose=verbose)


app.add_typer(check_app, name="check", rich_help_panel="Commands")
app.add_typer(db_app, name="db", rich_help_panel="Commands")
app.command(rich_help_panel="Commands")(download)
app.command(rich_help_panel="Commands")(query)
app.command(rich_help_panel="Commands")(status)
app.command(rich_help_panel="Commands")(sync)


def _handle_sigterm(_signum: int, _frame: FrameType | None) -> None:
    logger.info("Received SIGTERM, shutting down...")
    raise SystemExit(143)


def _handle_sigint(_signum: int, _frame: FrameType | None) -> None:
    logger.info("Received SIGINT, shutting down...")
    raise SystemExit(130)


def main() -> None:
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigint)

    try:
        app()
    except SystemExit:
        raise
    except AssetPriceDBError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if state.verbose >= 2:
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise SystemExit(1) from None
    except Exception as e:
        console.print(f"[bold red]Unexpected error:[/bold red] {e}")
        console.print("[dim]Hint: Run with -vv for full traceback.[/dim]")
        if state.verbose >= 2:
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise SystemExit(2) from None
