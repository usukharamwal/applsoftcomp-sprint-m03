#!/usr/bin/env python3
"""Demand Pattern Analyzer — terminal chat interface powered by Ollama.

Usage:
    uv run python3 .agents/skills/demand-analyzer/chat.py
    uv run python3 .agents/skills/demand-analyzer/chat.py --model llama3.2
    uv run python3 .agents/skills/demand-analyzer/chat.py --model mistral --url http://localhost:11434
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Missing dependency: run `uv add requests` then try again.")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).parent
TOOLS_DIR = SKILL_DIR / "tools"

SYSTEM_PROMPT = """\
You are a Demand Pattern Analyzer assistant embedded in a supply chain analytics tool.
You help users understand demand data — trends, seasonality, anomalies, and forecasts.

Capabilities (triggered automatically by keywords):
  • Analyze a CSV/Excel file  → detects trend, seasonality, anomalies
  • Forecast future demand     → weighted moving average, 8–12 periods, 95% CI
  • Generate an HTML report    → charts + tables saved to report.html

When analysis results are shown to you in [brackets], explain them clearly.
Focus on actionable supply chain insights: when to stock up, when demand dips, what spikes suggest.
Keep answers concise — 3–5 sentences max unless the user asks for more detail.\
"""

# ── Terminal colors ─────────────────────────────────────────────────────────────

def _c(code):
    return f"\033[{code}m" if sys.stdout.isatty() else ""

CYAN   = _c("96")
GREEN  = _c("92")
YELLOW = _c("93")
RED    = _c("91")
BOLD   = _c("1")
DIM    = _c("2")
RESET  = _c("0")

# ── Session state ───────────────────────────────────────────────────────────────

state = {
    "file_path":    None,   # last loaded file
    "has_profile":  False,
    "has_analysis": False,
    "has_forecast": False,
    "has_report":   False,
}

# ── Ollama helpers ──────────────────────────────────────────────────────────────

def ollama_chat(history, model, base_url):
    """Stream a response from Ollama; yield text tokens."""
    url = f"{base_url}/api/chat"
    payload = {"model": model, "messages": history, "stream": True}
    try:
        resp = requests.post(url, json=payload, stream=True, timeout=120)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        yield f"{RED}Cannot connect to Ollama at {base_url}. Is `ollama serve` running?{RESET}"
        return
    except requests.exceptions.HTTPError as e:
        yield f"{RED}Ollama error {e.response.status_code}: {e.response.text.strip()}{RESET}"
        return

    for line in resp.iter_lines():
        if not line:
            continue
        try:
            data = json.loads(line)
            token = data.get("message", {}).get("content", "")
            if token:
                yield token
        except json.JSONDecodeError:
            continue

# ── Tool runners ────────────────────────────────────────────────────────────────

def run(cmd):
    """Run a subprocess; return (success: bool, output: str)."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    combined = (result.stdout + result.stderr).strip()
    return result.returncode == 0, combined


def run_parser(file_path):
    print(f"\n{YELLOW}[Parser]{RESET} Reading {file_path} ...")
    ok, out = run(["uv", "run", "python3", str(TOOLS_DIR / "parse_data.py"),
                   file_path, "--output", "data_profile.json"])
    if ok:
        state["has_profile"] = True
    return ok, out


def run_analyzer():
    print(f"{YELLOW}[Analyzer]{RESET} Detecting trend, seasonality, anomalies ...")
    ok, out = run(["uv", "run", "python3", str(TOOLS_DIR / "analyze_demand.py"),
                   "--profile", "data_profile.json", "--output", "analysis_results.json"])
    if ok:
        state["has_analysis"] = True
    return ok, out


def run_forecaster(weeks):
    print(f"{YELLOW}[Forecaster]{RESET} Forecasting {weeks} periods ...")
    ok, out = run(["uv", "run", "python3", str(TOOLS_DIR / "forecast_demand.py"),
                   "--profile", "data_profile.json",
                   "--analysis", "analysis_results.json",
                   "--weeks", str(weeks),
                   "--output", "forecast_results.json"])
    if ok:
        state["has_forecast"] = True
    return ok, out


def run_visualizer():
    print(f"{YELLOW}[Visualizer]{RESET} Building report.html ...")
    ok, out = run(["uv", "run", "python3", str(TOOLS_DIR / "visualize_demand.py"),
                   "--profile", "data_profile.json",
                   "--analysis", "analysis_results.json",
                   "--forecast", "forecast_results.json",
                   "--output", "report.html"])
    if ok:
        state["has_report"] = True
    return ok, out

# ── Result readers ──────────────────────────────────────────────────────────────

def read_summary(json_path):
    try:
        return json.loads(Path(json_path).read_text()).get("summary", "")
    except Exception:
        return ""

# ── Intent detection ────────────────────────────────────────────────────────────

FILE_SUFFIXES = {".csv", ".xlsx", ".xls", ".xlsm"}

def find_file(text):
    for word in text.split():
        word = word.strip("'\",()")
        p = Path(word)
        if p.suffix.lower() in FILE_SUFFIXES and p.exists():
            return str(p)
    return None


def extract_weeks(text):
    m = re.search(r"\b(\d+)\s*(?:weeks?|periods?|steps?)\b", text, re.IGNORECASE)
    if m:
        return max(2, min(52, int(m.group(1))))
    m = re.search(r"\bforecast\s+(\d+)\b", text, re.IGNORECASE)
    if m:
        return max(2, min(52, int(m.group(1))))
    return 8


