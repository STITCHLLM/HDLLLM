# Artifact Appendix Draft for MLCAD 2026

> Replace bracketed placeholders before final submission.

---

## A. Artifact abstract

This artifact accompanies the paper **STITCH: Semantic Toolchain Integration for LLM-Driven RTL Generation**. It contains the source code, benchmark/testbench assets, experimental workflow, and reviewer documentation required to exercise the main evaluation pipeline. The artifact supports both the baseline AutoChip-style loop and the STITCH three-condition experiment that augments LLM-driven RTL generation with Verilator, Yosys, and a deterministic semantic interpreter.

The artifact is designed for two validation modes: (1) **cached-output validation**, where reviewers inspect archived outputs and recompute reported metrics from saved runs; and (2) **bounded rerun validation**, where reviewers rerun a small subset of experiments and compare qualitative outcomes against declared tolerances. Full reruns are also possible when compute, model access, and time permit.

Minimal software requirements are Linux or WSL, Python 3.10+, and the open-source EDA tools **Icarus Verilog**, **Verilator**, and **Yosys**. Some experiments additionally require access to either locally hosted Ollama models or closed API models. Because LLM outputs may vary across model revisions, serving backends, and hardware, the artifact does not require exact text-identical reproduction for bounded reruns unless exact text is the specific claim under evaluation.

---

## B. Artifact location

- Source repository: `https://github.com/KarthikatLilly/HDLLLM`
- Reviewed branch / tag: `[fill in]`
- Zenodo DOI: `[fill in after archival]`

---

## C. Artifact contents

The artifact includes:

- source workflow files (`autochip_runner.py`, `autochip_stitch_runner.py`),
- benchmark/testbench assets (`testbenches/`, `testbenches_v2/`),
- reviewer-facing documentation (`README.md`, `ARTIFACT_GUIDE.md`),
- environment packaging files (`Dockerfile`, `requirements.txt`),
- reviewer helper scripts (`scripts/`),
- optional cached outputs and logs (`results/`, `results_stitch/`),
- figure assets (`figures/`).

The artifact does not include proprietary tools, commercial PDKs, license files, or confidential datasets.

---

## D. Hardware requirements

### Minimal functional path

- CPU-only or modest workstation
- enough disk space for repository checkout plus cached outputs
- optional internet/API access if rerunning API-backed experiments

### Recommended local rerun path

- Linux or WSL2
- enough RAM/disk for EDA tools and model backend
- optional NVIDIA GPU for local Ollama-hosted models

### Full rerun path

- larger compute may be required depending on selected model(s)
- local or remote GPU resources may be necessary for larger open-weight models
- API access may be required for closed-model runs

---

## E. Software requirements

### Required open-source tools

- Python 3.10+
- Icarus Verilog
- Verilator
- Yosys

### Python packages

See `requirements.txt`.

### Optional model backends

#### Ollama-hosted local models

Examples referenced by the paper include:

- `gemma3:4b`
- `gemma3:12b`
- `gemma3:27b`
- `llama3.1:8b`
- `qwen2.5-coder:14b`
- `qwen2.5-coder:32b`
- `deepseek-coder:6.7b`

#### API-backed models

Examples referenced by the paper include:

- `gemini-2.5-flash`
- `gemini-2.5-pro`
- `gpt-4o`
- `gpt-4o-mini`

Environment variables for API-backed models may include:

```bash
export GEMINI_API_KEY=your_key_here
export OPENAI_API_KEY=your_key_here
```

---

## F. Model and inference details

The artifact uses a mix of local and API-backed LLMs. For final submission, fill in as much of the following as possible for each model used in paper-critical experiments:

- provider/backend,
- exact model ID,
- local source or API access path,
- experiment date range,
- checkpoint revision/hash if available,
- temperature,
- top-p / top-k,
- max tokens,
- seed if supported,
- number of retries / samples,
- stop sequences,
- timeout policy.

If exact revision/hash or version is not available for an API model, document that limitation and rely on cached-output validation or bounded reruns.

