#!/usr/bin/env python3
"""Parser Agent tool — profile CSV/Excel demand data: detect date/qty columns, granularity, stats."""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def detect_granularity(dates):
    if len(dates) < 2:
        return "unknown"
    diffs = dates.sort_values().diff().dropna()
    median_days = diffs.dt.days.median()
    if median_days <= 1:
        return "daily"
    elif median_days <= 8:
        return "weekly"
    elif median_days <= 32:
        return "monthly"
    elif median_days <= 95:
        return "quarterly"
    else:
        return "annual"


def detect_date_col(df):
    for col in df.columns:
        try:
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().sum() / max(len(df), 1) > 0.8:
                return col
        except Exception:
            continue
    return None


def detect_qty_col(df, date_col):
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    keywords = [
        "demand",
        "qty",
        "quantity",
        "sales",
        "volume",
        "units",
        "orders",
        "count",
    ]
    for kw in keywords:
        for col in numeric_cols:
            if kw in col.lower() and col != date_col:
                return col
    for col in numeric_cols:
        if col != date_col:
            return col
    return None


def parse_data(file_path, date_col=None, qty_col=None, output=None):
    path = Path(file_path)
    if not path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    if path.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    all_cols = df.columns.tolist()

    if not date_col:
        date_col = detect_date_col(df)
        if not date_col:
            print(
                f"Error: could not auto-detect date column. "
                f"Available columns: {all_cols}. Use --date-col.",
                file=sys.stderr,
            )
            sys.exit(1)

    if not qty_col:
        qty_col = detect_qty_col(df, date_col)
        if not qty_col:
            print(
                f"Error: could not auto-detect quantity column. "
                f"Available columns: {all_cols}. Use --qty-col.",
                file=sys.stderr,
            )
            sys.exit(1)

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values(date_col)

    granularity = detect_granularity(df[date_col])
    feature_cols = [
        c
        for c in df.columns
        if c not in (date_col, qty_col) and df[c].dtype.kind in ("f", "i", "O")
    ]

    col_stats = {}
    for col in [qty_col] + feature_cols:
        if df[col].dtype.kind in ("f", "i"):
            col_stats[col] = {
                "type": "numeric",
                "min": float(df[col].min()),
                "max": float(df[col].max()),
                "mean": float(df[col].mean()),
                "std": float(df[col].std()),
                "missing": int(df[col].isna().sum()),
            }
        else:
            col_stats[col] = {
                "type": "categorical",
                "n_unique": int(df[col].nunique()),
                "missing": int(df[col].isna().sum()),
                "top_values": df[col].value_counts().head(5).index.tolist(),
            }

    profile = {
        "file_path": str(path.resolve()),
        "date_col": date_col,
        "qty_col": qty_col,
        "feature_cols": feature_cols,
        "n_rows": len(df),
        "date_range": {
            "start": df[date_col].min().isoformat(),
            "end": df[date_col].max().isoformat(),
        },
        "granularity": granularity,
        "column_stats": col_stats,
    }

    out = json.dumps(profile, indent=2)
    if output:
        Path(output).write_text(out)
        print(f"Profile saved to {output}")
    else:
        print(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Profile demand data from CSV/Excel.")
    parser.add_argument("file", help="Path to CSV or Excel file")
    parser.add_argument(
        "--date-col", help="Date column name (auto-detected if omitted)"
    )
    parser.add_argument(
        "--qty-col", help="Quantity/demand column name (auto-detected if omitted)"
    )
    parser.add_argument(
        "--output", help="Save profile JSON to this file (default: stdout)"
    )
    args = parser.parse_args()
    parse_data(args.file, args.date_col, args.qty_col, args.output)
