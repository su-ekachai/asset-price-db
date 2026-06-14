from typing import Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from src.cli.deps import open_repo
from src.exceptions import DatabaseError
from src.services.integrity import IntegrityService

check_app = typer.Typer(help="Data integrity checks.", no_args_is_help=True)
console = Console(stderr=True)


@check_app.command()
def gaps(
    symbol: Annotated[str, typer.Argument(help="Symbol to check for gaps.")],
    exchange: Annotated[
        str,
        typer.Option("--exchange", "-e", help="Exchange name.", rich_help_panel="Filters"),
    ] = "binance",
    timeframe: Annotated[
        str,
        typer.Option("--timeframe", "-t", help="Candle timeframe.", rich_help_panel="Filters"),
    ] = "1m",
) -> None:
    """Find gaps in stored data.

    Example:
        ohlcv check gaps BTC/USDT -e binance -t 1m
    """
    logger.info("Checking gaps for {} ({}/{})", symbol, exchange, timeframe)
    with open_repo() as repo:
        service = IntegrityService(repo)

        try:
            gaps_found = service.find_gaps(symbol, exchange, timeframe)
        except DatabaseError as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            console.print("[dim]Hint: Verify QuestDB is running with 'ohlcv check health'[/dim]")
            raise typer.Exit(code=1) from None

        out = Console()
        if not gaps_found:
            out.print(f"[green]No gaps found for {symbol} ({exchange}/{timeframe})[/green]")
            return

        table = Table(title=f"Gaps: {symbol} ({exchange}/{timeframe})")
        table.add_column("Start")
        table.add_column("End")
        table.add_column("Missing Candles", justify="right")

        for gap in gaps_found:
            table.add_row(str(gap.start), str(gap.end), str(gap.missing_candles))

        out.print(table)
        total_missing = sum(g.missing_candles for g in gaps_found)
        out.print(f"\nTotal: {len(gaps_found)} gaps, {total_missing} missing candles")
        if timeframe in ("1d", "1wk", "1mo"):
            out.print(
                "[dim]Note: for market-hours assets (stocks/forex), weekend and "
                "holiday gaps are expected and not data errors.[/dim]"
            )
        logger.info("Found {} gaps ({} missing candles)", len(gaps_found), total_missing)


@check_app.command()
def anomalies(
    symbol: Annotated[str, typer.Argument(help="Symbol to check for anomalies.")],
    exchange: Annotated[
        str,
        typer.Option("--exchange", "-e", help="Exchange name.", rich_help_panel="Filters"),
    ] = "binance",
    timeframe: Annotated[
        str,
        typer.Option("--timeframe", "-t", help="Candle timeframe.", rich_help_panel="Filters"),
    ] = "1m",
) -> None:
    """Detect data quality anomalies.

    Example:
        ohlcv check anomalies BTC/USDT -e binance
    """
    logger.info("Checking anomalies for {} ({}/{})", symbol, exchange, timeframe)
    with open_repo() as repo:
        service = IntegrityService(repo)

        try:
            anomalies_found = service.find_anomalies(symbol, exchange, timeframe)
        except DatabaseError as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            console.print("[dim]Hint: Verify QuestDB is running with 'ohlcv check health'[/dim]")
            raise typer.Exit(code=1) from None

        out = Console()
        if not anomalies_found:
            out.print(f"[green]No anomalies found for {symbol} ({exchange}/{timeframe})[/green]")
            return

        table = Table(title=f"Anomalies: {symbol} ({exchange}/{timeframe})")
        table.add_column("Timestamp")
        table.add_column("Type")
        table.add_column("Details")

        for a in anomalies_found:
            table.add_row(str(a.timestamp), a.anomaly_type, a.details)

        out.print(table)
        out.print(f"\nTotal: {len(anomalies_found)} anomalies found")
        logger.info("Found {} anomalies", len(anomalies_found))


@check_app.command()
def health() -> None:
    """Verify system health and connectivity.

    Example:
        ohlcv check health
    """
    logger.info("Running health check")
    with open_repo() as repo:
        service = IntegrityService(repo)

        try:
            report = service.check_health()
        except DatabaseError as e:
            console.print("[red]Database: Not connected[/red]")
            console.print(f"  Error: {e}")
            console.print("[dim]Hint: Start QuestDB with 'docker-compose up -d'[/dim]")
            raise typer.Exit(code=1) from None

        out = Console()
        if report.connected:
            out.print("[green]Database: Connected[/green]")
            out.print(f"Tables exist: {'Yes' if report.tables_exist else 'No'}")
            out.print(f"Total rows: {report.total_rows:,}")
            out.print(f"Symbols tracked: {report.symbol_count}")
        else:
            out.print("[red]Database: Not connected[/red]")
            for err in report.errors:
                out.print(f"  Error: {err}")
            raise typer.Exit(code=1)
