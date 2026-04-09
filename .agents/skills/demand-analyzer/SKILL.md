---
name: demand-analyzer
description: Analyze demand patterns from CSV/Excel data — parse columns, detect trends/seasonality/anomalies.
---

Shared files (written to working directory): `data_profile.json` (column map + stats from Parser), `analysis_results.json` (trend/seasonality/anomalies from Analyzer).

## Lead Agent (pipeline orchestrator - do not read/write data files directly)

1. Accept from user: path to CSV/Excel file and optional forecast horizon `--weeks` (default 8).
2. Spawn Parser Agent. Wait for completion.
3. Spawn Analyzer Agent. Wait for completion.
4. Read the `summary` field from `analysis_results.json`Report key findings to user.

## Sub-Agents (all spawned via Task tool, `general` / `mode: subagent`)

**Parser Agent** (once, first):
1. Run: `uv run python3 .agents/skills/demand-analyzer/tools/parse_data.py <file_path> --output data_profile.json`
   - Replace `<file_path>` with the actual path provided by user.
2. If the tool exits with an error about column detection, re-run with `--date-col <name>` and `--qty-col <name>` based on any column names visible in the error output.
3. Confirm: "Parser done - `data_profile.json` written."

**Analyzer Agent** (once, after Parser):
1. Run: `uv run python3 .agents/skills/demand-analyzer/tools/analyze_demand.py --profile data_profile.json --output analysis_results.json`
2. Confirm: "Analyzer done - `analysis_results.json` written."

**Forecaster Agent** (once, after Analyzer):
1. Run: `uv run python3 .agents/skills/demand-analyzer/tools/forecast_demand.py --profile data_profile.json --analysis analysis_results.json --weeks <N> --output forecast_results.json`
   - Replace `<N>` with user-specified weeks (default 8).
2. Confirm: "Forecaster done - `forecast_results.json` written." 

**Visualizer Agent** (once, after Forecaster):
1. Run: `uv run python3 .agents/skills/demand-analyzer/tools/visualize_demand.py --profile data_profile.json --analysis analysis_results.json --forecast forecast_results.json --output report.html`
2. Confirm: "Visualizer done - `report.html` written."

## Stop Conditions
- All four complete and analysis report, report.html generated -> pipeline succeeded
- Any tool exits with a non-zero error -> retry once with corrected arguments; if it fails again, escalate to user with the exact error message
- User cancels
