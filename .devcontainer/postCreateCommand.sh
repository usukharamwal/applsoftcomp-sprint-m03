#!/bin/bash
set -e

echo "=== Setting up Context Engineering Exercise ==="

# ── 1. Install Python dependencies ────────────────────────────────────────
echo "Installing Python dependencies..."
UV_LINK_MODE=copy uv sync
uv run python -c "import fitz; print('pymupdf ok')"

# ── 2. Configure OpenCode ─────────────────────────────────────────────────
echo "Configuring OpenCode..."
mkdir -p ~/.config/opencode
cat > ~/.config/opencode/opencode.json << 'EOF'
{
  "$schema": "https://opencode.ai/config.json",
  "autoshare": false,
  "model": "ollama-cloud/qwen3.5:cloud",
  "provider": {
    "ollama-cloud": {
      "models": {
        "qwen3.5:cloud": {
          "name": "qwen3.5:cloud"
        }
      }
    },
    "openrouter": {
      "models": {
        "qwen/qwen3.5-flash-02-23": {
          "name": "Qwen3.5 Flash"
        }
      }
    }
  }
}
EOF

# ── 3. Update skill commands for this environment ─────────────────────────
echo "Updating skill commands..."
for skill_file in .agents/skills/*/SKILL.md; do
  if [ -f "$skill_file" ] && ! grep -q "uv run python3" "$skill_file"; then
    sed -i "s/python3 /uv run python3 /g" "$skill_file"
    sed -i "s/\bpython \b/uv run python3 /g" "$skill_file"
  fi
done

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Open a terminal and run: opencode"
echo "  2. Type /connect, select 'Ollama Cloud', and enter your API key"
echo "     (get one at ollama.com → Settings → Keys)"
echo "  3. In OpenCode, type /setup to verify dependencies"
echo "  4. Follow the exercise in docs/task.md"
echo ""
