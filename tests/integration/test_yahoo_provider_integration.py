import pytest

from trade_scanner.patterns import VCP
from trade_scanner.providers.prices import YahooProvider
from trade_scanner.types import CurrencyPair, Ticker


@pytest.mark.integration
def test_yahoo_provider_fetches_real_data():
    provider = YahooProvider()
    instruments = [Ticker(symbol="AAPL"), Ticker(symbol="MSFT")]
    result = provider.get_history(instruments, period="1y")
    assert len(result) == 2
    for inst in instruments:
        assert inst in result
        df = result[inst]
        assert df is not None
        assert len(df) > 1
        required = {"Open", "High", "Low", "Close", "Volume"}
        assert required.issubset(set(df.columns))
        # data must be usable by a pattern without crashing
        VCP().detect(df)


@pytest.mark.integration
def test_yahoo_provider_real_unknown_symbol():
    provider = YahooProvider()
    result = provider.get_history([Ticker(symbol="ZZZZZZ_INVALID")])
    assert result[Ticker(symbol="ZZZZZZ_INVALID")] is None


@pytest.mark.integration
def test_yahoo_provider_resolves_mic_ticker():
    provider = YahooProvider()
    inst = Ticker(mic="XNYS", symbol="JPM")
    result = provider.get_history([inst])
    assert result[inst] is not None
    df = result[inst]
    required = {"Open", "High", "Low", "Close", "Volume"}
    assert required.issubset(set(df.columns))
    VCP().detect(df)


@pytest.mark.integration
def test_yahoo_provider_resolves_pair():
    provider = YahooProvider()
    inst = CurrencyPair(base="EUR", counter="USD")
    result = provider.get_history([inst])
    assert result[inst] is not None
    df = result[inst]
    required = {"Open", "High", "Low", "Close", "Volume"}
    assert required.issubset(set(df.columns))
    VCP().detect(df)
