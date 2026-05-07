from src.sources.ccxt_source import CcxtSource
from src.sources.registry import create_source
from src.sources.yahoo import YahooSource


def test_create_source_yahoo():
    source = create_source("yahoo")
    assert isinstance(source, YahooSource)


def test_create_source_binance(mocker):
    mocker.patch("ccxt.binance")
    source = create_source("binance")
    assert isinstance(source, CcxtSource)


def test_create_source_custom_exchange(mocker):
    mocker.patch("ccxt.kraken")
    source = create_source("kraken", rate_limit_pause=1.0)
    assert isinstance(source, CcxtSource)


def test_create_source_passes_rate_limit(mocker):
    mocker.patch("ccxt.binance")
    source = create_source("binance", rate_limit_pause=2.0)
    assert source._rate_limit_pause == 2.0
