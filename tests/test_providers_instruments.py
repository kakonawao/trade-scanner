from trade_scanner.providers.instruments import (
    FileProvider,
    InstrumentListProvider,
)


def test_file_provider_is_instrument_list_provider():
    assert isinstance(FileProvider("/nonexistent"), InstrumentListProvider)


def test_file_provider_reads_lines(tmp_path):
    f = tmp_path / "instruments.txt"
    f.write_text("AAPL\nMSFT\nNVDA\n")
    assert FileProvider(str(f)).get_instruments() == ["AAPL", "MSFT", "NVDA"]


def test_file_provider_ignores_comments(tmp_path):
    f = tmp_path / "instruments.txt"
    f.write_text("# this is a comment\nAAPL\nMSFT\n")
    assert FileProvider(str(f)).get_instruments() == ["AAPL", "MSFT"]


def test_file_provider_ignores_blank_lines(tmp_path):
    f = tmp_path / "instruments.txt"
    f.write_text("AAPL\n\nMSFT\n  \nNVDA\n")
    assert FileProvider(str(f)).get_instruments() == ["AAPL", "MSFT", "NVDA"]
