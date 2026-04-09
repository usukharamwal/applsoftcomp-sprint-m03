#!/usr/bin/env python3
"""Visualizer Agent tool — generate a self-contained HTML report with base64-embedded charts."""

import argparse
import base64
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ── Data loading ─────────────────────────────────────────────────────────────

def load_data(profile):
    p = Path(profile["file_path"])
    if p.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
        df = pd.read_excel(p)
    else:
        df = pd.read_csv(p)
    date_col = profile["date_col"]
    qty_col = profile["qty_col"]
    df[date_col] = pd.to_datetime(df[date_col], infer_datetime_format=True, errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values(date_col)
    df["qty"] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0)
    df["date"] = df[date_col]
    return df[["date", "qty"]]


def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return encoded


# ── Charts ────────────────────────────────────────────────────────────────────

def chart_historical(df, analysis):
    """Line chart with rolling trend overlay and anomaly markers."""
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(df["date"], df["qty"], color="#2196F3", linewidth=1.4, label="Demand", alpha=0.9)

    window = analysis.get("trend", {}).get("rolling_window", 4)
    rolling = df["qty"].rolling(window=window, center=True).mean()
    ax.plot(df["date"], rolling, color="#FF5722", linewidth=2, linestyle="--",
            label=f"{window}-period trend")

    bounds = analysis.get("anomaly_bounds", {})
    anomalies = analysis.get("anomalies", [])
    if bounds and anomalies:
        ax.axhline(bounds.get("upper"), color="#E53935", linestyle=":", alpha=0.55, linewidth=1)
        ax.axhline(bounds.get("lower"), color="#7B1FA2", linestyle=":", alpha=0.55, linewidth=1,
                   label="Anomaly bounds (IQR)")
        for a in anomalies:
            color = "#E53935" if a["direction"] == "spike" else "#7B1FA2"
            ax.axvline(pd.to_datetime(a["date"]), color=color, alpha=0.35, linewidth=1)

    ax.set_title("Historical Demand with Trend", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Demand")
    ax.legend(fontsize=9)
    ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(mdates.AutoDateLocator()))
    fig.autofmt_xdate()
    plt.tight_layout()
    return fig_to_b64(fig)


def chart_forecast(df, forecast_data):
    """Forecast chart with CI ribbon, connected to historical context."""
    fc = forecast_data.get("forecast", [])
    if not fc:
        return None
    fc_df = pd.DataFrame(fc)
    fc_df["date"] = pd.to_datetime(fc_df["date"])

    n_ctx = min(len(df), len(fc) * 2)
    ctx = df.tail(n_ctx)

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(ctx["date"], ctx["qty"], color="#2196F3", linewidth=1.5, label="Historical")
    ax.plot(fc_df["date"], fc_df["value"], color="#FF5722", linewidth=2,
            marker="o", markersize=3, label=f"Forecast (WMA, window={forecast_data.get('window','?')})")
    ax.fill_between(fc_df["date"], fc_df["lower_ci"], fc_df["upper_ci"],
                    alpha=0.18, color="#FF5722", label="95% CI")
    if len(ctx):
        ax.plot([ctx["date"].iloc[-1], fc_df["date"].iloc[0]],
                [ctx["qty"].iloc[-1], fc_df["value"].iloc[0]],
                color="#FF5722", linestyle="--", linewidth=1, alpha=0.5)

    n = forecast_data.get("n_periods", len(fc))
    gran = forecast_data.get("granularity", "period")
    ax.set_title(f"{n}-{gran.capitalize()} Demand Forecast (Weighted Moving Average)",
                 fontsize=14, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Demand")
    ax.legend(fontsize=9)
    ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(mdates.AutoDateLocator()))
    fig.autofmt_xdate()
    plt.tight_layout()
    return fig_to_b64(fig)


