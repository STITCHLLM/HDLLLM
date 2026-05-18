# HDLLLM
# STITCH: Semantic Toolchain Integration for LLM-Driven RTL Generation

> **MLCAD 2026 Submission** — Full paper, benchmark data, and all runner scripts are released here for reproducibility.

[![Paper](https://img.shields.io/badge/Paper-MLCAD%202026-blue)](https://github.com/STITCHLLM/HDLLLM)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-yellow)](https://python.org)

---

## Overview

LLMs can generate Verilog, but the standard feedback loop (AutoChip: Icarus Verilog in the loop) has two structural blind spots:

1. **Structural blindness** — Icarus compiles and simulates RTL but never synthesises it. Unintended latches, combinational loops, and multiply-driven nets pass simulation yet fail on the physical design floor.
2. **Semantic opacity** — Raw EDA tool warnings are not actionable for weaker models. A model like `gemma3:4b` will copy `%Warning-UNUSEDSIGNAL` verbatim into a comment and regenerate the same broken code across all retries. Worse, for capable models, uninterpreted multi-tool verbosity actively disrupts their generation strategy and causes regression.

**STITCH** addresses both. It adds Verilator lint and Yosys synthesis to the AutoChip loop, and interposes a deterministic semantic interpreter that translates raw tool warnings into targeted fix directives the LLM can act on.

---

## Why This Matters: A Concrete Example

An LLM generates the following 3-to-8 decoder for `gemma3:4b`:

```verilog
module decoder_3to8 (
    input enable,
    input [2:0] in,
    output reg [7:0] out
);
always @(*) begin
    case (in)
        3'd0: out = 8'b0000_0001;
        3'd1: out = 8'b0000_0010;
        3'd2: out = 8'b0000_0100;
        3'd3: out = 8'b0000_1000;
        3'd4: out = 8'b0001_0000;
        3'd5: out = 8'b0010_0000;
        3'd6: out = 8'b0100_0000;
        3'd7: out = 8'b1000_0000;
    endcase
end
endmodule
```

**The problem:** The `enable` port is declared but never read. When `enable = 0`, the decoder should output zero — but it doesn't. The case statement runs unconditionally.

- **Icarus Verilog:** compiles without complaint. Testbench passes.
- **Yosys synthesis:** infers a latch on `out` because there is no else branch — `out` must hold its last value when the unhandled path executes. This `$_DLATCH_` cell will cause hold-time violations post-layout.
- **Verilator:** fires `%Warning-UNUSEDSIGNAL: Signal is not used: enable`.

Under the **baseline** condition, `gemma3:4b` receives the raw warning and pastes it into a comment in the next iteration. This repeats for all 6 iterations — the model never fixes the code.

Under the **STITCH semantic advanced** condition, the interpreter intercepts the warning and replaces it with:

```
CRITICAL: Port 'enable' declared but NEVER USED. You MUST condition on it:
  if (enable) begin
    <your existing case logic here>
  end else begin
    out = 8'b0;
  end
The FAIL lines (enable=0 returning non-zero output) are caused by 'enable' being ignored.
```

The model receives this directive and **resolves the module on the next iteration** — going from 6 failing iterations (14,733 tokens) to **2 iterations (2,648 tokens)**.

### Live Output — Three Conditions on `decoder_3to8` with `gemma3:4b`

<img width="1657" height="1071" alt="stitchdecoderdelta+4withyosys" src="https://github.com/user-attachments/assets/81306dbd-fcbe-4c89-9767-19c24ac47460" />

The error transition matrix tells the full story:
- `base`: `LGIC LGIC LGIC LGIC LGIC LGIC` — stuck on logic errors, never recovers
- `raw`:  `LGIC LGIC SYNT LGIC SYNT SYNT` — raw Verilator/Yosys output confuses the model and introduces new syntax errors
- `sem`:  `LGIC PASS` — semantic directive resolves it on iteration 2

---

## STITCH Pipeline


<img width="867" height="722" alt="STITCHframework" src="https://github.com/user-attachments/assets/4e4499a8-3830-423e-b9f3-a8c26a4d7e3b" />


The interpreter is a deterministic regex script — not an LLM call. It adds zero inference cost and zero latency.

### Warning Taxonomy

| Source | Code | Directive Issued |
|---|---|---|
| Verilator | `UNUSEDSIGNAL` | Named `if (port) begin...end else begin out=0; end` template |
| Verilator | `MULTIDRIVEN` | Merge conflicting drivers into one `always` block |
| Verilator | `UNDRIVEN` | Flag unconnected output; add missing assignment |
| Verilator | `WIDTHTRUNC` | Insert explicit bit-width cast |
| Yosys | Latch inferred | Extract signal name; insert `default` branch or `else` |
| Yosys | Combinational loop | Identify loop path; require intermediate register |
| Icarus | reg/wire mismatch | Classify driver type; rewrite declaration |
| Icarus | port mismatch | List expected vs. actual port names |

---

## Repository Structure

```
HDLLLM/
├── autochip_runner.py          # 20-module benchmark across 10 models (model benchmarking)
├── autochip_stitch_runner.py   # STITCH three-condition controlled experiment (feedback study)
│
├── testbenches/                # Testbenches for autochip_runner.py (20 modules)
│   ├── half_adder_tb.v
│   ├── full_adder_tb.v
│   ├── ripple_carry_adder_tb.v
│   ├── comparator_8bit_tb.v
│   ├── bcd_7seg_tb.v
│   ├── priority_encoder_tb.v
│   ├── alu_8bit_tb.v
│   ├── dff_sync_reset_tb.v
│   ├── counter_4bit_tb.v
│   ├── lfsr_8bit_tb.v
│   ├── pwm_gen_tb.v
│   ├── gray_counter_tb.v
│   ├── simple_cpu_alu_tb.v
│   ├── fsm_seq_detector_tb.v
│   ├── uart_tx_tb.v
│   ├── sync_fifo_8_tb.v
│   ├── alu_accumulator_tb.v
│   ├── param_regfile_tb.v
│   ├── pipeline_mult_4x4_tb.v  # corrected: checks N+2 not N+1
│   └── spi_master_8bit_tb.v
│
├── testbenches_v2/             # Testbenches for autochip_stitch_runner.py (5 focused modules)
│   ├── decoder_3to8_tb.v
│   ├── alu_ops_tb.v
│   ├── seg7_decoder_tb.v
│   ├── comb_sensitivity_tb.v
│   └── uart_rx_tb.v
│
├── results/                    # Auto-created by autochip_runner.py
│   └── <model>/
│       └── <module>/
│           ├── iter_1/ … iter_5/
│           │   ├── <module>.v
│           │   ├── raw_ai_response.txt
│           │   └── sim_log.txt
│           └── metrics.json
│
├── results_stitch/             # Auto-created by autochip_stitch_runner.py
│   └── <model>/
│       ├── baseline/<module>/
│       ├── raw_adv/<module>/
│       ├── sem_adv/<module>/
│       └── stitch_summary.json
│
└── figures/
    └── stitchdecoderdelta_4withyosys.png
```

---

## Installation

### Prerequisites

Install the EDA tools. On Ubuntu / WSL:

```bash
# Icarus Verilog (simulation)
sudo apt-get install iverilog

# Verilator (lint)
sudo apt-get install verilator

# Yosys (synthesis)
sudo apt-get install yosys
```

Verify all three are available:

```bash
iverilog -V
verilator --version
yosys --version
```

> **Windows users:** `autochip_stitch_runner.py` calls Verilator and Yosys via WSL. Ensure WSL2 is installed and the tools are available inside the WSL environment. `autochip_runner.py` (Icarus only) can run natively on Windows if `iverilog` is on your PATH.

### Python Dependencies

```bash
pip install openai google-genai
```

### LLM Backend — Ollama (local models)

```bash
# Install Ollama: https://ollama.com
ollama pull gemma3:4b
ollama pull gemma3:12b
ollama pull gemma3:27b
ollama pull llama3.1:8b
ollama pull qwen2.5-coder:14b
ollama pull qwen2.5-coder:32b
ollama pull deepseek-coder:6.7b
```

### LLM Backend — API models

```bash
export GEMINI_API_KEY=your_key_here    # for gemini-2.5-flash / gemini-2.5-pro
export OPENAI_API_KEY=your_key_here    # for gpt-4o, gpt-4o-mini
```

---

## Running the Benchmark — `autochip_runner.py`

This is the **20-module, 10-model benchmark** used to produce Tables 2, 3, and 4 in the paper. It runs the AutoChip loop (Icarus Verilog only, up to 5 retries) across all models on all 20 modules.

### Run a single model across all 20 modules

```bash
python autochip_runner.py --model gemma3:4b
python autochip_runner.py --model gemma3:12b
python autochip_runner.py --model qwen2.5-coder:14b
python autochip_runner.py --model llama3.1:8b
python autochip_runner.py --model deepseek-coder:6.7b
python autochip_runner.py --model gemini-2.5-flash
python autochip_runner.py --model gemini-2.5-pro
```

### Run only one difficulty tier

```bash
python autochip_runner.py --model gemma3:4b --level easy
python autochip_runner.py --model gemma3:4b --level medium
python autochip_runner.py --model gemma3:4b --level hard
python autochip_runner.py --model gemma3:4b --level critical
```

### Run a single module

```bash
python autochip_runner.py --model gemma3:4b --module decoder_3to8
python autochip_runner.py --model qwen2.5-coder:14b --module uart_tx
python autochip_runner.py --model gemma3:12b --module pipeline_mult_4x4
```

### Output

Results are written to `results/<model>/`:

```
results/gemma3_4b/
├── half_adder/
│   ├── iter_1/half_adder.v
│   ├── iter_1/sim_log.txt
│   └── metrics.json
├── lfsr_8bit/
│   └── metrics.json      ← pass_at_1: false, all 5 iterations fail
└── summary.json          ← overall pass rate, per-module breakdown
```

The terminal prints a summary table at the end:

```
========================================================================
  SUMMARY  --  Model: gemma3:4b
========================================================================
  Module                     Lvl    P   It   PassT    TotT   CE   SE  DominantError
  ----------------------------------------------------------------------
  half_adder                 easy   Y    1     3.1     3.1    0    0  -
  full_adder                 easy   Y    1     2.8     2.8    0    0  -
  lfsr_8bit                  mediu  N    -       -    44.2    0    5  logic_error
  uart_tx                    hard   N    -       -    67.1    0    5  logic_error
  ...

  Pass@k : 10/20 = 50%
  Failed : 10/20
  Total wall-clock time: 283s (4.7 min)
```

### Benchmark Modules

| Tier | Module | What is tested |
|---|---|---|
| **L1 Easy** | `half_adder` | Pure combinational assign |
| | `full_adder` | Combinational, no always blocks |
| | `ripple_carry_adder` | Module instantiation, dependency handling |
| | `comparator_8bit` | 8-bit comparison, wire/reg rules |
| | `bcd_7seg` | Case statement encoding |
| | `priority_encoder` | Priority logic |
| **L2 Medium** | `alu_8bit` | Arithmetic operations, carry-out |
| | `dff_sync_reset` | Clocked always block, non-blocking |
| | `counter_4bit` | Sequential state |
| | `lfsr_8bit` | Galois polynomial recall *(model failure)* |
| | `pwm_gen` | Counter + comparator |
| | `gray_counter` | Gray code sequencing |
| **L3 Hard** | `simple_cpu_alu` | ALU + FSM composition |
| | `fsm_seq_detector` | Mealy FSM, output timing |
| | `uart_tx` | FSM + baud counter + shift register *(model failure)* |
| | `sync_fifo_8` | Dual-pointer FIFO |
| | `alu_accumulator` | Pipeline coupling |
| **L4 Critical** | `param_regfile` | Parameterised memory |
| | `pipeline_mult_4x4` | 2-stage pipeline, N+2 latency *(oracle failure — fixed)* |
| | `spi_master_8bit` | SPI Mode 0, CPOL/CPHA *(scale-dependent)* |

---

## Running the STITCH Experiment — `autochip_stitch_runner.py`

This is the **controlled three-condition experiment** that produces Table 7 and Figure 2 in the paper. It runs the same module under three conditions to isolate the contribution of semantic interpretation:

| Condition | Tools | Interpretation | Purpose |
|---|---|---|---|
| `baseline` | Icarus only | None | Replicates AutoChip |
| `raw_adv` | Verilator + Icarus + Yosys | None | Isolates tool presence from interpretation |
| `sem_adv` | Verilator + Icarus + Yosys | **Semantic interpreter** | STITCH contribution |

The controlled variable is **feedback quality only** — the same system prompt is used for all three conditions.

### Run all three conditions on a single module

```bash
# Reproduce the paper's key result: decoder_3to8 with gemma3:4b
python autochip_stitch_runner.py --model gemma3:4b --condition all --module decoder_3to8

# Run the protective regime: decoder_3to8 with gemma3:12b
python autochip_stitch_runner.py --model gemma3:12b --condition all --module decoder_3to8

# Run the harmful regime: comb_sensitivity with llama3.1:8b
python autochip_stitch_runner.py --model llama3.1:8b --condition all --module comb_sensitivity

# Run the irrelevant regime: alu_ops with gemma3:4b
python autochip_stitch_runner.py --model gemma3:4b --condition all --module alu_ops
```

### Run all modules under all three conditions

```bash
python autochip_stitch_runner.py --model gemma3:4b --condition all
python autochip_stitch_runner.py --model gemma3:12b --condition all
```

### Run a single condition only

```bash
python autochip_stitch_runner.py --model gemma3:4b --condition baseline
python autochip_stitch_runner.py --model gemma3:4b --condition raw_adv
python autochip_stitch_runner.py --model gemma3:4b --condition sem_adv
```

### Output

The terminal prints the three-condition comparison table (Table 7):

```
==========================================================================================
  STITCH TABLE — Three-Condition Comparison  |  Model: gemma3:4b
  (Table 7 in paper)
==========================================================================================
  Module                 Cat            Baseline        Raw Adv         Sem Adv         ΔB→S  SemanFired
                                        P|Iters         P|Iters         P|Iters
  ----------------------------------------------------------------------------------------
  decoder_3to8           latch target   FAIL|6          FAIL|6          PASS|2           +4           1
  alu_ops                latch target   FAIL|6          FAIL|6          FAIL|6            0           0
  ...

  Pass rate                             0/5             0/5             1/5
  Total iterations                      6               6               2
  Total tokens                          14733           16446           2648

  Semantic interpreter fired: 1 iteration(s) across all modules (sem_adv only)

  Error Transition Matrix:
  Module                 Cond      I1    I2    I3    I4    I5    I6
  ----------------------------------------------------------------------------------
  decoder_3to8           base      LGIC  LGIC  LGIC  LGIC  LGIC  LGIC
  decoder_3to8           raw       LGIC  LGIC  SYNT  LGIC  SYNT  SYNT
  decoder_3to8           sem       LGIC  PASS
```

Results are saved to `results_stitch/<model>/stitch_summary.json`.

### STITCH Modules

| Module | Category | Why it was chosen |
|---|---|---|
| `decoder_3to8` | `latch_target` | Enable port ignored → Verilator `UNUSEDSIGNAL` → latch inferred by Yosys |
| `alu_ops` | `latch_target` | Logic-class failure — tools fire nothing, interpreter irrelevant |
| `seg7_decoder` | `latch_target` | Missing `default` in case → latch on all 7 output bits |
| `comb_sensitivity` | `verilator_target` | Intentionally partial sensitivity list → `BLKSEQ` harmful regime |
| `uart_rx` | `control` | FSM + baud sampling, protocol knowledge dependency |

---

## Results

### 20-Module Benchmark (Table 2)

| Model | Params | Pass@k | Time | Hardware |
|---|---|---|---|---|
| `gemma3:4b` | 4B | 10/20 (50%) | 4.7 min | RTX 5060 |
| `llama3.1:8b` | 8B | 13/20 (65%) | 4.0 min | RTX 5060 |
| `deepseek-coder:6.7b` | 6.7B | 13/20 (65%) | 97.9 min | CPU offload |
| `gemma3:12b` | 12B | 16/20 (80%) | 21.1 min | CPU offload |
| `qwen2.5-coder:14b` | 14B | 16/20 (80%) | 22.3 min | CPU offload |
| `gemini-2.5-flash` | API | 13/20 (65%) | <3 min | Cloud |
| `gemini-2.5-pro` | API | 16/20 (80%) | <5 min | Cloud |
| `qwen2.5-coder:14b` | 14B | 13/20 (65%) | 2.7 min | H100 |
| `qwen2.5-coder:32b` | 32B | 14/20 (70%) | 4.7 min | H100 |
| `gemma3:27b` | 27B | 14/20 (70%) | 26.1 min | H100 |

> HPC models used corrected testbenches and are not directly comparable to the laptop set.

### Failure Taxonomy (Table 3)

| Module | Class | Root Cause |
|---|---|---|
| `lfsr_8bit` | **Model failure** | Galois tap polynomial (x⁸+x⁶+x⁵+x⁴+1) not recalled; all 10 models fail |
| `uart_tx` | **Model failure** | FSM + baud-counter + shift-register temporal coupling; no EDA tool can detect |
| `pipeline_mult_4x4` | **Oracle failure** | Testbench checked N+1; correct 2-stage pipeline outputs at N+2. Fixed: all HPC models pass@1 after correction |
| `spi_master_8bit` | Scale-dependent | CPOL/CPHA phase confusion; resolved by `gemma3:27b` at iteration 3 |
| `fsm_seq_detector` | Scale-dependent | Mealy output timing confusion; fails 5/10 models including 32B |
| `alu_accumulator` | Scale-dependent | Accumulator pipeline coupling; fails 27B and 32B |

### Four Interpreter Outcome Regimes (Table 7)

| Module | Model | Baseline | Sem Adv | Δ | Regime |
|---|---|---|---|---|---|
| `decoder_3to8` | `gemma3:4b` | FAIL \| 6 iters | **PASS \| 2 iters** | **+4** | **Enabling** — interpreter resolves what baseline cannot |
| `decoder_3to8` | `gemma3:12b` | PASS \| 2 iters | PASS \| 2 iters | 0 | **Protective** — raw_adv fails all 6; sem_adv restores baseline |
| `alu_ops` | `gemma3:4b` | FAIL \| 6 iters | FAIL \| 6 iters | 0 | **Irrelevant** — logic-class failure, no EDA signal |
| `comb_sensitivity` | `llama3.1:8b` | PASS \| 4 iters | FAIL \| 6 iters | −2 | **Harmful** — BLKSEQ directive exceeds model capability floor |

### The Compute Ceiling

| Metric | RTX 5060 (8 GB) | H100 (80 GB) |
|---|---|---|
| Architecture | Blackwell | Hopper |
| Max model (FP16) | ~4B full | ~70B full |
| Tokens/sec (14B model) | ~5 t/s | ~60 t/s |
| **Best Pass@k** | **80% (12B/14B)** | **70% (32B/27B)** |
| Run time (20 modules) | 4 to 98 min | 2.7 to 26 min |

The 32B model on an H100 does not surpass the 12B laptop model. Structural errors approach zero with scale; logic errors hold constant at 10–12 per model regardless of scale or hardware.

---

## The Semantic Interpreter

The interpreter (`interpret_verilator` + `interpret_yosys_latches` in `autochip_stitch_runner.py`) is a deterministic Python regex script. It adds zero inference cost and zero latency.

```python
def interpret_verilator_warnings(raw):
    if "UNUSEDSIGNAL" in raw:
        m = re.search(r"Signal is not used: (\w+)", raw)
        if m:
            name = m.group(1)
            return (
                f"CRITICAL: Port '{name}' declared but NEVER USED. "
                f"Condition on it:\n"
                f"  if ({name}) begin ... end\n"
                f"  else begin out = 0; end"
            )
    if "Latch inferred" in raw:
        return interpret_yosys_latches(raw)
    return raw  # graceful fallback to baseline behaviour
```

Adding a new warning type requires one regex pattern and one directive template — typically under ten lines of Python. If a warning code has no registered handler, the raw output passes through unchanged, so the system degrades gracefully to baseline AutoChip behaviour.

---

## Replicating the Key Paper Results

### Step 1 — Reproduce the enabling regime (Figure 2 / Table 7 row 1)

```bash
python autochip_stitch_runner.py \
    --model gemma3:4b \
    --condition all \
    --module decoder_3to8
```

Expected output:
- `baseline`: `FAIL|6`, 14,733 tokens
- `raw_adv`: `FAIL|6`, 16,446 tokens
- `sem_adv`: `PASS|2`, 2,648 tokens, semantic interpreter fired once

### Step 2 — Reproduce the protective regime

```bash
python autochip_stitch_runner.py \
    --model gemma3:12b \
    --condition all \
    --module decoder_3to8
```

Expected output:
- `baseline`: `PASS|2`
- `raw_adv`: `FAIL|6` (multi-tool verbosity disrupts the model)
- `sem_adv`: `PASS|2` (interpretation neutralises the harm)

### Step 3 — Reproduce the harmful regime

```bash
python autochip_stitch_runner.py \
    --model llama3.1:8b \
    --condition all \
    --module comb_sensitivity
```

Expected output:
- `baseline`: `PASS|4`
- `sem_adv`: `FAIL|6` (BLKSEQ directive exceeds model capability floor)

### Step 4 — Run the full 20-module benchmark

```bash
for model in gemma3:4b llama3.1:8b gemma3:12b qwen2.5-coder:14b; do
    python autochip_runner.py --model $model
done
```

Results accumulate in `results/<model>/summary.json`.

---


## Acknowledgements

The HPC experiments were conducted on the institutional High-Performance Computing facility with NVIDIA H100 accelerators. The benchmark modules are sourced from and extended from [HDLBits](https://hdlbits.01xz.net). The AutoChip baseline is from Thakur et al., DAC 2024.

---

## License

MIT. See [LICENSE](LICENSE).
