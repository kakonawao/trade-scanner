# Instrument Scanner — Design

## 1. Overview

CLI tool that scans a list of financial instruments (stocks, ETFs,
currencies, crypto, etc.) for technical patterns or setups. All
inputs are pluggable: where the instrument list comes from, where
price data comes from, and what patterns to look for.

## 2. High-Level Components

```
┌──────────────────────────────────────────────────────────────────┐
│                          CLI                                     │
│  picks: instrument list source, data source, pattern             │
│  formats output                                                  │
└──┬───────────────┬───────────────────┬───────────────────────────┘
   │ instruments   │                   │ pattern name
   ▼               ▼                   │
 ┌────────────┐ ┌────────────┐         │
 │ Instrument │ │   Data     │         │
 │ List       │ │  Provider  │         │
 │ Provider   │ │ prices     │         │
 └─────┬──────┘ └─────┬──────┘         │
       │              │                │
       ▼              ▼                ▼
   ┌──────────────────────────────────────┐
   │            Scanner                   │
   │  orchestrates: list → prices → detect│
   └──────────────────┬───────────────────┘
                      │ df per instrument
                      ▼
   ┌──────────────────────────────────────┐
   │        Pattern Detection Engine      │
   │  dispatches to registered patterns   │
   │  (VCP, Bull Flag, etc.)              │
   └──────┬───────────────────────────┬───┘
          │                           │
          ▼                           ▼
   ┌──────────────┐          ┌──────────────┐
   │   Pattern    │          │  Indicators  │
   │   detect()   │          │  (pure fns)  │
   └──────────────┘          └──────────────┘
```

### Instrument List Provider
Abstract interface for sourcing the list of instruments to scan.
Could be a local file, a watchlist API, a predefined universe
(e.g. S&P 500), or a portfolio service.

### Data Provider
Abstract interface for fetching OHLCV price history. The scanner
never calls a data API directly — it always goes through this
interface.

### Pattern
A named detection algorithm. Each pattern implements `detect(df)`
and returns a scored result. Multiple patterns are registered
in a `PATTERNS` dict and can be selected by name.

### Scanner
Orchestrator. Gets the instrument list from its provider, fetches
prices from the data provider, runs the selected pattern on each,
collects and filters results. Stateless.

### CLI
Entry point. Parses args, instantiates the selected instrument
list provider, data provider, and pattern registry, runs the
scanner, formats output.

## 3. Component Details

### 3.1 Instrument Identifiers

Instruments are identified by provider-agnostic strings that stay
valid across data sources. Four formats are supported:

| Format | Example | Scope |
|--------|---------|-------|
| ISIN | `DE0007164600` | Securities (stocks, bonds, ETFs) |
| TICKER | `AAPL` | Securities (stocks, bonds, ETFs) |
| MIC:TICKER | `XNYS:BRK.A` | Exchange-listed instruments |
| PAIR | `EUR/USD`, `BTC/USD` | Forex and crypto spot pairs |

The pipeline never uses provider-specific symbols (e.g. `SAP.DE` for
Yahoo). Each `DataProvider` maintains its own mapping layer to
translate identifiers into whatever the source expects.

### 3.2 Instrument List Provider

Returns `list[str]` of instrument identifiers. Implementations:

| Provider | Description |
|----------|-------------|
| FileProvider | Reads a text file (one symbol per line, `#` comments) |
| WatchlistProvider | Fetches from a portfolio/watchlist service (future) |

### 3.3 Data Provider

Returns `{identifier: DataFrame}` with OHLCV columns (`Open`, `High`,
`Low`, `Close`, `Volume`). A `None` value means the identifier could
not be resolved.

Each provider maps identifiers internally. For example, YahooProvider
listens for ISINs or MIC:TICKER and translates them to yfinance-compatible
symbols before calling the API.

| Implementation | Source |
|----------------|--------|
| YahooProvider | `yfinance.download()`, maps ISIN / MIC:TICKER → Yahoo symbol |
| PortfolioProvider | Local database (future) |

### 3.4 Pattern

A pattern is a named class that implements `detect(df) → Result | None`.
Multiple patterns are registered in a `PATTERNS` dict in `patterns/__init__.py`.

```python
PATTERNS = {
    "vcp": VCP,
    "flag": BullFlag,
}
```

The CLI `--pattern` argument selects which to run (default: all).

#### 3.4.1 VCP Pattern

The VCP (Volatility Contraction Pattern, Minervini) identifies stocks
that have pulled back from a peak, consolidated with shrinking volatility,
and are beginning to recover toward a potential breakout.

