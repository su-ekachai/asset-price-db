from datetime import UTC, datetime, timedelta

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from src.cli.deps import open_repo
from src.exceptions import ConfigurationError, DatabaseError
from src.services.integrity import TIMEFRAME_MINUTES
from src.watchlist import load_watchlist

console = Console()


def status() -> None:
    """Show overview of all stored data."""
    logger.info("Loading data store status")
    with open_repo() as repo:
        try:
            df = repo.get_symbols()
        except DatabaseError as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            console.print("[dim]Hint: Verify QuestDB is running with 'ohlcv check health'[/dim]")
            raise typer.Exit(code=1) from None

        if df.empty:
            console.print(
                "[yellow]No data stored yet. Use 'download' or 'sync' to fetch data.[/yellow]"
            )
            return

        table = Table(title="OHLCV Data Store Status")
        table.add_column("Symbol")
        table.add_column("Exchange")
        table.add_column("Timeframe")
        table.add_column("Rows", justify="right")
        table.add_column("Last Update")
        table.add_column("Status")

        now = datetime.now(UTC)
        fresh_count = 0
        stale_count = 0
        empty_count = 0

        for _, row in df.iterrows():
            rows_count = int(row["rows"])
            last_update = row["last_update"]
            timeframe = str(row["timeframe"])

            if rows_count == 0 or last_update is None:
                status_str = "[red]Empty[/red]"
                empty_count += 1
                last_str = "-"
            else:
                interval_min = TIMEFRAME_MINUTES.get(timeframe, 1440)
                threshold = timedelta(minutes=interval_min * 2)

                if hasattr(last_update, "tzinfo") and last_update.tzinfo is None:
                    last_update = last_update.replace(tzinfo=UTC)

                age = now - last_update
                last_str = str(last_update)

                if age <= threshold:
                    status_str = "[green]Fresh[/green]"
                    fresh_count += 1
                else:
                    status_str = "[yellow]Stale[/yellow]"
                    stale_count += 1

            table.add_row(
                str(row["symbol"]),
                str(row["exchange"]),
                timeframe,
                f"{rows_count:,}",
                last_str,
                status_str,
            )

        console.print(table)
        total = len(df)
        console.print(
            f"\nTotal: {total} symbols — "
            f"{fresh_count} fresh, {stale_count} stale, {empty_count} empty"
        )
        logger.info(
            "Status: {} total, {} fresh, {} stale, {} empty",
            total,
            fresh_count,
            stale_count,
            empty_count,
        )

        _warn_orphaned_data(df)


def _warn_orphaned_data(df) -> None:
    """Print a warning if DB contains symbols not present in the watchlist."""
    try:
        wl = load_watchlist()
    except ConfigurationError:
        return

    watchlist_keys = {(e.symbol, e.exchange, e.timeframe) for e in wl.symbols}

    orphans = []
    for _, row in df.iterrows():
        key = (str(row["symbol"]), str(row["exchange"]), str(row["timeframe"]))
        if key not in watchlist_keys:
            orphans.append(row)

    if not orphans:
        return

    console.print(f"\n[yellow]⚠ {len(orphans)} symbol(s) in database not in watchlist:[/yellow]")
    for row in orphans:
        console.print(
            f"  {row['symbol']} ({row['exchange']}/{row['timeframe']}) "
            f"— {int(row['rows']):,} rows, last update {row['last_update']}"
        )
    console.print(
        "[dim]  Hint: These are not being synced. Add to watchlist to resume, or ignore.[/dim]"
    )
