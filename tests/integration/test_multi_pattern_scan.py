import pytest

from trade_scanner.scanner import scan
from trade_scanner.providers.instruments import InstrumentListProvider
from trade_scanner.providers.prices import YahooProvider


class _InlineProvider(InstrumentListProvider):
    def __init__(self, symbols: list[str]):
        self._symbols = symbols

    def get_instruments(self) -> list[str]:
        return self._symbols


@pytest.mark.integration
def test_multi_pattern_scan_runs_all_patterns():
    provider = _InlineProvider(["NVDA", "AAPL"])
    results = list(scan(
        instrument_provider=provider,
        data_provider=YahooProvider(),
        pattern_names=["vcp", "flag"],
        period="1y",
    ))
    assert len(results) == 4
    patterns_seen = set()
    for r in results:
        assert r.symbol is not None
        patterns_seen.add(r.pattern)
        if r.error:
            continue
        assert r.score >= 0
    assert patterns_seen == {"vcp", "flag"}


@pytest.mark.integration
def test_multi_pattern_scan_single_ticker():
    provider = _InlineProvider(["NVDA"])
    results = list(scan(
        instrument_provider=provider,
        data_provider=YahooProvider(),
        pattern_names=["vcp", "flag"],
        period="1y",
    ))
    assert len(results) == 2
    for r in results:
        assert str(r.symbol) == "NVDA"
        assert r.error is None
        assert r.score >= 0


@pytest.mark.integration
def test_multi_pattern_scan_with_unknown_ticker():
    provider = _InlineProvider(["NVDA", "ZZZZZ_INVALID"])
    results = list(scan(
        instrument_provider=provider,
        data_provider=YahooProvider(),
        pattern_names=["vcp", "flag"],
        period="1y",
    ))
    assert len(results) == 4
    for r in results:
        assert str(r.symbol) in ("NVDA", "ZZZZZ_INVALID")
        if str(r.symbol) == "ZZZZZ_INVALID":
                assert r.error is not None
                assert r.score is None


@pytest.mark.integration
def test_multi_pattern_scan_single_pattern():
    provider = _InlineProvider(["NVDA"])
    results = list(scan(
        instrument_provider=provider,
        data_provider=YahooProvider(),
        pattern_names=["vcp"],
        period="1y",
    ))
    assert len(results) == 1
    assert results[0].pattern == "vcp"