##### 3.4.1.1 Indicators

| Indicator | Window | Purpose |
|-----------|--------|---------|
| SMA_50, SMA_150, SMA_200 | 50/150/200 | Uptrend confirmation |
| ATR_5, ATR_10 | 5/10 | Volatility contraction (start-to-end ratio, stages) |
| ATR_21 | 21 | Background indicator (not used in scoring) |
| VMA_10, VMA_50 | 10/50 | Volume drying up |
| RANGE_PCT | 1 | Daily range as % of close |

##### 3.4.1.2 Detection algorithm

All steps operate on the **consolidation window**, defined as the range
from the peak bar (inclusive) through the last bar where `Close < peak_high`.
This excludes post-breakout noise while capturing the pullback.

1. **Peak identification** — iterates unique High values in the last 90 bars
   from highest to lowest, skipping any without at least `min_consolidation_bars`
   (default 15) of data after them. Highest-to-lowest order prevents a recent
   breakout (highest high, but too close to present) from being selected as the
   VCP peak — the algorithm naturally falls through to the next highest peak
   that has enough room for the consolidation window.
2. **Declination filter** — peak-to-trough decline between `min_decline`
   (default 5%) and `max_decline` (default 55%).
3. **Trough confirmation** — the current close must not be below the
   trough (i.e., not making new lows).
4. **Minimum consolidation** — at least `min_consolidation_bars`
   (default 15) trading days from peak.
5. **Uptrend context** — hard filter. At the peak row (before the
   pullback), Close > SMA_50 > SMA_150. SMA_200 is checked if available
   but is optional (allows detection on recently relisted tickers).
6. **Trough date** — recorded as the index of the lowest Low within
   the consolidation window.

##### 3.4.1.3 Metrics

| Metric | Formula | What it measures |
|--------|---------|------------------|
| `decline_pct` | `(peak − trough) / peak` | Depth of the pullback |
| `contraction_ratio` | `ATR_5_end / ATR_5_start` | Volatility contraction from first to last bar of consolidation |
| `contraction_stages` | Count of chunks where ATR_10 decreased | Progression of tightening (0–3) |
| `tight_range_pct` | Mean `RANGE_PCT` over last 5 bars | Recent price range as % of close |
| `is_tight` | `tight_range_pct < 3%` | Binary tightness flag |
| `vol_dry` | `VMA_10 < VMA_50` (last bar) | Volume drying up |
| `recovery_pct` | `(close − trough) / (peak − trough)` | Position within range — 0% = trough, 100% = peak |
| `peak_distance_pct` | `(peak − close) / peak` | Distance from peak — 0% = at peak |
| `vcp_trend` | ROC of close over last 5 bars | Momentum label: rising / steady / flat / weakening / falling |

**Notes on metric design:**

- `contraction_ratio` uses the window-wide trend (`ATR_5_end / ATR_5_start`)
  rather than a last-bar snapshot (e.g., `ATR_5 / ATR_21`). This captures
  the full evolution of volatility through the VCP.
- `recovery_pct` is the primary breakout readiness signal. A stock near
  the peak (high recovery) is closer to breaking out regardless of
  consolidation length.
- `current_price` and end-of-window calculations use `last_valid_index()`
  instead of `iloc[-1]` to handle yfinance NaN close on the last bar.

##### 3.4.1.4 Scoring (max 100)

The additive score is the sum of 8 independent components, then scaled by
`criteria_met / criteria_total` (8 criteria). Uptrend is a hard
prerequisite (filter) rather than a scored component.

| # | Component | Max | Scoring details |
|---|-----------|-----|-----------------|
| 1 | Contraction ratio | 22 | `< 0.5` = 22, `0.5–0.75` = 18, `0.75–0.9` = 13, `0.9–1.1` = 4 |
| 2 | Tightness | 17 | Binary: last 5-bar avg range < 3% |
| 3 | Volume dry-up | 17 | Binary: `VMA_10 < VMA_50` |
| 4 | Decline quality | 13 | `15–25%` ideal = 13, `10–15%` = 9, `25–35%` = 7, `< 10%` or `35–55%` = 4 |
| 5 | Recovery from trough | 13 | Continuous: `min(int(recovery_pct × 13), 13)` |
| 6 | Contraction stages | 10 | `4 × stages`, capped at 10 |
| 7 | Peak distance | 4 | Continuous: `max(0, 4 − int(dist × 100))` |
| 8 | Trend momentum | 4 | `5-bar ROC ≥ 3%` = 4, `≥ 1%` = 2, else 0 |

