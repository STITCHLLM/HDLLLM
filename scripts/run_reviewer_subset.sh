#!/usr/bin/env bash
set -euo pipefail

echo "[reviewer-subset] starting"

echo "[reviewer-subset] first run the smoke test"
bash scripts/smoke_test.sh

cat <<'EOF'

Recommended reviewer subset commands for this artifact:

1) STITCH enabling regime
   python autochip_stitch_runner.py --model gemma3:4b --condition all --module decoder_3to8

2) STITCH protective regime
   python autochip_stitch_runner.py --model gemma3:12b --condition all --module decoder_3to8

3) STITCH harmful regime
   python autochip_stitch_runner.py --model llama3.1:8b --condition all --module comb_sensitivity

4) Small benchmark slice
   python autochip_runner.py --model gemma3:4b --level easy

If the required model backend or API credentials are not configured on this machine,
reviewers may instead validate cached outputs and recompute summaries from archived results.
EOF

echo "[reviewer-subset] note: commands are documented but not auto-executed because model access may vary"
