import sys

import pandas as pd
from loguru import logger

from src.exceptions import ConfigurationError


def export_dataframe(df: pd.DataFrame, fmt: str, output: str | None) -> None:
    """Export DataFrame to file or stdout in the given format (csv, parquet, json)."""
    if df.empty:
        logger.warning("Nothing to export: DataFrame is empty")
        return

    if fmt == "csv":
        if output:
            df.to_csv(output, index=False)
        else:
            df.to_csv(sys.stdout, index=False)

    elif fmt == "json":
        json_str = df.to_json(orient="records", date_format="iso", indent=2) or ""
        if output:
            with open(output, "w") as f:
                f.write(json_str)
        else:
            sys.stdout.write(json_str)
            sys.stdout.write("\n")

    elif fmt == "parquet":
        if not output:
            raise ConfigurationError("Parquet format requires --output file path.")
        df.to_parquet(output, index=False)

    else:
        raise ConfigurationError(f"Unsupported format: {fmt}. Use csv, json, or parquet.")
