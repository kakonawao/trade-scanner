import argparse
import csv
import json
import sys
from collections import OrderedDict

from tabulate import tabulate

from .patterns import PATTERNS
from .providers.instruments import FileProvider
from .providers.prices import PRICES_PROVIDERS
from .scanner import scan


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan financial instruments for technical patterns"
    )
    parser.add_argument(
        "--instruments", "-i",
        required=True,
        help="Instrument list file path",
    )
    parser.add_argument(
        "--pattern", "-p",
        default=None,
        nargs="+",
        choices=list(PATTERNS) + ["all"],
        help="Pattern(s) to scan for (default: all)",
    )
    parser.add_argument(
        "--prices-provider",
        default="yahoo",
        choices=list(PRICES_PROVIDERS),
        help="Price data provider (default: yahoo)",
    )
    parser.add_argument(
        "--min-score", "-m",
        type=int,
        default=50,
        help="Minimum score to report (default: 50)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed per-pattern tables",
    )
    parser.add_argument(
        "--output", "-o",
        default="table",
        choices=["table", "csv", "json"],
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--period",
        default="1y",
        help="Data period (default: 1y)",
    )
    parser.add_argument(
        "--end-date", "-e",
        default=None,
        help="End date for historical backtesting (YYYY-MM-DD)",
    )
    return parser


_PATTERN_DISPLAY: dict[str, tuple[list[str], dict[str, str], set[str]]] = {
    "vcp": (
        ["peak_date", "peak_price", "decline_pct", "contraction_ratio", "recovery_pct", "current_price", "vcp_trend"],
        {"peak_date": "peak date", "decline_pct": "decline", "contraction_ratio": "contraction",
         "recovery_pct": "recovery", "peak_price": "peak", "current_price": "price", "vcp_trend": "trend"},
        {"decline_pct", "recovery_pct"},
    ),
    "flag": (
        ["pole_date", "pole_pct", "flag_retracement_pct", "flag_bars", "breakout_pct", "current_price"],
        {"pole_date": "pole date", "pole_pct": "pole gain", "flag_retracement_pct": "retrace",
         "flag_bars": "flag bars", "breakout_pct": "breakout", "current_price": "price"},
        {"pole_pct", "flag_retracement_pct", "breakout_pct"},
    ),
}


def _fields_for(pattern: str) -> tuple[list[str], dict[str, str], set[str]]:
    return _PATTERN_DISPLAY.get(pattern, ([], {}, set()))


def _extract_rows(results) -> list[dict]:
    rows = []
    for r in results:
        row = {
            "symbol": str(r.symbol),
            "pattern": r.pattern,
        }
        if r.details is not None:
            met = getattr(r.details, "criteria_met", None)
            total = getattr(r.details, "criteria_total", None)
            if met is not None and total is not None:
                row["criteria"] = f"{met}/{total}"
        row["score"] = r.score
        if r.error:
            row["error"] = r.error
        detail_fields, field_labels, _pct = _fields_for(r.pattern)
        for k in detail_fields:
            if r.details is not None:
                v = getattr(r.details, k, None)
            else:
                v = None
            row[field_labels.get(k, k)] = v
        rows.append(row)
    return rows


def _fmt_pct(rows: list[dict]) -> list[dict]:
    pct_keys = set()
    for r in rows:
        if r.get("pattern") in _PATTERN_DISPLAY:
            _, _, pct_set = _PATTERN_DISPLAY[r["pattern"]]
            pct_keys |= pct_set
    return [
        {k: f"{v:.1f}%" if k in pct_keys else v for k, v in row.items()}
        for row in rows
    ]


def _group_results(results) -> OrderedDict:
    groups: OrderedDict[str, list] = OrderedDict()
    for r in results:
        sym = str(r.symbol)
        if sym not in groups:
            groups[sym] = []
        groups[sym].append(r)
    return groups


def _build_summary_row(symbol: str, group: list, min_score: int, pattern_names: list[str]) -> dict:
    by_pattern: dict[str, str] = {}
    for r in group:
        if r.error is not None:
            continue
        val = str(r.score) if r.score is not None else "—"
        if r.details is not None:
            met = getattr(r.details, "criteria_met", None)
            total = getattr(r.details, "criteria_total", None)
            if met is not None and total is not None:
                val = f"{val} ({met}/{total})"
        by_pattern[r.pattern] = val
    price = None
    for r in group:
        if r.details is not None:
            price = getattr(r.details, "current_price", None) or price
    row = {"symbol": symbol}
    for pat in pattern_names:
        row[pat] = by_pattern.get(pat, "—")
    row["price"] = price
    return row


def _output_table_grouped(groups: OrderedDict, min_score: int, pattern_names: list[str]) -> None:
    summary_rows = [_build_summary_row(sym, grp, min_score, pattern_names) for sym, grp in groups.items()]
    print(tabulate(summary_rows, headers="keys", floatfmt=".2f", numalign="left"))


def _output_table_flat(rows: list[dict]) -> None:
    print(tabulate(_fmt_pct(rows), headers="keys", floatfmt=".2f", numalign="left"))


def _output_csv(rows: list[dict]) -> None:
    if not rows:
        return
    out = _fmt_pct(rows)
    writer = csv.DictWriter(sys.stdout, fieldnames=out[0].keys())
    writer.writeheader()
    writer.writerows(out)


def _output_json(rows: list[dict]) -> None:
    print(json.dumps(rows, indent=2))


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()

    instrument_provider = FileProvider(args.instruments)
    prices_cls = PRICES_PROVIDERS[args.prices_provider]
    prices_provider = prices_cls()

    if args.pattern is None or "all" in args.pattern:
        pattern_names = list(PATTERNS)
    else:
        pattern_names = args.pattern

    results = scan(
        instrument_provider=instrument_provider,
        data_provider=prices_provider,
        pattern_names=pattern_names,
        period=args.period,
        end_date=args.end_date,
    )

    errors = []
    valid = []
    for r in results:
        if r.error is not None:
            errors.append(r)
        elif r.score is not None and r.score >= args.min_score:
            valid.append(r)

    groups: OrderedDict[str, list] = OrderedDict()
    for r in valid:
        sym = str(r.symbol)
        if sym not in groups:
            groups[sym] = []
        groups[sym].append(r)

    groups = OrderedDict(
        sorted(groups.items(), key=lambda kv: max(r.score for r in kv[1] if r.score is not None), reverse=True)
    )

    if args.output == "table":
        if args.verbose:
            flat = [r for group in groups.values() for r in group]
            pat_results: dict[str, list] = {}
            for r in flat:
                pat_results.setdefault(r.pattern, []).append(r)
            first_pat = True
            for pat in pattern_names:
                if pat not in pat_results:
                    continue
                results = sorted(pat_results[pat], key=lambda r: r.score if r.score is not None else -1, reverse=True)
                if not first_pat:
                    print()
                first_pat = False
                print(pat)
                rows = _extract_rows(results)
                for r in rows:
                    r.pop("pattern", None)
                print(tabulate(_fmt_pct(rows), headers="keys", floatfmt=".2f", numalign="left"))
        else:
            _output_table_grouped(groups, args.min_score, pattern_names)

        if errors:
            print()
            print("errors")
            err_rows = [{"symbol": str(r.symbol), "pattern": r.pattern, "error": r.error} for r in errors]
            print(tabulate(err_rows, headers="keys", floatfmt=".2f", numalign="left"))
    else:
        flat = valid + errors
        rows = _extract_rows(flat)
        if args.output == "csv":
            _output_csv(rows)
        elif args.output == "json":
            _output_json(rows)