Criteria (all must pass 8/8 for max score):
`decline 10–35%` | `contraction < 0.9` | `stages >= 2` | `vol_dry` |
`is_tight` | `recovery 10–99%` | `roc >= 0.01` | `peak_distance < 5%`

Score = additive × (criteria_met / criteria_total). Missing criteria
meaningfully penalizes the score — e.g., 85 additive with 6/8 → 63.

##### 3.4.1.5 End date semantics

The `end_date` field shows the last bar of the consolidation window
(the last bar where `Close < peak_high`). If this bar is also the
last bar of available data, the VCP is still ongoing and the field
displays `"current"`. This signals the pattern hasn't resolved.

#### 3.4.2 Bull Flag Pattern

The Bull Flag pattern (also known as a flagpole-flag continuation)
identifies stocks that have rallied sharply (the pole) and are now
pulling back in a tight, orderly range (the flag). A breakout above
the pole high confirms the continuation.

##### 3.4.2.1 Indicators

Same base indicators as VCP. The flag pattern uses:

| Indicator | Window | Purpose |
|-----------|--------|---------|
| SMA_50, SMA_150 | 50/150 | Uptrend confirmation at pole start |
| VMA_10, VMA_50 | 10/50 | Volume drying up during flag |
| RANGE_PCT | 1 | Flag tightness measurement |

##### 3.4.2.2 Detection algorithm

1. **Pole identification** — highest high in the trailing 90 bars.
2. **Pole low** — walks back up to 25 bars from the pole high to find
   the start of the rally (lowest low in that window).
3. **Pole gain filter** — pole gain must be between 15% and 50%.
4. **Uptrend check at pole start** — SMA_50 must be above SMA_150
   (hard filter).
5. **Flag identification** — after the pole high, find the contiguous
   block where Close < pole_high. This is the flag/pullback.
6. **Flag length filter** — flag must be between 3 and 25 bars.
7. **Retracement filter** — flag's lowest low must retrace no more
   than 50% of the pole's height. This ensures the flag is a
   shallow pullback, not a full reversal.

##### 3.4.2.3 Key parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_pole_pct` | 15% | Minimum pole gain required |
| `max_pole_pct` | 50% | Maximum pole gain allowed |
| `max_pole_bars` | 25 | Max bars to search back for pole low |
| `min_flag_bars` | 3 | Minimum flag duration |
| `max_flag_bars` | 25 | Maximum flag duration |
| `max_retracement_pct` | 50% | Maximum flag retracement vs pole height |

##### 3.4.2.4 Metrics

| Metric | Formula | What it measures |
|--------|---------|------------------|
| `pole_pct` | `(pole_high − pole_low) / pole_low` | Rally magnitude |
| `flag_retracement_pct` | `(pole_high − flag_low) / (pole_high − pole_low)` | Pullback depth as fraction of pole |
| `flag_bars` | Count of bars in the flag | Flag duration |
| `flag_tightness_pct` | Mean RANGE_PCT within flag | How tight the flag is |
| `vol_dry` | `VMA_10 < VMA_50` at flag end | Volume drying up during flag |
| `breakout_pct` | `(current_close − pole_high) / pole_high` | Distance from pole high (negative = below) |
| `trend_ok` | SMA_50 > SMA_150 at pole start | Uptrend confirmation |

##### 3.4.2.5 Scoring (max 100)

The additive score is the sum of 7 components, then scaled by
`criteria_met / criteria_total` (7 criteria).

| # | Component | Max | Scoring details |
|---|-----------|-----|-----------------|
| 1 | Pole height | 15 | `15–35%` = 15, `35–50%` = 10, `10–15%` = 5 |
| 2 | Retracement | 20 | `25–40%` = 20, `15–25%` = 15, `40–50%` or `< 15%` = 10 |
| 3 | Flag tightness | 15 | `< 3%` = 15, `< 5%` = 10, else 5 |
| 4 | Volume dry-up | 15 | Binary: `VMA_10 < VMA_50` |
| 5 | Flag duration | 10 | `5–15` bars = 10, `3–4` or `16–20` = 5 |
| 6 | Breakout proximity | 15 | `≥ 0%` = 15, `≥ −2%` = 10, `≥ −5%` = 5 |
| 7 | Trend | 10 | Binary: SMA_50 > SMA_150 at pole start |

