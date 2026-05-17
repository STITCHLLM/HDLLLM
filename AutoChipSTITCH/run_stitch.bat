@echo off
REM ================================================================
REM  run_stitch.bat  —  STITCH MLCAD Benchmark
REM  Three-condition comparison: baseline / raw_adv / sem_adv
REM  Results -> results_stitch\<model>\stitch_summary.json
REM
REM  Usage:
REM    run_stitch.bat                    -> Table 7 key result only (fast)
REM    run_stitch.bat full               -> all models, all modules
REM    run_stitch.bat single gemma3:4b   -> one model, all modules
REM    run_stitch.bat module decoder_3to8 -> all models, one module
REM ================================================================

set MODE=%1
set ARG2=%2

REM ── Quick run: Table 7 key result (decoder_3to8, 2 models) ─────────────────
if "%MODE%"=="" goto table7

REM ── Single model, all modules ──────────────────────────────────────────────
if "%MODE%"=="single" (
    echo.
    echo [STITCH] Single model: %ARG2%
    python autochip_stitch_runner.py --model %ARG2% --condition all
    goto end
)

REM ── All models, one module ─────────────────────────────────────────────────
if "%MODE%"=="module" (
    echo.
    echo [STITCH] All models, module: %ARG2%
    python autochip_stitch_runner.py --model gemma3:4b           --condition all --module %ARG2%
    python autochip_stitch_runner.py --model gemma3:12b          --condition all --module %ARG2%
    python autochip_stitch_runner.py --model qwen2.5-coder:14b   --condition all --module %ARG2%
    python autochip_stitch_runner.py --model llama3.1:8b         --condition all --module %ARG2%
    goto end
)

REM ── Full run: all models, all modules ──────────────────────────────────────
if "%MODE%"=="full" (
    echo.
    echo [STITCH] Full benchmark - all models, all modules
    echo [STITCH] Estimated time: 2-4 hours
    echo.

    echo === gemma3:4b ===
    python autochip_stitch_runner.py --model gemma3:4b --condition all

    echo === gemma3:12b ===
    python autochip_stitch_runner.py --model gemma3:12b --condition all

    echo === qwen2.5-coder:14b ===
    python autochip_stitch_runner.py --model qwen2.5-coder:14b --condition all

    echo === llama3.1:8b ===
    python autochip_stitch_runner.py --model llama3.1:8b --condition all

    goto end
)

REM ── Table 7: decoder_3to8 only, gemma3:4b + gemma3:12b ────────────────────
:table7
echo.
echo [STITCH] Running Table 7 key result: decoder_3to8
echo   gemma3:4b  -> expect baseline=FAIL^|6, raw_adv=FAIL^|6, sem_adv=PASS^|2
echo   gemma3:12b -> expect all conditions PASS^|2 (capability boundary)
echo.

echo --- gemma3:4b ---
python autochip_stitch_runner.py --model gemma3:4b --condition all --module decoder_3to8

echo --- gemma3:12b ---
python autochip_stitch_runner.py --model gemma3:12b --condition all --module decoder_3to8

echo.
echo [STITCH] Table 7 done. Check results_stitch\
echo To run full benchmark: run_stitch.bat full

:end
