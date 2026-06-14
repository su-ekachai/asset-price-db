from collections.abc import Generator
from contextlib import contextmanager

from src.cli.state import state
from src.db.connection import QuestDBReader, QuestDBWriter
from src.db.repository import OHLCVRepository


@contextmanager
def open_repo() -> Generator[OHLCVRepository]:
    """Yield a repository backed by fresh connections, releasing the reader on exit."""
    reader = QuestDBReader(state.cfg.database)
    try:
        yield OHLCVRepository(QuestDBWriter(state.cfg.database), reader)
    finally:
        reader.close()
