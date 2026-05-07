import pandas as pd
import pytest

from src.exceptions import ConfigurationError
from src.export import export_dataframe


def test_export_csv_to_file(tmp_path):
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    output = str(tmp_path / "out.csv")
    export_dataframe(df, "csv", output)

    result = pd.read_csv(output)
    assert len(result) == 2
    assert list(result.columns) == ["a", "b"]


def test_export_csv_to_stdout(capsys):
    df = pd.DataFrame({"x": [10, 20]})
    export_dataframe(df, "csv", None)

    captured = capsys.readouterr()
    assert "x" in captured.out
    assert "10" in captured.out


def test_export_json_to_file(tmp_path):
    df = pd.DataFrame({"a": [1], "b": [2]})
    output = str(tmp_path / "out.json")
    export_dataframe(df, "json", output)

    with open(output) as f:
        content = f.read()
    assert '"a"' in content
    assert "1" in content


def test_export_json_to_stdout(capsys):
    df = pd.DataFrame({"x": [10, 20]})
    export_dataframe(df, "json", None)

    captured = capsys.readouterr()
    assert '"x"' in captured.out
    assert "10" in captured.out


def test_export_parquet_to_file(tmp_path):
    df = pd.DataFrame({"a": [1, 2, 3]})
    output = str(tmp_path / "out.parquet")
    export_dataframe(df, "parquet", output)

    result = pd.read_parquet(output)
    assert len(result) == 3


def test_export_parquet_requires_output():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(ConfigurationError, match="requires --output"):
        export_dataframe(df, "parquet", None)


def test_export_unsupported_format():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(ConfigurationError, match="Unsupported format"):
        export_dataframe(df, "xml", None)


def test_export_empty_dataframe(tmp_path):
    df = pd.DataFrame()
    output = str(tmp_path / "out.csv")
    export_dataframe(df, "csv", output)
    # Empty df should not create the file
    import os

    assert not os.path.exists(output)
