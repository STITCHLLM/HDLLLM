#!/usr/bin/env bash
set -euo pipefail

echo "[smoke-test] checking repository root"
for path in README.md autochip_runner.py autochip_stitch_runner.py testbenches testbenches_v2; do
  if [ ! -e "$path" ]; then
    echo "[smoke-test] missing required path: $path" >&2
    exit 1
  fi
done

echo "[smoke-test] checking tool availability"
python3 --version
iverilog -V | head -n 1
verilator --version
yosys -V

echo "[smoke-test] checking python package imports"
python3 - <<'PY'
import importlib
mods = ["openai", "google.genai", "requests"]
for m in mods:
    importlib.import_module(m)
print("python dependency import check passed")
PY

echo "[smoke-test] success"
