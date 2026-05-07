import typer
from loguru import logger
from rich.console import Console

from src.cli.state import state
from src.db.connection import QuestDBReader
from src.db.schema import init_db as db_schema_init
from src.exceptions import DatabaseError

db_app = typer.Typer(help="Database management commands.", no_args_is_help=True)
console = Console(stderr=True)


@db_app.command()
def init() -> None:
    """Initialize database tables and views.

    Example:
        ohlcv db init
    """
    reader = QuestDBReader(state.cfg.database)
    try:
        db_schema_init(reader)
        logger.info("Database initialized successfully.")
    except DatabaseError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print("[dim]Hint: Verify QuestDB is running with 'ohlcv check health'[/dim]")
        raise typer.Exit(code=1) from None
    finally:
        reader.close()
