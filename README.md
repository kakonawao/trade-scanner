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
| `-p, --pattern` | `all` | Pattern(s) to scan for |
| `--prices-provider` | `yahoo` | Price data source |
| `-m, --min-score` | `50` | Minimum score threshold |
| `-o, --output` | `table` | Output format: `table`, `csv`, `json` |
| `--period` | `1y` | Lookback period (e.g., `1y`, `6mo`, `3mo`) |

### Example

```bash
trade-scanner -i instruments.txt -o table
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

## Output

Common columns for all patterns: `symbol`, `score`, `signal`.

### VCP (Volatility Contraction Pattern)

Additional columns:

| Column | Description |
|---|---|
| `decline_pct` | Peak-to-trough decline (%) |
| `contraction_ratio` | Volatility contraction (ATR_5_end / ATR_5_start) |
| `contraction_stages` | Count of contracting volatility phases |
| `tight_range_pct` | Average daily range over last 5 days (%) |
| `vol_dry` | Volume drying up below long-term average |
| `is_tight` | Tight range flag |
| `peak_price` | Peak high price |
| `current_price` | Most recent close |
| `peak_date` | Date of the peak |

**Signal levels:** `strong` (≥70), `mid` (50–69), `weak` (35–49) on a 100-point basis.

### Example output (table)

```
symbol      score  signal    decline_pct    contraction_ratio    contraction_stages
------  -------  --------  ------------  ------------------  --------------------
AAPL          82  strong           15.3                0.45                    3
XPAR:SAP      65  mid             22.1                0.62                    2
EUR/USD       48  weak             8.4                0.78                    1
```

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
