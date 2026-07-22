# HDLLLM
# STITCH: Semantic Toolchain Integration for LLM-Driven RTL Generation

> **MLCAD 2026 Submission** — This repository includes the source code, benchmark/testbench assets, and artifact-evaluation guidance for the STITCH paper. This README is written both as a project overview and as an artifact-facing guide for reviewers.

[![Paper](https://img.shields.io/badge/Paper-MLCAD%202026-blue)](https://github.com/STITCHLLM/HDLLLM)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-yellow)](https://python.org)

---

## Artifact Status for MLCAD 2026

This GitHub repository is the development and collaboration home for the artifact, but **GitHub alone is not sufficient for the MLCAD 2026 `Artifacts Available` badge**. For badge eligibility, the final reviewed artifact must be archived on **Zenodo** and cited in the Artifact Appendix with its Zenodo DOI.

This repository is therefore intended to serve three roles:

1. **Source repository** for the paper code and benchmark assets.
2. **Reviewer-facing documentation** for setup, validation, and expected outcomes.
3. **Staging area** for preparing the final Zenodo snapshot and Artifact Appendix.

If you are reviewing or reusing this work before the Zenodo DOI is added, treat this repository as the mutable working copy rather than the final archival artifact.

---

## What This Repository Contains

This repository contains the implementation and experimental workflow for **STITCH**, a semantic toolchain integration method for LLM-driven RTL generation.

At a high level, the artifact contains:

- the baseline AutoChip-style generation loop (`autochip_runner.py`),
- the STITCH three-condition controlled experiment runner (`autochip_stitch_runner.py`),
- benchmark testbench assets,
- deterministic semantic interpretation logic for Verilator/Yosys feedback,
- scripts and logic used to collect iteration-level outputs,
- generated figure and results structures referenced in the paper.

The artifact does **not** include proprietary EDA tools, commercial PDKs, or confidential license files. The released workflow uses open-source EDA tools:

- **Icarus Verilog** for simulation,
- **Verilator** for linting,
- **Yosys** for synthesis.

The artifact can be exercised with:

- **local Ollama-served models**,
- **API-based Gemini models**,
- **API-based OpenAI models**.

Because LLM-backed experiments may vary across model revisions, serving backends, hardware, and time, this artifact supports both:

- **fresh reruns**, and
- **cached-output / result-recomputation validation**.

---

## Overview

LLMs can generate Verilog, but the standard feedback loop (AutoChip: Icarus Verilog in the loop) has two structural blind spots:

1. **Structural blindness** — Icarus compiles and simulates RTL but never synthesizes it. Unintended latches, combinational loops, and multiply-driven nets can pass simulation yet fail under synthesis or downstream physical-design constraints.
2. **Semantic opacity** — Raw EDA tool warnings are often not actionable for weaker models. A model such as `gemma3:4b` may simply echo `%Warning-UNUSEDSIGNAL` into a comment and regenerate the same broken design.

**STITCH** addresses both. It augments the AutoChip loop with Verilator lint and Yosys synthesis, and interposes a deterministic semantic interpreter that translates raw tool warnings into targeted repair directives.

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

**The problem:** The `enable` port is declared but never used. When `enable = 0`, the decoder should output zero — but it does not. The case statement runs unconditionally.

- **Icarus Verilog:** compiles without complaint; a weak testbench may still pass.
- **Yosys synthesis:** infers a latch on `out` because there is no fallback assignment for unhandled paths.
- **Verilator:** emits `%Warning-UNUSEDSIGNAL: Signal is not used: enable`.

Under the **baseline** condition, `gemma3:4b` may simply copy the warning into a comment or continue failing for multiple iterations.

Under the **STITCH semantic advanced** condition, the interpreter rewrites the warning into a direct repair instruction:

```text
CRITICAL: Port 'enable' declared but NEVER USED. You MUST condition on it:
  if (enable) begin
    <your existing case logic here>
  end else begin
    out = 8'b0;
  end
The FAIL lines (enable=0 returning non-zero output) are caused by 'enable' being ignored.
```

The model can then fix the bug in the next iteration.

### Live Output — Three Conditions on `decoder_3to8` with `gemma3:4b`

<img width="1657" height="1071" alt="stitchdecoderdelta+4withyosys" src="https://github.com/user-attachments/assets/81306dbd-fcbe-4c89-9767-19c24ac47460" />

The error transition matrix captures the qualitative difference:

- `base`: `LGIC LGIC LGIC LGIC LGIC LGIC`
- `raw`: `LGIC LGIC SYNT LGIC SYNT SYNT`
- `sem`: `LGIC PASS`

---

## STITCH Pipeline

<img width="867" height="722" alt="STITCHframework" src="https://github.com/user-attachments/assets/4e4499a8-3830-423e-b9f3-a8c26a4d7e3b" />

The interpreter is a deterministic regex script — not an LLM call. It adds no extra inference call and negligible runtime overhead.

### Warning Taxonomy

| Source | Code / class | Directive issued |
|---|---|---|
| Verilator | `UNUSEDSIGNAL` | Named `if (port) ... else out=0` repair template |
| Verilator | `MULTIDRIVEN` | Merge conflicting drivers into one `always` block |
| Verilator | `UNDRIVEN` | Flag unconnected output; add missing assignment |
| Verilator | `WIDTHTRUNC` | Insert explicit bit-width cast |
| Yosys | Latch inferred | Extract signal name; add `default` or `else` |
| Yosys | Combinational loop | Identify loop path; require intermediate register |
| Icarus | reg/wire mismatch | Classify driver type; rewrite declaration |
| Icarus | port mismatch | List expected vs. actual port names |

---

## Repository Structure

```text
HDLLLM/
├── autochip_runner.py
├── autochip_stitch_runner.py
├── testbenches/
├── testbenches_v2/
├── results/                 # generated by benchmark runs
├── results_stitch/          # generated by STITCH runs
├── figures/
├── README.md
└── ARTIFACT_GUIDE.md
```

Key files and directories:

- `autochip_runner.py` — 20-module benchmark across multiple models.
- `autochip_stitch_runner.py` — three-condition controlled STITCH experiment.
- `testbenches/` — benchmark testbenches for the 20-module evaluation.
- `testbenches_v2/` — focused STITCH modules used for the controlled study.
- `results/` — generated benchmark outputs.
- `results_stitch/` — generated STITCH outputs.
- `figures/` — figures used in the paper and artifact documentation.
- `ARTIFACT_GUIDE.md` — reviewer-facing artifact checklist, release prep, and automation handoff instructions.

---

## Installation

### System prerequisites

Install the open-source EDA tools. On Ubuntu / WSL:

```bash
sudo apt-get update
sudo apt-get install -y iverilog verilator yosys python3 python3-pip
```

Verify installation:

```bash
iverilog -V
verilator --version
yosys --version
python3 --version
```

> **Windows note:** `autochip_stitch_runner.py` may rely on WSL for Verilator and Yosys. If running from Windows, ensure WSL2 is installed and that the EDA tools are available inside the WSL environment. `autochip_runner.py` is lighter-weight because it only requires Icarus Verilog.

### Python dependencies

At minimum:

```bash
pip install openai google-genai
```

If you prepare a locked artifact environment, pin all Python packages in a `requirements.txt` or equivalent environment file before archival.

---

## Model Backends

### Ollama-backed local models

Example local models used in experiments:

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

### API-backed models

```bash
export GEMINI_API_KEY=your_key_here
export OPENAI_API_KEY=your_key_here
```

Typical API models referenced in the paper:

- `gemini-2.5-flash`
- `gemini-2.5-pro`
- `gpt-4o`
- `gpt-4o-mini`

### Important reproducibility note for LLM experiments

LLM results may vary across:

- model revisions or provider-side updates,
- Ollama/backend versions,
- quantization/backend configuration,
- GPU type and available memory,
- API date and service-side model drift,
- stochastic decoding settings.

Accordingly, this artifact should be evaluated using one or more of the following paths:

1. **Cached-output validation** — use archived outputs/logs to recompute reported metrics.
2. **Bounded rerun** — rerun a small reviewer subset and compare against expected qualitative outcomes.
3. **Full rerun** — rerun the complete workflow when compute, model access, and time permit.

If exact bit-for-bit or text-identical outputs are not central to a claim, reviewers should evaluate whether the result is **functionally similar within the declared tolerance**.

---

## Running the Benchmark — `autochip_runner.py`

This is the **20-module benchmark** used to produce the benchmark summary tables in the paper. It runs the AutoChip-style loop (Icarus Verilog only, up to 5 retries) across modules and models.

### Run a single model across all modules

```bash
python autochip_runner.py --model gemma3:4b
python autochip_runner.py --model gemma3:12b
python autochip_runner.py --model qwen2.5-coder:14b
python autochip_runner.py --model llama3.1:8b
python autochip_runner.py --model deepseek-coder:6.7b
python autochip_runner.py --model gemini-2.5-flash
python autochip_runner.py --model gemini-2.5-pro
```

### Run one difficulty tier

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

### Output layout

Results are written to `results/<model>/`:

```text
results/gemma3_4b/
├── half_adder/
│   ├── iter_1/half_adder.v
│   ├── iter_1/sim_log.txt
│   └── metrics.json
├── lfsr_8bit/
│   └── metrics.json
└── summary.json
```

The terminal prints a model summary table at the end.

---

## Running the STITCH Experiment — `autochip_stitch_runner.py`

This is the **controlled three-condition experiment** used to isolate the value of semantic interpretation.

| Condition | Tools | Interpretation | Purpose |
|---|---|---|---|
| `baseline` | Icarus only | None | Replicates AutoChip |
| `raw_adv` | Verilator + Icarus + Yosys | None | Isolates tool presence from interpretation |
| `sem_adv` | Verilator + Icarus + Yosys | Semantic interpreter | STITCH contribution |

### Run all three conditions on one module

```bash
python autochip_stitch_runner.py --model gemma3:4b --condition all --module decoder_3to8
python autochip_stitch_runner.py --model gemma3:12b --condition all --module decoder_3to8
python autochip_stitch_runner.py --model llama3.1:8b --condition all --module comb_sensitivity
python autochip_stitch_runner.py --model gemma3:4b --condition all --module alu_ops
```

### Run all modules for one model

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

### Output layout

Results are written to `results_stitch/<model>/`:

```text
results_stitch/<model>/
├── baseline/<module>/
├── raw_adv/<module>/
├── sem_adv/<module>/
└── stitch_summary.json
```

---

## Results Summary

### 20-module benchmark

Representative outcomes reported in the paper include:

| Model | Pass@k | Notes |
|---|---|---|
| `gemma3:4b` | 10/20 (50%) | laptop-scale local model |
| `llama3.1:8b` | 13/20 (65%) | stronger local baseline |
| `deepseek-coder:6.7b` | 13/20 (65%) | CPU offload, slow |
| `gemma3:12b` | 16/20 (80%) | local best reported |
| `qwen2.5-coder:14b` | 16/20 (80%) | strong local model |
| `gemini-2.5-flash` | 13/20 (65%) | API model |
| `gemini-2.5-pro` | 16/20 (80%) | API model |

### STITCH controlled-study regimes

Representative qualitative regimes reported in the paper:

| Module | Model | Baseline | Sem Adv | Regime |
|---|---|---|---|---|
| `decoder_3to8` | `gemma3:4b` | FAIL \| 6 | PASS \| 2 | enabling |
| `decoder_3to8` | `gemma3:12b` | PASS \| 2 | PASS \| 2 | protective |
| `alu_ops` | `gemma3:4b` | FAIL \| 6 | FAIL \| 6 | irrelevant |
| `comb_sensitivity` | `llama3.1:8b` | PASS \| 4 | FAIL \| 6 | harmful |

### Reviewer tolerance guidance

For fresh reruns, reviewers should not require exact textual reproduction of LLM outputs unless exact text is the claim. Instead, evaluate whether:

- the workflow executes successfully,
- the intermediate toolchain signals are sensible,
- the semantic interpreter fires on the intended warnings,
- the final qualitative regime matches the paper claim,
- the pass/fail behavior and iteration count are reasonably close to the declared outcome.

Suggested tolerance for bounded reruns:

- cached-output recomputation: **must match archived outputs exactly**,
- fresh LLM rerun: **same qualitative regime preferred**, with small differences in iteration count acceptable,
- runtime: hardware-dependent; wall-clock time is informative, not normative.

---

## Recommended Artifact Evaluation Paths

### Path A — Cached-output validation

Use archived `results/` and `results_stitch/` outputs to:

- inspect generated RTL,
- inspect logs,
- recompute metrics,
- validate that reported tables/figures are consistent with archived runs.

This is the preferred path when API cost, model drift, or local compute limits make a full rerun impractical.

### Path B — Bounded rerun subset

Recommended reviewer subset:

1. `decoder_3to8` with `gemma3:4b` under `baseline`, `raw_adv`, `sem_adv`
2. `decoder_3to8` with `gemma3:12b` under `all`
3. `comb_sensitivity` with `llama3.1:8b` under `all`
4. one short benchmark slice such as `--level easy`

This subset is intended to validate the paper’s main qualitative claims without requiring the full multi-model benchmark.

### Path C — Full rerun

Reviewers with sufficient compute and model access may rerun all benchmark and STITCH experiments.

---

## Final Archival Release Checklist

Before final MLCAD AE submission and Zenodo archival, ensure the reviewed artifact includes or documents:

- exact source snapshot / release tag,
- Artifact Appendix,
- this README,
- a locked environment (preferably Docker or equivalent),
- dependency versions,
- model/backend list,
- inference settings,
- prompts or prompt-construction code,
- retry policy,
- cached outputs/logs/metrics used for the paper,
- figure/table regeneration scripts,
- expected results and tolerances,
- approximate runtime, disk usage, and compute requirements,
- note of any components not publicly redistributable.

---

## The Semantic Interpreter

The interpreter (`interpret_verilator` + `interpret_yosys_latches` in `autochip_stitch_runner.py`) is a deterministic Python regex layer. It adds no model call and negligible compute overhead.

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
    return raw
```

Adding support for a new warning type typically requires one regex handler and one directive template.

---

## Replicating Key Paper Results

### 1. Enabling regime

```bash
python autochip_stitch_runner.py \
    --model gemma3:4b \
    --condition all \
    --module decoder_3to8
```

Expected qualitative outcome:

- `baseline`: repeated failure,
- `raw_adv`: repeated failure or instability,
- `sem_adv`: early pass with semantic firing.

### 2. Protective regime

```bash
python autochip_stitch_runner.py \
    --model gemma3:12b \
    --condition all \
    --module decoder_3to8
```

Expected qualitative outcome:

- baseline passes quickly,
- raw advanced condition may degrade,
- semantic advanced restores or preserves success.

### 3. Harmful regime

```bash
python autochip_stitch_runner.py \
    --model llama3.1:8b \
    --condition all \
    --module comb_sensitivity
```

Expected qualitative outcome:

- semantic intervention can over-direct the model and degrade performance.

### 4. Full benchmark

```bash
for model in gemma3:4b llama3.1:8b gemma3:12b qwen2.5-coder:14b; do
    python autochip_runner.py --model $model
done
```

---

## Limitations and Variability

This artifact contains LLM-based experiments, so some variability is expected.

Potential sources of variation include:

- open-weight model updates or re-packaging,
- Ollama version differences,
- quantization/backend differences,
- GPU memory pressure and fallback behavior,
- API model drift,
- non-deterministic decoding,
- timeout and retry behavior.

For this reason, the strongest claims of the artifact should be interpreted as:

- **exactly reproducible from archived outputs**, and
- **functionally reproducible within tolerance on bounded reruns**.

If your rerun differs materially, inspect:

- exact model ID,
- serving backend version,
- prompt formatting,
- retry logic,
- tool versions,
- whether cached outputs or fresh runs are being compared.

---

## Acknowledgements

The HPC experiments were conducted on institutional high-performance computing infrastructure with NVIDIA H100 accelerators. Benchmark modules are sourced from and extended from HDLBits-style tasks and custom evaluation cases.

---

## License

MIT. See [LICENSE](LICENSE).