---

## G. Key results and how to validate them

### Result 1 — 20-module benchmark summary

**Claim:** Representative models achieve the reported pass@k behavior on the 20-module benchmark, with stronger models generally outperforming weaker ones while some modules remain model-limited.

**Validation path:**
- preferred: inspect cached outputs and recompute metrics,
- optional: bounded rerun of a subset or full rerun.

**Command(s):**

```bash
python autochip_runner.py --model gemma3:4b
python autochip_runner.py --model gemma3:12b
```

**Expected output:**
- result directories under `results/<model>/`
- per-model summary JSON / logs
- terminal summary table

**Tolerance:**
- cached-output recomputation should match exactly,
- fresh reruns may vary modestly in iteration counts, runtime, and generated text.

---

### Result 2 — STITCH enabling regime

**Claim:** On `decoder_3to8` with `gemma3:4b`, semantic interpretation can convert repeated baseline failure into an early successful repair.

**Validation path:**
- preferred: inspect cached outputs for the three conditions,
- recommended: bounded rerun.

**Command:**

```bash
python autochip_stitch_runner.py --model gemma3:4b --condition all --module decoder_3to8
```

**Expected qualitative output:**
- baseline repeatedly fails,
- raw advanced may remain unstable or fail,
- semantic advanced succeeds earlier.

**Tolerance:**
- qualitative regime should match,
- exact iteration count or tokens may vary on fresh reruns.

---

### Result 3 — STITCH protective regime

**Claim:** On `decoder_3to8` with `gemma3:12b`, semantic interpretation preserves or restores success when raw multi-tool feedback degrades behavior.

**Command:**

```bash
python autochip_stitch_runner.py --model gemma3:12b --condition all --module decoder_3to8
```

**Expected qualitative output:**
- baseline succeeds quickly,
- raw advanced may degrade,
- semantic advanced restores/preserves success.

---

### Result 4 — STITCH harmful regime

**Claim:** On `comb_sensitivity` with `llama3.1:8b`, semantic intervention can be over-directive and degrade performance.

**Command:**

```bash
python autochip_stitch_runner.py --model llama3.1:8b --condition all --module comb_sensitivity
```

**Expected qualitative output:**
- baseline succeeds or performs better,
- semantic advanced may degrade.

---

## H. Smoke test

Run:

```bash
bash scripts/smoke_test.sh
```

Expected behavior:
- verifies Python and open-source EDA tools are visible,
- prints versions,
- confirms repository layout is sane.

---

## I. Reviewer subset

Run:

```bash
bash scripts/run_reviewer_subset.sh
```

Expected behavior:
- executes a bounded subset of representative experiments, or
- prints guidance and exits cleanly if model access is not configured.

---

## J. Full evaluation

A full evaluation may include:

```bash
python autochip_runner.py --model gemma3:4b
python autochip_stitch_runner.py --model gemma3:4b --condition all
```

Additional models may be run as time and access permit.

---

## K. Recomputing metrics from cached outputs

Run:

```bash
bash scripts/recompute_tables.sh
```

Expected behavior:
- checks for cached outputs,
- recomputes or summarizes available results,
- emits a helpful message if required cached artifacts are absent.

---

## L. Variability and limitations

This artifact includes LLM-based experiments. Therefore:

- exact generated text may vary,
- API-backed models may drift over time,
- local model results may vary across hardware/backend versions,
- runtime may vary across machines,
- larger models may require compute beyond a typical laptop.

Reviewers should focus on:

- workflow correctness,
- consistency of cached outputs,
- qualitative regime matching,
- reasonable metric similarity within declared tolerance.

---

## M. Not publicly redistributed

The artifact does not include:

- API credentials,
- proprietary software,
- commercial EDA tools,
- commercial/foundry PDKs,
- confidential license files.

---

## N. Final submission note

For the `Artifacts Available` badge, replace the Zenodo placeholder with the final DOI of the reviewed artifact snapshot. The final Zenodo record should correspond to the artifact actually evaluated by reviewers.
