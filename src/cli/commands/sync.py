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
from rich.table import Table

from src.cli.state import state
from src.db.connection import QuestDBReader, QuestDBWriter
from src.db.repository import OHLCVRepository
from src.exceptions import ConfigurationError
from src.services.sync import SyncResult, SyncService
from src.watchlist import load_watchlist

console = Console(stderr=True)


def sync(
    symbols: Annotated[
        list[str] | None,
        typer.Argument(help="Symbols to sync (omit for all watchlist)."),
    ] = None,
    watchlist_path: Annotated[
        str,
        typer.Option(
            "--watchlist",
            help="Path to watchlist YAML.",
            rich_help_panel="Configuration",
        ),
    ] = "symbols.yaml",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would be downloaded without fetching.",
            rich_help_panel="Behavior",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", help="Suppress output (for cron).", rich_help_panel="Behavior"),
    ] = False,
) -> None:
    """Sync OHLCV data for watchlist symbols to present.

    Examples:
        ohlcv sync
        ohlcv sync BTC/USDT --dry-run
        ohlcv sync --watchlist custom.yaml --quiet
    """
    try:
        wl = load_watchlist(watchlist_path)
    except ConfigurationError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print(
            "[dim]Hint: Copy symbols.yaml.example to symbols.yaml and customize it,[/dim]"
        )
        console.print(
            "[dim]      or use 'ohlcv download BTC/USDT --start 2024-01-01' "
            "for one-off downloads.[/dim]"
        )
        raise typer.Exit(code=1) from None

    if symbols:
        entries = [e for e in wl.symbols if e.symbol in symbols]
        if not entries:
            missing = ", ".join(symbols)
            console.print(
                f"[bold red]Error:[/bold red] None of the specified symbols "
                f"found in watchlist: {missing}"
            )
            raise typer.Exit(code=1)
    else:
        entries = wl.symbols

    reader = QuestDBReader(state.cfg.database)
    try:
        writer = QuestDBWriter(state.cfg.database)
        repo = OHLCVRepository(writer, reader)

        service = SyncService(repo, rate_limit_pause=state.cfg.download.rate_limit_pause)

        results: list[SyncResult] = []
        if quiet:
            for entry in entries:
                result = service.sync_symbol(entry, dry_run=dry_run)
                results.append(result)
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                console=Console(stderr=True),
            ) as progress:
                task = progress.add_task("Syncing...", total=len(entries))
                for entry in entries:
                    progress.update(task, description=f"Syncing {entry.symbol}...")
                    result = service.sync_symbol(entry, dry_run=dry_run)
                    results.append(result)
                    progress.advance(task)

        failed = [r for r in results if r.status == "failed"]
        synced = [r for r in results if r.status == "synced"]
        skipped = [r for r in results if r.status == "skipped"]

        if not quiet:
            out = Console()
            table = Table(title="Sync Results")
            table.add_column("Symbol")
            table.add_column("Exchange")
            table.add_column("Timeframe")
            table.add_column("Status")
            table.add_column("Rows")
            table.add_column("Duration")
            table.add_column("Message")

            status_style = {
                "synced": "green",
                "skipped": "yellow",
                "failed": "red",
                "dry_run": "blue",
            }

            for r in results:
                table.add_row(
                    r.symbol,
                    r.exchange,
                    r.timeframe,
                    f"[{status_style.get(r.status, 'white')}]{r.status}[/]",
                    str(r.rows_inserted),
                    f"{r.duration:.1f}s",
                    r.message,
                )

            out.print(table)
            out.print(
                f"\nTotal: {len(results)} symbols — "
                f"{len(synced)} synced, {len(skipped)} skipped, {len(failed)} failed"
            )

            if synced:
                total_rows = sum(r.rows_inserted for r in synced)
                out.print(f"Rows inserted: {total_rows:,}")

        if failed:
            if not quiet:
                for r in failed:
                    logger.error("{}: {}", r.symbol, r.message)
            raise typer.Exit(code=1)
    finally:
        reader.close()
