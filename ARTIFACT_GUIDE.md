# Artifact Guide for MLCAD 2026

This guide explains exactly how to turn this repository into an MLCAD 2026-ready artifact package for **Artifacts Available** and **Artifacts Evaluated – Functional**.

The short version is:

1. **GitHub alone is not enough** for the `Artifacts Available` badge.
2. You must create a **Zenodo snapshot** of the reviewed artifact.
3. You should provide a **locked environment** (preferably Docker).
4. For LLM-based workflows, you must document **models, versions, prompts, settings, retry policy, and variability/tolerance**.
5. The most practical evaluation path is usually a mix of:
   - archived cached outputs,
   - a bounded rerun subset,
   - and scripts that recompute reported tables/figures from archived outputs.

---

## 1. What this repository already provides

This repository already provides the core research artifact:

- `autochip_runner.py` — baseline AutoChip-style benchmark runner
- `autochip_stitch_runner.py` — STITCH three-condition experiment runner
- `testbenches/` — 20-module benchmark testbenches
- `testbenches_v2/` — 5-module STITCH evaluation set
- `figures/` — figure assets
- generated results directories (`results/`, `results_stitch/`) when runs are present
- a README that now explains reviewer-facing usage and variability

That is a strong starting point, but **it is not yet the final AE package by itself**.

---

## 2. What still needs to be done

To make this ready for MLCAD AE, complete the following items.

### Required for `Artifacts Available`

- [ ] Create a **Zenodo record** for the final reviewed artifact snapshot.
- [ ] Ensure the final Artifact Appendix includes the **Zenodo DOI**.
- [ ] Make sure the Zenodo snapshot corresponds to the artifact actually reviewed.

### Strongly recommended for `Artifacts Evaluated – Functional`

- [ ] Provide a **Dockerfile** or equivalent locked environment.
- [ ] Provide **pinned Python dependencies**.
- [ ] Document exact or approximate **EDA tool versions** used.
- [ ] Document **LLM model IDs**, backend type (Ollama/API), and access assumptions.
- [ ] Document **inference settings** and retry behavior.
- [ ] Archive **cached outputs / logs / metrics** used for the paper.
- [ ] Provide a **reviewer subset** with expected outcomes.
- [ ] Provide a short **smoke test**.
- [ ] Provide **Artifact Appendix** text for the AE submission PDF.

---

## 3. Fastest practical path if you are short on time

If time is limited, do the following in order.

### Tier 1 — must do

1. Update the repository documentation.
2. Add a locked environment (`Dockerfile`, `requirements.txt`).
3. Add an Artifact Appendix draft.
4. Archive cached outputs and logs used for the paper.
5. Create a Zenodo release snapshot.

### Tier 2 — strongly improve your chances

6. Add scripts for:
   - smoke test,
   - reviewer subset rerun,
   - recomputing tables from cached outputs.
7. Add a run manifest capturing:
   - model/backend,
   - settings,
   - date,
   - machine/GPU,
   - tool versions.

### Tier 3 — best practice

8. Archive prompt templates and/or generated prompt dumps.
9. Add checksums or release notes for major cached artifacts.
10. Add an AE-focused directory with one obvious reviewer path.

---

## 4. What you need to do personally

These are the human-in-the-loop tasks that typically cannot be fully automated.

### A. Zenodo setup

You should:

1. Sign in to **Zenodo**.
2. Connect your GitHub account to Zenodo.
3. Enable the repository for archival.
4. Create a GitHub release or tag for the reviewed artifact.
5. Let Zenodo archive that release.
6. Copy the resulting **Zenodo DOI** into:
   - the Artifact Appendix,
   - the README (optional but useful),
   - the AE submission materials.

### B. AE submission materials

You should prepare and upload:

- the **artifact abstract**,
- the **paper PDF** with the Artifact Appendix attached,
- any private large artifacts if required by AE chairs,
- any API access assumptions and disclosures.

### C. Final verification

Before submission:

- clone the reviewed branch fresh,
- follow the guide exactly,
- ensure at least the smoke test and reviewer subset path work,
- confirm the Zenodo snapshot matches what reviewers will inspect.

---

## 5. What should be included in the final artifact package

The final reviewed artifact should include as many of the following as possible:

### Documentation

- `README.md`
- `ARTIFACT_GUIDE.md`
- `ARTIFACT_APPENDIX.md`
- `COPILOT_HANDOFF_PROMPT.md`
- optional `ZENODO_CHECKLIST.md`

### Environment / setup

- `Dockerfile`
- `requirements.txt`
- optional `environment.yml`
- optional helper scripts under `scripts/`

### Source and workflow

- `autochip_runner.py`
- `autochip_stitch_runner.py`
- all benchmark/testbench assets required for evaluation

### Cached evaluation evidence

- `results/`
- `results_stitch/`
- figures used in the paper
- logs and summaries
- optional prompt dumps / run manifests

### Reviewer utilities

- smoke-test script
- subset rerun script
- metric/table recomputation script

---

## 6. Recommended directory additions

