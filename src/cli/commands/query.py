from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from src.cli.deps import open_repo
from src.exceptions import ConfigurationError
from src.export import export_dataframe

console = Console(stderr=True)


class OutputFormat(StrEnum):
    """Supported output formats for data export."""

    csv = "csv"
    json = "json"
    parquet = "parquet"


def query(
    symbol: Annotated[
        str | None,
        typer.Argument(help="Symbol to query. Omit with --list to list all."),
    ] = None,
    exchange: Annotated[
        str,
        typer.Option("--exchange", "-e", help="Exchange name.", rich_help_panel="Filters"),
    ] = "binance",
    timeframe: Annotated[
        str,
        typer.Option("--timeframe", "-t", help="Candle timeframe.", rich_help_panel="Filters"),
    ] = "1m",
    start_date: Annotated[
        str | None,
        typer.Option("--start", "-s", help="Start date (YYYY-MM-DD).", rich_help_panel="Filters"),
    ] = None,
    end_date: Annotated[
        str | None,
        typer.Option("--end", help="End date (YYYY-MM-DD).", rich_help_panel="Filters"),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", help="Max rows to return.", rich_help_panel="Filters"),
    ] = None,
    fmt: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format.", rich_help_panel="Output"),
    ] = OutputFormat.csv,
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path (required for parquet).",
            rich_help_panel="Output",
        ),
    ] = None,
    list_mode: Annotated[
        bool,
        typer.Option("--list", help="List available symbols.", rich_help_panel="Output"),
    ] = False,
) -> None:
    """Query stored OHLCV data and export to CSV, JSON, or Parquet.

    Examples:
        ohlcv query BTC/USDT --start 2024-01-01 --format csv
        ohlcv query --list
        ohlcv query AAPL -e yahoo -t 1d --format json -o data.json
    """
    with open_repo() as repo:
        if list_mode:
            logger.info("Listing stored symbols")
            df = repo.get_symbols()
            if df.empty:
                console.print("[bold red]Error:[/bold red] No data stored yet.")
                raise typer.Exit(code=1)

            out = Console()
            table = Table(title="Available Data")
            table.add_column("Symbol")
            table.add_column("Exchange")
            table.add_column("Timeframe")
            table.add_column("Rows", justify="right")
            table.add_column("Last Update")

            for _, row in df.iterrows():
                table.add_row(
                    str(row["symbol"]),
                    str(row["exchange"]),
                    str(row["timeframe"]),
                    f"{int(row['rows']):,}",
                    str(row["last_update"]),
                )

            out.print(table)
            return

        if not symbol:
            console.print("[bold red]Error:[/bold red] SYMBOL argument required (or use --list).")
            console.print("[dim]Hint: Run 'ohlcv query --list' to see available symbols.[/dim]")
            raise typer.Exit(code=1)

        start = None
        end = None
        try:
            if start_date:
                start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC)
            if end_date:
                end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError as e:
            console.print(f"[bold red]Error:[/bold red] Dates must be in YYYY-MM-DD format: {e}")
            raise typer.Exit(code=1) from None

        logger.info(
            "Querying {} ({}/{}) from {} to {}",
            symbol,
            exchange,
            timeframe,
            start_date,
            end_date,
        )
        df = repo.get_candles(symbol, exchange, timeframe, start=start, end=end, limit=limit)

        if df.empty:
            console.print(
                f"[bold red]Error:[/bold red] No data found for {symbol} ({exchange}/{timeframe})."
            )
            raise typer.Exit(code=1)

        try:
            export_dataframe(df, fmt.value, output)
        except ConfigurationError as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=1) from None
        except OSError as e:
            console.print(f"[bold red]Error:[/bold red] Cannot write output file: {e}")
            raise typer.Exit(code=1) from None

        logger.info("Exported {} rows as {}", len(df), fmt.value)
        if output:
            Console().print(f"Exported {len(df):,} rows to {output}")
