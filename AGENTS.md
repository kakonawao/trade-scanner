# AGENTS.md — trader

## Project

Python CLI tool that scans a list of financial instruments (stocks, ETFs,
forex, crypto) for technical patterns. Inputs are pluggable: instrument
list source, data provider, and detection pattern.

## Commands

```bash
uv venv                          # create virtual environment
uv sync --dev                    # editable install with dev deps
uv run pytest                    # run all unit tests (excludes integration)
uv run pytest tests/ -v          # verbose
uv run pytest tests/test_patterns_vcp.py  # single test file
uv run pytest -m integration     # integration tests (manual, hits live APIs)
uv run pytest tests/integration/ # also runs integration tests explicitly
```

## Project structure

```
trade_scanner/              # main package
├── cli.py                       # entry point
├── scanner.py                   # orchestration
├── indicators.py                # technical indicator functions
├── types.py                     # Instrument types (Ticker, ISIN, CurrencyPair)
├── patterns/                    # detection patterns (VCP, etc.)
└── providers/
    ├── instruments/             # where instrument lists come from
    └── prices/                  # where price data comes from
tests/                           # pytest suite
```

## Key conventions

- Instrument identifiers are provider-agnostic: ISIN (`DE0007164600`),
  MIC:TICKER (`XNYS:BRK.A`), or PAIR (`EUR/USD`, `BTC/USD`).
- The combined string format (`MIC:TICKER`, `EUR/USD`) is a CLI concern.
  Internally the system uses typed dataclasses: `Ticker`, `ISIN`, `CurrencyPair`.
  `parse_instrument(s)` converts strings at the boundary.
- `DataProvider.to_provider_symbol(instrument)` takes a typed `Instrument`
  and returns the provider-specific API string (e.g., `"SAP.PA"`, `"EURUSD=X"`).
- `Result.symbol` is typed as `Instrument`, not `str`.
- Patterns implement `detect(df) → Result[T] | None`.
- `Result` is generic over pattern-specific details.
- All modules are stateless — no global state or caches.
- Use relative imports within the main application code.

## Critical Context

- VCP peak search iterates from highest to lowest unique High values in the last 90 bars, skipping any without at least `min_consolidation_bars` (default 15) of data after them. This prevents breakouts from being mistaken for VCP peaks.
- `_is_uptrend` checks SMA alignment at the PEAK row (before pullback); NaN SAFMA returns `False` (was a latent bug when peak was too early for SMA_200).
- `current_price` and "current" end_date use `last_valid_index()` instead of `iloc[-1]` to handle yfinance NaN close on last bar.
- `contraction_ratio` uses window-wide trend (`ATR_5_end / ATR_5_start`) not last-bar snapshot (`ATR_5 / ATR_21`).
- Each scoring criterion has its own `_score_*` private method; `_compute_score` is a simple sum. VCP weights: contraction (22), tightness (17), volume dry-up (17), decline (13), recovery (13), stages (10), peak distance (4), trend (4). Max 100. Bull Flag weights: pole (15), retrace (20), tightness (15), volume (15), duration (10), breakout (15), trend (10). Max 100. Both patterns are on a 100-point basis so scores are comparable.
- Uptrend alignment is a hard filter (not scored) — stocks that fail are excluded entirely.
- `--end-date` / `-e` passes `end` parameter to yfinance; "current" detection compares against `last_valid_index()`.

- `VcpDetails` has `criteria_met` / `criteria_total` fields showing how many of 8 VCP qualifiers are satisfied. The CLI displays them as "5/8" alongside the additive score.
- Criteria: decline 5-35%, contraction < 0.9, stages >= 2, volume dry-up, tight, recovery 10-99%, trend rising/steady, peak distance < 5%.
- Final score = additive score × (criteria_met / criteria_total), so missing criteria meaningfully reduces the score. Criteria column appears before score in CLI output.

## CLI table output

### Non-verbose (default)
One row per symbol, one column per pattern with score and optional criteria in parentheses (e.g., `40 (5/8)`). Zero-score patterns below `--min-score` hide the entire row. `—` means the pattern didn't run or had no result for that symbol. Columns: `symbol`, `<pattern1>`, `<pattern2>`, ..., `price`.

### Verbose (`-v`)
Separate tables per pattern, each with its own consistent column headers (VCP: peak date, peak, decline, contraction, recovery, price, trend — Flag: pole date, pole gain, retrace, flag bars, breakout, price). Pattern name printed as a section header above each table. Tables sorted by score descending. Detail columns are always present even for zero-score rows so the structure is consistent.

### Errors
Always shown at the bottom as a separate `errors` table in both verbose and non-verbose modes. Columns: `symbol`, `pattern`, `error`. Not affected by `--min-score`.

### CSV / JSON
Flat format: one row per pattern per instrument, all columns present.

## Scanner error handling

`scan()` catches `PatternError` and `Exception` from `p.detect(df)`, yielding `Result(error=...)` instead of crashing. Unexpected exceptions are prefixed with `"Unexpected error: "`.

## Next Steps
- Add unit tests for Bull Flag pattern
- Add integration tests for multi-pattern scanning
- Add `PatternError` / `Exception` edge case tests for scanner (garbage data, fake instruments)
- Add more patterns (breakout, pullback-to-SMA) in `trade_scanner/patterns/`
- Implement `WatchlistProvider` for portfolio service integration
- Implement additional price providers beyond yahoo
