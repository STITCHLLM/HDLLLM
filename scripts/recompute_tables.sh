#!/usr/bin/env bash
set -euo pipefail

echo "[recompute] checking available cached artifacts"

if [ -d results ]; then
  echo "[recompute] found results/"
else
  echo "[recompute] results/ not found"
fi

if [ -d results_stitch ]; then
  echo "[recompute] found results_stitch/"
else
  echo "[recompute] results_stitch/ not found"
fi

echo "[recompute] searching for summary-like files"
find results results_stitch -maxdepth 4 \( -name 'summary.json' -o -name 'stitch_summary.json' -o -name 'metrics.json' \) 2>/dev/null || true

echo "[recompute] note: add project-specific table aggregation logic here once final archived result layout is frozen"
