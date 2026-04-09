# Demand Pattern Analyzer

A multi-agent skill built on top of the OpenCode agent framework that analyzes demand data from CSV/Excel files, detects patterns, forecasts future demand, and produces an interactive HTML report — all through a natural language chat interface.

---

## What is the Demand Pattern Analyzer?

The Demand Pattern Analyzer is a conversational analytics skill that takes raw demand/sales data and automatically:

- **Profiles** the dataset (columns, date range, granularity, missing values)
- **Detects** trends (increasing/decreasing), seasonal patterns, and anomalies (spikes and dips)
- **Forecasts** 8-12 periods ahead using Weighted Moving Average with 95% confidence intervals
- **Generates** a self-contained HTML report with embedded charts — no internet connection needed to view it

It is designed for supply chain analysts, operations managers, or students who want quick, explainable demand insights without writing code.

---

## Project Structure

    .agents/skills/demand-analyzer/
    ├── SKILL.md                    # Agent orchestration instructions (read by OpenCode)
    ├── samples/
    │   ├── demand_sample.csv       # Sample weekly demand data (52 weeks)
    │   └── your_file.csv           # Upload your own demand file here
    └── tools/
        ├── parse_data.py           # Sub-Agent 1 - Parser Agent
        ├── analyze_demand.py       # Sub-Agent 2 - Analyzer Agent
        ├── forecast_demand.py      # Sub-Agent 3 - Forecaster Agent
        └── visualize_demand.py     # Sub-Agent 4 - Visualizer Agent

---

## The 4 Sub-Agents

### Sub-Agent 1 - `parse_data.py` (Parser Agent)
Reads the CSV or Excel file and profiles it automatically.

- Auto-detects the date column and demand/quantity column
- Identifies extra feature columns (price, promotions, region, etc.)
- Detects data granularity (daily / weekly / monthly / quarterly)
- Computes basic statistics: min, max, mean, std, missing values
- **Output**: `data_profile.json`

### Sub-Agent 2 - `analyze_demand.py` (Analyzer Agent)
Analyzes the demand series for patterns using simple, explainable methods.

- **Trend**: Rolling mean + linear slope (increasing / decreasing / flat, % overall change)
- **Seasonality**: STL decomposition (seasonal strength score, peak and trough offsets)
- **Anomalies**: IQR method (flags spikes and dips beyond 1.5x interquartile range)
- **Output**: `analysis_results.json`

### Sub-Agent 3 - `forecast_demand.py` (Forecaster Agent)
Produces a forward-looking demand forecast.

- Method: **Weighted Moving Average** (linearly increasing weights over last N periods)
- Horizon: 8-12 periods (configurable)
- Confidence intervals: 95% CI based on historical standard deviation
- **Output**: `forecast_results.json`

### Sub-Agent 4 - `visualize_demand.py` (Visualizer Agent)
Generates a fully self-contained HTML report with embedded charts.

- **Historical Demand**: Line chart with trend overlay and anomaly markers
- **Distribution**: Histogram + box plot side by side
- **Forecast**: Line chart with CI ribbon connected to historical data
- **Forecast Table**: Tabular view of all forecast periods with confidence bounds
- **Output**: `report.html`: open this in your browser

---

## Output Files (created in project root)

| File | Description |
|------|-------------|
| `data_profile.json` | Column mapping, date range, granularity, statistics |
| `analysis_results.json` | Trend direction, seasonality strength, anomaly list |
| `forecast_results.json` | Forecast values with 95% confidence intervals |
| `report.html` | **Open this in your browser** - full visual report |

---

## Using Your Own Data

Upload your CSV or Excel file to:

    .agents/skills/demand-analyzer/samples/your_file.csv

Your file should have at minimum:

- A **date column** (any standard date format — auto-detected)
- A **demand / quantity column** (named anything like `demand`, `qty`, `sales`, `units`, `orders`)

Optional extra columns (price, promotion, region, etc.) are automatically detected and profiled.

---

## How to Run — GitHub Codespace (Recommended)

> **Note:** OpenCode may not work on local Windows machines due to configuration limitations. GitHub Codespace is the recommended environment to run this project.

### Step 1: Open in Codespace

### Step 2: Open OpenCode
In the VS Code terminal inside Codespace, open the command palette and select **Open OpenCode**. The chat UI will appear.

Connect your provider: `/connect` --> **Ollama Cloud** --> enter your API key --> select **Qwen 3.5 Cloud** model.

### Step 3: Ask questions in chat

**Run the full analysis pipeline on the sample file:**

    I have a demand analyzer skill in this project. Please run the demand
    analysis pipeline on the sample demand file.

**Or with your own file:**

    Run the demand-analyzer skill on your_file.csv (or .xlsx)

**Follow-up questions to explore the results:**

    1. What does the seasonal pattern suggest about restocking timing?
    2. Forecast 12 weeks ahead and regenerate the report.
    3. Are the anomalies detected a concern? What could cause them?

### Step 4: View the report
Once the pipeline completes, open `report.html` from the VS Code file explorer → right-click → **Open with Live Server** (or download and open in your browser).

The report includes:

- Historical demand chart with trend line and anomaly markers
- Distribution histogram and box plot
- Forecast chart with 95% confidence interval ribbon
- Forecast table with exact values per period

---

## Dependencies

Managed via `uv` (defined in `pyproject.toml`):

| Package | Purpose |
|---------|---------|
| `pandas` | Data loading and manipulation |
| `matplotlib` | Chart generation |
| `seaborn` | Chart styling |
| `statsmodels` | STL decomposition for seasonality detection |
| `openpyxl` / `xlrd` | Excel file reading support |
| `pymupdf` | PDF support (existing project dependency) |

