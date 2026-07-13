# trade-scanner

Scan financial instruments for technical patterns.

## Setup

```bash
uv venv
uv sync --dev
```

## Usage

```
trade-scanner --instruments <file> [options]
```

### Options

| Flag | Default | Description |
|---|---|---|
| `-i, --instruments` | (required) | Path to instrument list file |
| `-p, --pattern` | all | Pattern(s) to scan for (`vcp`, `flag`, or `all`) |
| `--prices-provider` | `yahoo` | Price data source |
| `-m, --min-score` | `50` | Minimum score threshold |
| `-o, --output` | `table` | Output format: `table`, `csv`, `json` |
| `-v, --verbose` | | Show detailed per-pattern tables |
| `--period` | `1y` | Lookback period (e.g. `1y`, `6mo`, `3mo`) |
| `-e, --end-date` | | End date for historical backtesting (YYYY-MM-DD) |

### Example

```bash
trade-scanner -i instruments.txt
```

## Input file

Plain text file, one instrument per line. Blank lines and `#` comments are ignored.

**Instrument formats:**

| Format | Example | Description |
|---|---|---|
| Plain ticker | `AAPL` | Ticker symbol (defaults to US listing) |
| MIC:TICKER | `XPAR:SAP` | Exchange-specific ticker via MIC code |
| Currency pair | `EUR/USD` | Forex pair |
| ISIN | `US0378331005` | International Securities Identifier |

**Example file:**
```
# US stocks
AAPL
MSFT
NVDA

# International with MIC
XPAR:SAP
XLON:BP

# Forex
EUR/USD
GBP/JPY
```

### Supported MIC codes

`XAMS`, `XASX`, `XBOM`, `XBRU`, `XCSE`, `XDUB`, `XETR`, `XFRA`, `XHKG`,
`XICE`, `XKRX`, `XLIS`, `XLON`, `XMAD`, `XMEX`, `XMIL`, `XNAS`, `XNSE`,
`XNYS`, `XOSL`, `XPAR`, `XSES`, `XSTO`, `XSWX`, `XTAE`, `XTKS`, `XTSE`,
`XTSX`, `XWAR`

## Patterns

### VCP (Volatility Contraction Pattern)

Detects Mark Minervini-style VCP setups: a peak-to-trough decline of 5–35%,
volatility contraction across multiple stages, tight price action, volume
dry-up, and recovery toward the peak.

Scoring criteria (max 100): contraction (22), tightness (17), volume dry-up
(17), decline (13), recovery (13), stages (10), peak distance (4), trend (4).

### Bull Flag

Detects flag/pennant patterns: a sharp rally (pole) of 15–50%, followed by
a shallow pullback (retracement ≤ 50%) on declining volatility, with volume
dry-up in the flag.

Scoring criteria (max 100): retracement (20), pole height (15), tightness
(15), volume (15), breakout proximity (15), duration (10), trend (10).

## Output

### Non-verbose (default)

One row per symbol, one column per pattern. Score is shown with optional
criteria in parentheses (e.g., `40 (5/8)`). A dash (`—`) means the pattern
did not match for that symbol. Rows with no scores above `--min-score` are
hidden.

```
symbol    vcp       flag      price
--------  --------  --------  -------
AAPL      72 (6/8)  40 (4/7)  245.83
XPAR:SAP  55 (4/8)  —         68.12
```

### Verbose (`-v`)

Separate tables per pattern with detailed columns, sorted by score descending.

```
vcp
symbol    peak date    peak    decline    contraction    recovery    price    trend
--------  -----------  ------  ---------  -------------  ----------  -------  -------
AAPL      2025-12-15   258.3     -15.3%          0.45       55.0%    245.83  steady
XPAR:SAP  2025-11-20    77.5     -22.1%          0.62       40.2%     68.12  rising

flag
symbol    pole date    pole gain    retrace    flag bars    breakout    price
--------  -----------  -----------  ---------  -----------  ----------  -------
AAPL      2026-03-10       22.5%      35.0%           12        2.1%    245.83
```

### Errors

Always shown as a separate table in both modes.

```
errors
symbol    pattern   error
--------  --------  --------------------------
FAKE      vcp       No price data available
```

### CSV / JSON

Flat format: one row per pattern per instrument, all columns present.

## Tests

Run unit tests (hits no external APIs):

```bash
uv run pytest
```

Run integration tests (fetches live data from Yahoo Finance):

```bash
uv run pytest -m integration
```

Run a single test file:

```bash
uv run pytest tests/test_types.py -v
```
