#!/usr/bin/env python3
"""Analyzer Agent tool — detect trend (rolling mean), seasonality (STL), and anomalies (IQR)."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def load_data(profile):
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


def seasonal_period(granularity):
    return {"daily": 7, "weekly": 52, "monthly": 12, "quarterly": 4, "annual": 2}.get(
        granularity, 7
    )


def analyze(profile_path, output=None):
    profile = json.loads(Path(profile_path).read_text())
    df = load_data(profile)
    granularity = profile.get("granularity", "weekly")
    period = seasonal_period(granularity)
    qty = df["qty"].values

    results = {
        "granularity": granularity,
        "n_observations": len(df),
        "trend": {},
        "seasonality": {},
        "anomalies": [],
        "anomaly_bounds": {},
    }

    # --- Trend: rolling mean + linear slope ---
    window = min(period, max(2, len(df) // 2))
    rolling = pd.Series(qty).rolling(window=window, center=True).mean().dropna()
    if len(rolling) >= 2:
        x = np.arange(len(rolling))
        slope = float(np.polyfit(x, rolling.values, 1)[0])
        pct_change = float(
            (rolling.iloc[-1] - rolling.iloc[0]) / (abs(rolling.iloc[0]) + 1e-9) * 100
        )
        results["trend"] = {
            "direction": "increasing" if slope > 0.001 else "decreasing" if slope < -0.001 else "flat",
            "slope_per_period": round(slope, 4),
            "overall_pct_change": round(pct_change, 2),
            "rolling_window": int(window),
        }

    # --- Seasonality: STL decomposition ---
    min_obs_for_stl = 2 * period
    if len(df) >= min_obs_for_stl:
        try:
            from statsmodels.tsa.seasonal import STL

            series = pd.Series(qty, index=pd.RangeIndex(len(qty)))
            stl = STL(series, period=period, robust=True)
            res = stl.fit()
            seasonal_var = float(np.var(res.seasonal))
            residual_var = float(np.var(res.resid))
            strength = seasonal_var / (seasonal_var + residual_var + 1e-9)
            avg_seasonal = res.seasonal[:period].tolist()
            peak_idx = int(np.argmax(avg_seasonal))
            trough_idx = int(np.argmin(avg_seasonal))
            results["seasonality"] = {
                "detected": strength > 0.1,
                "strength": round(float(strength), 4),
                "period": period,
                "peak_period_offset": peak_idx,
                "trough_period_offset": trough_idx,
                "interpretation": (
                    f"Seasonal strength {strength:.2f} — "
                    f"{'strong' if strength > 0.4 else 'moderate' if strength > 0.1 else 'weak'} seasonality"
                ),
            }
        except Exception as e:
            results["seasonality"] = {"detected": False, "error": str(e)}
    else:
        results["seasonality"] = {
            "detected": False,
            "reason": f"Need at least {min_obs_for_stl} observations for STL; have {len(df)}.",
        }

    # --- Anomalies: IQR method ---
    q1 = float(np.percentile(qty, 25))
    q3 = float(np.percentile(qty, 75))
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    mask = (df["qty"] < lower) | (df["qty"] > upper)
    results["anomalies"] = [
        {
            "date": row.date.isoformat(),
            "qty": float(row.qty),
            "direction": "spike" if row.qty > upper else "dip",
        }
        for row in df[mask].itertuples()
    ]
    results["anomaly_bounds"] = {
        "lower": round(lower, 4),
        "upper": round(upper, 4),
        "iqr": round(iqr, 4),
    }

    results["summary"] = (
        f"Data spans {len(df)} {granularity} observations. "
        f"Trend is {results['trend'].get('direction', 'unknown')} "
        f"({results['trend'].get('overall_pct_change', 0):+.1f}% overall). "
        f"Seasonality: {'detected — ' + results['seasonality'].get('interpretation', '') if results['seasonality'].get('detected') else 'not detected'}. "
        f"{len(results['anomalies'])} anomalies found (IQR method)."
    )

    out = json.dumps(results, indent=2)
    if output:
        Path(output).write_text(out)
        print(f"Analysis saved to {output}")
    else:
        print(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze demand patterns.")
    parser.add_argument("--profile", required=True, help="Path to data_profile.json")
    parser.add_argument("--output", help="Save analysis JSON to this file (default: stdout)")
    args = parser.parse_args()
    analyze(args.profile, args.output)
