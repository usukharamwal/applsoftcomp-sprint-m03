#!/usr/bin/env python3
"""Forecaster Agent tool — weighted moving average forecast with 95% confidence intervals."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def load_series(profile):
    path = profile["file_path"]
    date_col = profile["date_col"]
    qty_col = profile["qty_col"]
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
        df = pd.read_excel(p)
    else:
        df = pd.read_csv(p)
    df[date_col] = pd.to_datetime(df[date_col], infer_datetime_format=True, errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values(date_col)
    df["qty"] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0)
    df["date"] = df[date_col]
    return df[["date", "qty"]]


def infer_freq(granularity):
    return {"daily": "D", "weekly": "W", "monthly": "MS", "quarterly": "QS", "annual": "YS"}.get(
        granularity, "W"
    )


def forecast(profile_path, analysis_path=None, n_periods=8, output=None):
    profile = json.loads(Path(profile_path).read_text())
    df = load_series(profile)
    granularity = profile.get("granularity", "weekly")

    qty = df["qty"].values.astype(float)

    # Weighted moving average: linearly increasing weights over last `window` periods
    window = min(12, max(3, len(qty) // 2))
    weights = np.arange(1, window + 1, dtype=float)
    weights /= weights.sum()

    # Historical std from the trailing window for confidence intervals
    hist_std = float(np.std(qty[-window:]))

    # Rolling WMA forecast
    extended = list(qty)
    forecast_values = []
    for _ in range(n_periods):
        tail = np.array(extended[-window:])
        if len(tail) < window:
            tail = np.pad(tail, (window - len(tail), 0), mode="edge")
        wma = float(np.dot(weights, tail))
        extended.append(wma)
        forecast_values.append(wma)

    # Generate forecast dates
    last_date = df["date"].iloc[-1]
    freq = infer_freq(granularity)
    try:
        forecast_dates = pd.date_range(start=last_date, periods=n_periods + 1, freq=freq)[1:]
    except Exception:
        forecast_dates = [last_date + pd.Timedelta(weeks=i + 1) for i in range(n_periods)]

    z = 1.96  # 95% confidence
    results = {
        "method": "weighted_moving_average",
        "window": int(window),
        "n_periods": int(n_periods),
        "granularity": granularity,
        "forecast": [
            {
                "date": str(d.date()) if hasattr(d, "date") else str(d),
                "value": round(v, 4),
                "lower_ci": round(v - z * hist_std, 4),
                "upper_ci": round(v + z * hist_std, 4),
            }
            for d, v in zip(forecast_dates, forecast_values)
        ],
        "summary": (
            f"{n_periods}-period WMA forecast (window={window}, granularity={granularity}). "
            f"Last observed: {float(qty[-1]):.2f}. "
            f"First forecast: {forecast_values[0]:.2f} "
            f"[95% CI: {forecast_values[0]-z*hist_std:.2f}, {forecast_values[0]+z*hist_std:.2f}]. "
            f"Last forecast: {forecast_values[-1]:.2f}."
        ),
    }

    out = json.dumps(results, indent=2)
    if output:
        Path(output).write_text(out)
        print(f"Forecast saved to {output}")
    else:
        print(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forecast demand using weighted moving average.")
    parser.add_argument("--profile", required=True, help="Path to data_profile.json")
    parser.add_argument("--analysis", help="Path to analysis_results.json (optional context)")
    parser.add_argument(
        "--weeks", type=int, default=8, help="Forecast horizon in periods (default: 8)"
    )
    parser.add_argument("--output", help="Save forecast JSON to this file (default: stdout)")
    args = parser.parse_args()
    forecast(args.profile, args.analysis, args.weeks, args.output)