def detect_intent(text):
    """Return (intent, extra).  Intents: analyze | forecast | report | chat."""
    lower = text.lower()

    file_path = find_file(text)
    if file_path:
        return "analyze", file_path

    analyze_kw = {"analyze", "analysis", "load", "upload", "import", "process", "examine"}
    if any(kw in lower for kw in analyze_kw):
        return "analyze", state["file_path"]

    forecast_kw = {"forecast", "predict", "future", "next week", "next month", "predict"}
    if any(kw in lower for kw in forecast_kw):
        return "forecast", extract_weeks(text)

    report_kw = {"report", "chart", "visual", "html", "graph", "plot", "show result"}
    if any(kw in lower for kw in report_kw):
        return "report", None

    return "chat", None

# ── Pipeline ────────────────────────────────────────────────────────────────────

def full_pipeline(file_path, weeks=8):
    """Run all four tools; return (tool_context_str, success)."""
    bits = []

    ok, out = run_parser(file_path)
    if not ok:
        return f"Parser failed:\n{out}", False
    bits.append(read_summary("data_profile.json") or "Data parsed.")

    ok, out = run_analyzer()
    if not ok:
        return f"Analyzer failed:\n{out}", False
    bits.append(read_summary("analysis_results.json"))

    ok, out = run_forecaster(weeks)
    if not ok:
        return f"Forecaster failed:\n{out}", False
    bits.append(read_summary("forecast_results.json"))

    ok, out = run_visualizer()
    if not ok:
        return f"Visualizer failed:\n{out}", False
    bits.append("HTML report saved → report.html (open in browser).")

    return "\n".join(filter(None, bits)), True

# ── Banner ──────────────────────────────────────────────────────────────────────

def banner(model, base_url):
    width = 48
    title  = "Demand Pattern Analyzer"
    sub    = f"Model: {model}"
    server = f"Server: {base_url}"
    hint   = "Type 'help' for tips  |  'quit' to exit"
    sep = "─" * width
    print(f"\n{BOLD}{CYAN}┌{sep}┐{RESET}")
    print(f"{BOLD}{CYAN}│{RESET}  {BOLD}{title:<{width-2}}{RESET}{BOLD}{CYAN}│{RESET}")
    print(f"{BOLD}{CYAN}│{RESET}  {DIM}{sub:<{width-2}}{RESET}{BOLD}{CYAN}│{RESET}")
    print(f"{BOLD}{CYAN}│{RESET}  {DIM}{server:<{width-2}}{RESET}{BOLD}{CYAN}│{RESET}")
    print(f"{BOLD}{CYAN}│{RESET}  {DIM}{hint:<{width-2}}{RESET}{BOLD}{CYAN}│{RESET}")
    print(f"{BOLD}{CYAN}└{sep}┘{RESET}\n")


HELP_TEXT = f"""\
{BOLD}Tips:{RESET}
  • Drop a file path to start full analysis:
      {DIM}my_data.csv{RESET}
      {DIM}analyze sales/weekly.xlsx{RESET}
  • Re-forecast with a different horizon:
      {DIM}forecast 12 weeks{RESET}
  • Regenerate the HTML report:
      {DIM}show report{RESET}
  • Ask anything about demand / supply chain:
      {DIM}what does the seasonal pattern mean?{RESET}
  • {BOLD}quit{RESET} or {BOLD}exit{RESET} — end session
"""

# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Demand Pattern Analyzer chat (Ollama)")
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "llama3.2"),
                        help="Ollama model name (default: llama3.2)")
    parser.add_argument("--url",   default=os.getenv("OLLAMA_URL", "http://localhost:11434"),
                        help="Ollama base URL (default: http://localhost:11434)")
    args = parser.parse_args()

    banner(args.model, args.url)

    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = input(f"{BOLD}{GREEN}You:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Goodbye!{RESET}")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q", "bye"):
            print(f"{DIM}Goodbye!{RESET}")
            break

        if user_input.lower() in ("help", "?"):
            print(HELP_TEXT)
            continue

        intent, extra = detect_intent(user_input)
        tool_context = ""

        # ── Handle tool intents ──────────────────────────────────────────────
        if intent == "analyze":
            file_path = extra or state["file_path"]
            if not file_path:
                print(f"{RED}No file found in your message. "
                      f"Please include a path to a .csv or .xlsx file.{RESET}\n")
                continue
            state["file_path"] = file_path
            summary, ok = full_pipeline(file_path)
            if not ok:
                print(f"{RED}{summary}{RESET}\n")
                continue
            tool_context = f"\n\n[Analysis Results]\n{summary}"

        elif intent == "forecast":
            if not state["has_profile"]:
                print(f"{YELLOW}No data loaded yet. "
                      f"Please provide a CSV/Excel file path first.{RESET}\n")
                continue
            weeks = extra or 8
            ok, out = run_forecaster(weeks)
            if not ok:
                print(f"{RED}Forecaster failed: {out}{RESET}\n")
                continue
            run_visualizer()  # refresh report
            tool_context = f"\n\n[Forecast Results]\n{read_summary('forecast_results.json')}"

        elif intent == "report":
            if not state["has_forecast"]:
                print(f"{YELLOW}No forecast yet. "
                      f"Load a data file first.{RESET}\n")
                continue
            ok, out = run_visualizer()
            if not ok:
                print(f"{RED}Visualizer failed: {out}{RESET}\n")
                continue
            tool_context = "\n\n[Report] report.html updated — open it in your browser."

        # ── Send to LLM ──────────────────────────────────────────────────────
        content = user_input + tool_context
        history.append({"role": "user", "content": content})

        print(f"\n{BOLD}{CYAN}Assistant:{RESET} ", end="", flush=True)
        full_reply = ""
        for token in ollama_chat(history, args.model, args.url):
            print(token, end="", flush=True)
            full_reply += token
        print("\n")

        history.append({"role": "assistant", "content": full_reply})


if __name__ == "__main__":
    main()