def chart_distribution(df):
    """Histogram + box plot side by side."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
    ax1.hist(df["qty"], bins=20, color="#2196F3", edgecolor="white", alpha=0.8)
    ax1.set_title("Demand Distribution", fontsize=13, fontweight="bold")
    ax1.set_xlabel("Demand")
    ax1.set_ylabel("Frequency")

    bp = ax2.boxplot(df["qty"].dropna(), vert=True, patch_artist=True,
                     boxprops=dict(facecolor="#2196F3", alpha=0.6),
                     medianprops=dict(color="#FF5722", linewidth=2))
    ax2.set_title("Demand Box Plot", fontsize=13, fontweight="bold")
    ax2.set_ylabel("Demand")
    ax2.set_xticks([])
    plt.tight_layout()
    return fig_to_b64(fig)


# ── HTML builder ──────────────────────────────────────────────────────────────

def _img(b64):
    return f"<img src='data:image/png;base64,{b64}' alt='chart'/>" if b64 else "<p><em>Chart unavailable.</em></p>"


def build_html(charts, profile, analysis, forecast_data):
    trend = analysis.get("trend", {})
    seasonality = analysis.get("seasonality", {})
    anomalies = analysis.get("anomalies", [])
    a_summary = analysis.get("summary", "")
    f_summary = forecast_data.get("summary", "")

    anom_rows = "".join(
        f"<tr><td>{a['date']}</td><td>{a['qty']:.2f}</td>"
        f"<td class='{a['direction']}'>{a['direction'].upper()}</td></tr>"
        for a in anomalies[:30]
    )
    fc_rows = "".join(
        f"<tr><td>{f['date']}</td><td>{f['value']:.2f}</td>"
        f"<td>{f['lower_ci']:.2f}</td><td>{f['upper_ci']:.2f}</td></tr>"
        for f in forecast_data.get("forecast", [])
    )
    feature_html = (
        "<p><b>Feature columns:</b> " + ", ".join(profile.get("feature_cols", [])) + "</p>"
        if profile.get("feature_cols")
        else ""
    )
    anomaly_section = (
        f"<h2>Anomalies ({len(anomalies)} detected)</h2>"
        f"<div class='card'><table><thead><tr><th>Date</th><th>Value</th><th>Type</th></tr></thead>"
        f"<tbody>{anom_rows}</tbody></table></div>"
        if anomalies
        else ""
    )

    trend_dir = trend.get("direction", "N/A").capitalize()
    trend_pct = trend.get("overall_pct_change", 0)
    seas_text = (
        "Detected — " + seasonality.get("interpretation", "")
        if seasonality.get("detected")
        else "Not detected (" + seasonality.get("reason", seasonality.get("error", "no clear pattern")) + ")"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Demand Pattern Analysis Report</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f7fa;margin:0;padding:24px;color:#333}}
  h1{{color:#1565C0;border-bottom:3px solid #1565C0;padding-bottom:8px;margin-bottom:8px}}
  h2{{color:#1976D2;margin-top:32px;margin-bottom:8px}}
  h3{{color:#424242;margin-top:20px}}
  .card{{background:white;border-radius:8px;padding:20px;margin:12px 0;box-shadow:0 2px 6px rgba(0,0,0,.08)}}
  .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:12px 0}}
  .stat{{background:#E3F2FD;border-radius:8px;padding:16px;text-align:center}}
  .stat-value{{font-size:1.9em;font-weight:bold;color:#1565C0}}
  .stat-label{{font-size:.82em;color:#666;margin-top:4px}}
  img{{max-width:100%;border-radius:6px;display:block}}
  table{{width:100%;border-collapse:collapse;font-size:.9em}}
  th{{background:#1565C0;color:white;padding:8px 12px;text-align:left}}
  td{{padding:7px 12px;border-bottom:1px solid #eee}}
  tr:hover td{{background:#f0f7ff}}
  .spike{{color:#C62828;font-weight:bold}}
  .dip{{color:#6A1B9A;font-weight:bold}}
  .box{{background:#FFF8E1;border-left:4px solid #FFC107;padding:12px 16px;border-radius:4px;margin:8px 0}}
  footer{{text-align:center;color:#aaa;font-size:.78em;margin-top:40px}}
</style>
</head>
<body>
<h1>Demand Pattern Analysis Report</h1>
<div class="box"><b>Analysis:</b> {a_summary}</div>
<div class="box"><b>Forecast:</b> {f_summary}</div>

<h2>Data Profile</h2>
<div class="card">
  <div class="grid">
    <div class="stat"><div class="stat-value">{profile.get('n_rows','?')}</div><div class="stat-label">Observations</div></div>
    <div class="stat"><div class="stat-value">{profile.get('granularity','?').capitalize()}</div><div class="stat-label">Granularity</div></div>
    <div class="stat"><div class="stat-value">{len(anomalies)}</div><div class="stat-label">Anomalies</div></div>
  </div>
  <p><b>Date range:</b> {profile.get('date_range',{}).get('start','?')} → {profile.get('date_range',{}).get('end','?')}</p>
  <p><b>Date column:</b> {profile.get('date_col','?')} &nbsp;|&nbsp; <b>Quantity column:</b> {profile.get('qty_col','?')}</p>
  {feature_html}
</div>

<h2>Trend &amp; Seasonality</h2>
<div class="card">
  <p><b>Trend:</b> {trend_dir} ({trend_pct:+.1f}% overall change)</p>
  <p><b>Seasonality:</b> {seas_text}</p>
</div>

<h2>Historical Demand</h2>
<div class="card">{_img(charts.get('historical'))}</div>

<h2>Distribution</h2>
<div class="card">{_img(charts.get('distribution'))}</div>

<h2>Forecast</h2>
<div class="card">
  {_img(charts.get('forecast'))}
  <h3>Forecast Table</h3>
  <table><thead><tr><th>Date</th><th>Forecast</th><th>Lower 95% CI</th><th>Upper 95% CI</th></tr></thead>
  <tbody>{fc_rows}</tbody></table>
</div>

{anomaly_section}

<footer>Generated by Demand Pattern Analyzer &middot; Powered by Claude</footer>
</body>
</html>"""


# ── Entry point ───────────────────────────────────────────────────────────────

def visualize(profile_path, analysis_path, forecast_path, output="report.html"):
    profile = json.loads(Path(profile_path).read_text())
    analysis = json.loads(Path(analysis_path).read_text())
    forecast_data = json.loads(Path(forecast_path).read_text())
    df = load_data(profile)

    charts = {
        "historical": chart_historical(df, analysis),
        "distribution": chart_distribution(df),
        "forecast": chart_forecast(df, forecast_data),
    }

    html = build_html(charts, profile, analysis, forecast_data)
    Path(output).write_text(html, encoding="utf-8")
    print(f"Report saved to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate HTML demand analysis report.")
    parser.add_argument("--profile", required=True, help="Path to data_profile.json")
    parser.add_argument("--analysis", required=True, help="Path to analysis_results.json")
    parser.add_argument("--forecast", required=True, help="Path to forecast_results.json")
    parser.add_argument("--output", default="report.html", help="Output HTML file (default: report.html)")
    args = parser.parse_args()
    visualize(args.profile, args.analysis, args.forecast, args.output)