A clean reviewer-oriented structure would look like this:

```text
HDLLLM/
├── README.md
├── ARTIFACT_GUIDE.md
├── ARTIFACT_APPENDIX.md
├── COPILOT_HANDOFF_PROMPT.md
├── ZENODO_CHECKLIST.md
├── Dockerfile
├── requirements.txt
├── scripts/
│   ├── smoke_test.sh
│   ├── run_reviewer_subset.sh
│   └── recompute_tables.sh
├── manifests/
│   └── run_manifest_template.md
├── results/
├── results_stitch/
└── ...
```

---

## 7. Exact reviewer story you should aim for

A reviewer should be able to do one of the following:

### Path A — inspect archived outputs

- open cached outputs,
- inspect generated RTL and logs,
- rerun metric aggregation,
- verify the paper’s tables/claims from archived evidence.

### Path B — run a bounded rerun subset

- install the environment,
- run a smoke test,
- run a small subset such as:
  - `decoder_3to8` / `gemma3:4b` / `all`
  - `decoder_3to8` / `gemma3:12b` / `all`
  - `comb_sensitivity` / `llama3.1:8b` / `all`
  - one easy benchmark slice,
- compare outcomes against your declared tolerance.

### Path C — full rerun

- run the complete benchmark and full STITCH evaluation if they have sufficient compute and time.

---

## 8. LLM-specific requirements you must document

For each important model/backend used in the paper, capture as much of the following as possible:

- exact model ID/name
- backend type: Ollama or API
- provider name
- date range when experiments were run
- if available: model revision/hash/checkpoint reference
- inference settings:
  - temperature
  - top-p
  - top-k
  - max tokens
  - seed (if supported)
  - number of samples
  - stop sequences
- retry policy / timeout policy
- prompt template or prompt construction code
- known variability limitations

If exact revision/hash is unavailable for some API models, say so explicitly and document a **cached-output validation path**.

---

## 9. How to handle model drift and hardware variation

You do **not** need to promise exact text-identical reruns for all LLM outputs.

Instead, explicitly state:

- cached-output validation should match exactly,
- fresh reruns may vary due to:
  - model updates,
  - backend differences,
  - GPU/CPU constraints,
  - stochastic generation,
  - timeout/retry behavior,
- evaluation should focus on:
  - similar qualitative regime,
  - similar pass/fail pattern,
  - similar iteration count within tolerance,
  - valid toolchain behavior.

This is a normal and acceptable way to package LLM artifacts.

---

## 10. Minimal tolerance template you can use

Suggested language:

- **Exact recomputation from archived outputs:** must match exactly.
- **Bounded rerun subset:** same qualitative outcome is the main requirement.
- **Iteration count:** small differences are acceptable.
- **Runtime:** hardware-dependent and not normative.
- **Generated text:** exact match not required unless the claim depends on exact text.

---

## 11. Artifact Appendix guidance

Your Artifact Appendix should cover:

1. artifact abstract / summary,
2. hardware requirements,
3. software requirements,
4. model/backend requirements,
5. dataset/benchmark contents,
6. commands to run smoke test,
7. commands to run reviewer subset,
8. commands to run full evaluation,
9. expected outputs and tolerances,
10. validation path for each key result,
11. known limitations,
12. Zenodo DOI.

A draft file is being added in this branch as `ARTIFACT_APPENDIX.md`.

---

## 12. What Copilot / Claude Code should do next

If you want an AI coding assistant to finish the remaining packaging work, ask it to:

1. inspect the current repository structure,
2. add a Dockerfile,
3. pin Python dependencies,
4. add smoke-test and reviewer-subset scripts,
5. add table recomputation utilities,
6. add a run manifest template,
7. add an Artifact Appendix draft,
8. add a Zenodo checklist,
9. avoid changing the scientific claims,
10. preserve current experiment commands and file layout where possible.

A ready-to-use prompt is included in `COPILOT_HANDOFF_PROMPT.md`.

---

## 13. Final pre-submission checklist

Before submission, confirm all of the following:

- [ ] README is artifact-ready.
- [ ] Artifact guide is present.
- [ ] Artifact Appendix draft is present.
- [ ] Dockerfile is present and builds.
- [ ] Python dependencies are pinned.
- [ ] smoke test runs.
- [ ] reviewer subset script runs.
- [ ] cached outputs/logs are present or clearly referenced.
- [ ] expected outcomes and tolerances are documented.
- [ ] Zenodo DOI has been minted.
- [ ] final Zenodo snapshot matches the reviewed artifact.
- [ ] submission abstract is prepared.
- [ ] paper PDF includes Artifact Appendix.

---

## 14. If you only have a few hours left

Do this minimum set:

1. Merge documentation updates.
2. Add `Dockerfile`.
3. Add `requirements.txt`.
4. Add `ARTIFACT_APPENDIX.md`.
5. Add `ZENODO_CHECKLIST.md`.
6. Archive cached outputs.
7. Create Zenodo release.
8. Submit appendix + abstract.

That is the shortest path to a credible artifact package.
