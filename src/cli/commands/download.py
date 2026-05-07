from datetime import UTC, datetime
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
)

from src.cli.state import state
from src.db.connection import QuestDBReader, QuestDBWriter
from src.db.repository import OHLCVRepository
from src.exceptions import DatabaseError, DownloadError
from src.services.downloader import DownloadService
from src.sources.registry import create_source

console = Console(stderr=True)


def download(
    symbols: Annotated[
        list[str], typer.Argument(help="One or more symbols (e.g. BTC/USDT ETH/USDT).")
    ],
    exchange: Annotated[
        str,
        typer.Option("--exchange", "-e", help="Exchange name.", rich_help_panel="Source"),
    ] = "binance",
    timeframe: Annotated[
        str,
        typer.Option("--timeframe", "-t", help="Candle timeframe.", rich_help_panel="Source"),
    ] = "1m",
    start: Annotated[
        str,
        typer.Option(
            "--start",
            "-s",
            help="Start date (YYYY-MM-DD).",
            rich_help_panel="Date Range",
        ),
    ] = ...,  # type: ignore[assignment]
    end: Annotated[
        str | None,
        typer.Option(
            "--end",
            help="End date (YYYY-MM-DD). Defaults to now.",
            rich_help_panel="Date Range",
        ),
    ] = None,
) -> None:
    """Download OHLCV data for one or more symbols.

    Examples:
        ohlcv download BTC/USDT --start 2024-01-01
        ohlcv download BTC/USDT ETH/USDT -e binance -t 1h -s 2024-01-01 --end 2024-06-01
    """
    try:
        source = create_source(exchange, rate_limit_pause=state.cfg.download.rate_limit_pause)
    except DownloadError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print("[dim]Hint: Supported exchanges: binance, coinbase, yahoo, etc.[/dim]")
        raise typer.Exit(code=1) from None

    if timeframe not in source.supported_timeframes():
        available = ", ".join(source.supported_timeframes())
        console.print(
            f"[bold red]Error:[/bold red] Timeframe '{timeframe}' not supported "
            f"by {exchange}. Available: {available}"
        )
        console.print(
            "[dim]Hint: Use --timeframe with a supported value from the list above.[/dim]"
        )
        raise typer.Exit(code=1)

    for symbol in symbols:
        if not source.validate_symbol(symbol):
            raise typer.BadParameter(f"Symbol '{symbol}' is not valid for {exchange}.")

    reader = QuestDBReader(state.cfg.database)
    try:
        writer = QuestDBWriter(state.cfg.database)
        repo = OHLCVRepository(writer, reader)
        service = DownloadService(repo, {exchange: source})

        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=UTC)
            end_dt = (
                datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=UTC) if end else datetime.now(UTC)
            )
        except ValueError as e:
            console.print(f"[bold red]Error:[/bold red] Dates must be in YYYY-MM-DD format: {e}")
            console.print("[dim]Hint: Use format like --start 2024-01-15[/dim]")
            raise typer.Exit(code=1) from None

        if start_dt >= end_dt:
            console.print("[bold red]Error:[/bold red] Start date must be before end date.")
            raise typer.Exit(code=1)

        if start_dt > datetime.now(UTC):
            console.print("[bold red]Error:[/bold red] Start date cannot be in the future.")
            raise typer.Exit(code=1)

        total_rows = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=Console(stderr=True),
            disable=False,
        ) as progress:
            task = progress.add_task("Downloading...", total=len(symbols))
            for symbol in symbols:
                progress.update(task, description=f"Downloading {symbol}...")
                try:
                    rows = service.download(symbol, exchange, timeframe, start_dt, end_dt)
                    total_rows += rows
                    logger.info("Downloaded {} rows for {}", rows, symbol)
                except (DownloadError, DatabaseError) as e:
                    logger.error("Download failed for {}: {}", symbol, e)
                    if len(symbols) == 1:
                        console.print(f"[bold red]Error:[/bold red] {e}")
                        raise typer.Exit(code=1) from None
                progress.advance(task)

        Console().print(
            f"[green]Done:[/green] Downloaded {total_rows:,} rows for {len(symbols)} symbol(s)"
        )
    finally:
        reader.close()
