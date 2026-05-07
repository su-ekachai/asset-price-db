import pytest

from src.exceptions import ConfigurationError
from src.watchlist import load_watchlist, parse_lookback_days


class TestParseLookbackDays:
    @pytest.mark.parametrize(
        ("input_str", "expected_days"),
        [
            ("1d", 1),
            ("30d", 30),
            ("2w", 14),
            ("4w", 28),
            ("1mo", 30),
            ("6mo", 180),
            ("1y", 365),
            ("5y", 1825),
        ],
    )
    def test_valid_lookback(self, input_str, expected_days):
        assert parse_lookback_days(input_str) == expected_days

    @pytest.mark.parametrize(
        "invalid_input",
        ["", "30", "d", "abc", "30x", "1.5d", "30days", "-1d"],
    )
    def test_invalid_lookback_raises(self, invalid_input):
        with pytest.raises(ConfigurationError, match="Invalid lookback format"):
            parse_lookback_days(invalid_input)


class TestLoadWatchlist:
    def test_valid_watchlist(self, tmp_path):
        f = tmp_path / "symbols.yaml"
        f.write_text("""
symbols:
  - symbol: BTC/USDT
    exchange: binance
    timeframe: 1m
    lookback: 30d
  - symbol: AAPL
    exchange: yahoo
    timeframe: 1d
    lookback: 2y
""")
        wl = load_watchlist(f)

        assert len(wl.symbols) == 2
        assert wl.symbols[0].symbol == "BTC/USDT"
        assert wl.symbols[0].exchange == "binance"
        assert wl.symbols[0].timeframe == "1m"
        assert wl.symbols[0].lookback == "30d"
        assert wl.symbols[1].symbol == "AAPL"
        assert wl.symbols[1].exchange == "yahoo"

    def test_default_lookback(self, tmp_path):
        f = tmp_path / "symbols.yaml"
        f.write_text("""
symbols:
  - symbol: BTC/USDT
    exchange: binance
    timeframe: 1m
""")
        wl = load_watchlist(f)
        assert wl.symbols[0].lookback == "30d"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ConfigurationError, match="not found"):
            load_watchlist(tmp_path / "nonexistent.yaml")

    def test_empty_yaml_raises(self, tmp_path):
        f = tmp_path / "symbols.yaml"
        f.write_text("")

        with pytest.raises(ConfigurationError, match="must contain a 'symbols' key"):
            load_watchlist(f)

    def test_no_symbols_key_raises(self, tmp_path):
        f = tmp_path / "symbols.yaml"
        f.write_text("other_key: value\n")

        with pytest.raises(ConfigurationError, match="must contain a 'symbols' key"):
            load_watchlist(f)

    def test_non_dict_entry_raises(self, tmp_path):
        f = tmp_path / "symbols.yaml"
        f.write_text("""
symbols:
  - just a string
""")
        with pytest.raises(ConfigurationError, match="Entry 0 must be a mapping"):
            load_watchlist(f)

    def test_missing_required_fields_raises(self, tmp_path):
        f = tmp_path / "symbols.yaml"
        f.write_text("""
symbols:
  - symbol: BTC/USDT
    exchange: binance
""")
        with pytest.raises(ConfigurationError, match="missing required fields"):
            load_watchlist(f)

    def test_invalid_lookback_in_entry_raises(self, tmp_path):
        f = tmp_path / "symbols.yaml"
        f.write_text("""
symbols:
  - symbol: BTC/USDT
    exchange: binance
    timeframe: 1m
    lookback: invalid
""")
        with pytest.raises(ConfigurationError, match="Invalid lookback format"):
            load_watchlist(f)

    def test_empty_symbols_list_raises(self, tmp_path):
        f = tmp_path / "symbols.yaml"
        f.write_text("symbols: []\n")

        with pytest.raises(ConfigurationError, match="at least one symbol"):
            load_watchlist(f)