Criteria:
`pole 15–35%` | `retrace 25–40%` | `tightness < 5%` | `vol_dry` |
`flag bars 5–15` | `breakout ≥ −2%` | `trend_ok`

Score = additive × (criteria_met / criteria_total). Both VCP and Flag
use a 100-point basis so scores are comparable.

### 3.5 Scanner

Accepts an `InstrumentListProvider`, a `DataProvider`, and a list
of pattern names (`pattern_names: list[str]`). Operates as a
generator — yields results one at a time without buffering:

1. Get instrument list: `provider.get_instruments()`
2. Fetch price data for all instruments: `data_provider.get_history(instruments, period)`
3. For each instrument with data, run each pattern's `detect(df)`
4. Yield one `Result` per pattern per instrument
5. Missing data (None df) yields `Result(error=..., score=None)`
6. Pattern errors (`PatternError`) and unexpected exceptions
   (`Exception`) are caught and yielded as `Result(error=...)`
   instead of crashing the entire scan

### 3.6 CLI

Minimal wrapper. Parses arguments, instantiates providers and pattern,
runs `scanner.scan()`, formats output. See `--help` for available flags.

## 4. Code Structure & Interfaces

```
trade_scanner/
├── cli.py                    # CLI entry, argparse, output formatting
├── scanner.py                # orchestration
├── patterns/
│   ├── __init__.py           # pattern registry
│   ├── base.py               # Pattern ABC
│   ├── vcp.py                # VCP detection
│   └── flag.py               # Bull Flag detection
├── indicators.py             # SMA, ATR, volume MAs  (pure)
├── providers/
│   ├── __init__.py
│   ├── instruments/
│   │   ├── base.py           # InstrumentListProvider ABC
│   │   └── file.py           # reads from text file
│   └── data/
│       ├── base.py           # DataProvider ABC
│       └── yahoo.py          # yfinance implementation
```

### InstrumentListProvider

```python
class InstrumentListProvider(ABC):
    @abstractmethod
    def get_instruments(self) -> list[str]:
        """Return list of instrument symbols to scan."""
```

### DataProvider

```python
class DataProvider(ABC):
    @abstractmethod
    def get_history(
        self, symbols: list[str], period: str = "1y",
        end: str | None = None,
    ) -> dict[str, pd.DataFrame | None]:
        """Returns {symbol: OHLCV DataFrame}. None = no data.
        If end is set, yields data up to that date (for historical backtesting)."""
```

### Pattern

```python
class Pattern(ABC):
    name: str

    @abstractmethod
    def detect(self, df: pd.DataFrame) -> Result | None:
        """Analyze a single instrument's OHLCV data."""
```

### Result type

`Result` is generic over pattern-specific details.

```python
T = TypeVar("T")

@dataclass
class Result(Generic[T]):
    symbol: Instrument
    pattern: str
    score: int
    details: T
    error: str | None = None
```

Each pattern defines its own details dataclass.

`VcpDetails`:

| Field | Type | Description |
|-------|------|-------------|
| `peak_date` | `str \| None` | Date of the peak high |
| `end_date` | `str \| None` | Last bar of consolidation ("current" if ongoing) |
| `decline_pct` | `float \| None` | Peak-to-trough decline % |
| `contraction_ratio` | `float \| None` | ATR_5_end / ATR_5_start |
| `contraction_stages` | `int \| None` | Number of chunks with decreasing ATR_10 |
| `recovery_pct` | `float \| None` | Position within peak-to-trough range |
| `vcp_trend` | `str \| None` | Directional momentum label |
| `current_price` | `float \| None` | Close at latest bar |

`BullFlagDetails`:

| Field | Type | Description |
|-------|------|-------------|
| `pole_date` | `str \| None` | Date of the pole high |
| `pole_pct` | `float \| None` | Pole gain % |
| `flag_retracement_pct` | `float \| None` | Flag retracement as % of pole height |
| `flag_bars` | `int \| None` | Number of bars in the flag |
| `flag_tightness_pct` | `float \| None` | Mean RANGE_PCT within flag |
| `vol_dry` | `bool \| None` | Volume drying up in flag |
| `breakout_pct` | `float \| None` | Distance from pole high % |
| `current_price` | `float \| None` | Close at latest bar |
| `trend_ok` | `bool \| None` | SMA_50 > SMA_150 at pole start |

## 5. Out of scope (for now)

- Real-time / intraday data.
- Relative strength (RS) line computation.
- Web UI or API server.
- Persistent storage of scan results.
