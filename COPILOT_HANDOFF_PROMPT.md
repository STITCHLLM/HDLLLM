# Copilot / Claude Code Handoff Prompt

Use the following prompt with GitHub Copilot coding agent, Claude Code, or another repository-aware coding assistant to finish packaging this repository for MLCAD 2026 artifact evaluation.

---

## Prompt

You are helping prepare the repository `KarthikatLilly/HDLLLM` for **MLCAD 2026 artifact evaluation**.

Repository context:

- This repository contains the STITCH artifact for LLM-driven RTL generation.
- Main workflow files are:
  - `autochip_runner.py`
  - `autochip_stitch_runner.py`
- Benchmark assets are under:
  - `testbenches/`
  - `testbenches_v2/`
- Reviewer-facing documentation already exists in:
  - `README.md`
  - `ARTIFACT_GUIDE.md`
- The repository currently supports:
  - open-source EDA tools (`iverilog`, `verilator`, `yosys`)
  - local Ollama models
  - API-based Gemini/OpenAI models

The artifact is intended for MLCAD 2026 AE, which requires:

- a Zenodo-archived final artifact for the `Artifacts Available` badge,
- a documented and exercisable workflow for the `Artifacts Evaluated – Functional` badge,
- explicit LLM-specific documentation of model identity, access, prompts/settings, and variability,
- a reviewer validation path that may rely on cached outputs and bounded reruns rather than exact text-identical LLM reproduction.

### Your task

Inspect the repository and add the missing packaging and evaluation files needed to make this repo AE-ready, while preserving the scientific content and current workflow structure.

### Goals

Please create or improve the following:

1. **Environment packaging**
   - Add a `Dockerfile` suitable for Ubuntu-based evaluation.
   - Install open-source EDA tools (`iverilog`, `verilator`, `yosys`), Python 3, pip, and project dependencies.
   - Keep the image simple and reviewer-friendly.

2. **Dependency pinning**
   - Add a `requirements.txt` with pinned versions for Python packages actually used by the repo.
   - If exact pins are unknown, choose conservative pins and clearly comment them.

3. **Artifact Appendix draft**
   - Add `ARTIFACT_APPENDIX.md` covering:
     - artifact summary,
     - hardware/software requirements,
     - model/backend requirements,
     - smoke-test instructions,
     - reviewer-subset instructions,
     - full evaluation instructions,
     - expected outputs and tolerances,
     - limitations and model drift notes,
     - Zenodo note placeholder.

4. **Zenodo checklist**
   - Add `ZENODO_CHECKLIST.md` with exact step-by-step instructions for the human maintainer to create the Zenodo archival release and copy the DOI into the submission materials.

5. **Reviewer scripts**
   - Add `scripts/smoke_test.sh`
   - Add `scripts/run_reviewer_subset.sh`
   - Add `scripts/recompute_tables.sh`
   Each script should be conservative, documented, and avoid fabricating unavailable data.

6. **Run-manifest template**
   - Add `manifests/run_manifest_template.md` that captures:
     - date,
     - commit hash,
     - machine / GPU / CPU info,
     - OS,
     - EDA tool versions,
     - model/backend identity,
     - inference settings,
     - retry policy,
     - notes.

7. **Preserve scientific fidelity**
   - Do not change paper claims casually.
   - Do not invent exact tool versions, exact prompt settings, or exact model revisions unless already present in the repo.
   - Where unknown, insert explicit placeholders and TODO notes.

8. **Structure the repository for reviewers**
   - Prefer a clear, minimal set of files at repo root.
   - Keep paths stable.
   - Make reviewer flow obvious.

### Important constraints

- Do not remove or rewrite the experimental logic unless necessary.
- Do not add commercial-tool assumptions.
- Assume variability for LLM outputs is acceptable if documented.
- Prefer cached-output validation and bounded reruns over forcing exact reproduction.
- If scripts depend on files not yet present, include checks and helpful failure messages.
- Avoid breaking existing commands in the README.

### Expected deliverables

Create or update:

- `Dockerfile`
- `requirements.txt`
- `ARTIFACT_APPENDIX.md`
- `ZENODO_CHECKLIST.md`
- `scripts/smoke_test.sh`
- `scripts/run_reviewer_subset.sh`
- `scripts/recompute_tables.sh`
- `manifests/run_manifest_template.md`

### Quality bar

The result should be practical for a human maintainer with limited time:

- clear,
- non-fragile,
- honest about what is known vs unknown,
- aligned with MLCAD 2026 artifact requirements,
- ready for final human review before Zenodo upload.

### Additional repo-specific context to preserve

The repository evaluates multiple models and regimes, including examples like:

- `gemma3:4b`
- `gemma3:12b`
- `gemma3:27b`
- `llama3.1:8b`
- `qwen2.5-coder:14b`
- `qwen2.5-coder:32b`
- `deepseek-coder:6.7b`
- `gemini-2.5-flash`
- `gemini-2.5-pro`
- possibly `gpt-4o` and `gpt-4o-mini`

The repository has undergone multiple experiment iterations and result structures. Prefer the **latest current structure in the repository** rather than trying to recreate older layouts. If multiple result layouts exist, document the latest one as canonical and mention older ones only if needed for clarity.

The key paper-facing evaluation paths include:

- the 20-module benchmark via `autochip_runner.py`,
- the 3-condition STITCH experiments via `autochip_stitch_runner.py`,
- cached-output validation,
- bounded reruns for reviewers.

Before making changes, inspect the current repository contents and adapt the files to what actually exists.

---

## How the human maintainer should use this prompt

1. Open the repository-aware coding assistant.
2. Paste the full prompt above.
3. Ask it to work on the current branch.
4. Review all changes before merging.
5. Fill in any remaining placeholders:
   - Zenodo DOI,
   - exact model revision/hash if known,
   - exact inference settings if known,
   - cached-output locations if finalized later.
