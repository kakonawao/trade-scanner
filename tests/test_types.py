import pytest

from trade_scanner.types import (
    CurrencyPair,
    ISIN,
    Ticker,
    parse_instrument,
)


@pytest.mark.parametrize(
    "input_str, expected",
    [
        ("AAPL", Ticker(symbol="AAPL")),
        ("XNYS:BRK.A", Ticker(mic="XNYS", symbol="BRK.A")),
        ("EUR/USD", CurrencyPair(base="EUR", counter="USD")),
        ("DE0007164600", ISIN(code="DE0007164600")),
        ("US0378331005", ISIN(code="US0378331005")),
    ],
)
def test_parse_instrument(input_str, expected):
    assert parse_instrument(input_str) == expected


@pytest.mark.parametrize(
    "inst, expected_str",
    [
        (Ticker(symbol="AAPL"), "AAPL"),
        (Ticker(mic="XNYS", symbol="BRK.A"), "XNYS:BRK.A"),
        (Ticker(), ""),
        (ISIN(code="DE0007164600"), "DE0007164600"),
        (CurrencyPair(base="EUR", counter="USD"), "EUR/USD"),
    ],
)
def test_instrument_str(inst, expected_str):
    assert str(inst) == expected_str
