# Zenodo Checklist

Use this checklist to create the final archival snapshot required for the **MLCAD 2026 Artifacts Available** badge.

---

## 1. Why this matters

MLCAD 2026 requires a **Zenodo DOI** for the `Artifacts Available` badge.

A GitHub repository by itself is **not sufficient** because GitHub is mutable. Zenodo provides a frozen, citable snapshot of the reviewed artifact.

---

## 2. Before creating the Zenodo release

Make sure the reviewed branch contains the files you want reviewers to evaluate.

Checklist:

- [ ] `README.md` is up to date.
- [ ] `ARTIFACT_GUIDE.md` is present.
- [ ] `ARTIFACT_APPENDIX.md` is present.
- [ ] `Dockerfile` is present.
- [ ] `requirements.txt` is present.
- [ ] reviewer scripts are present.
- [ ] cached outputs/logs are present or clearly referenced.
- [ ] any large externally hosted artifacts have stable names/checksums/locations.
- [ ] placeholders are filled where possible.

---

## 3. Connect GitHub to Zenodo

1. Sign in to Zenodo: `https://zenodo.org`
2. Go to your Zenodo GitHub integration settings.
3. Authorize GitHub access if needed.
4. Enable the repository:
   - `KarthikatLilly/HDLLLM`

---

## 4. Create the archival snapshot

1. In GitHub, make sure the final artifact branch is merged or tagged appropriately.
2. Create a GitHub release or annotated tag for the exact artifact snapshot.
3. Suggested tag naming:
   - `mlcad2026-ae-v1`
   - or similar stable version name.
4. After release creation, wait for Zenodo to ingest the release.
5. Open the Zenodo record and verify:
   - title,
   - authors,
   - description,
   - uploaded/archive contents.

---

## 5. What the Zenodo record should contain or reference

Preferably include directly:

- source snapshot,
- documentation files,
- environment files,
- helper scripts,
- benchmark/testbench assets,
- cached outputs and logs if size permits.

If very large runnable artifacts are hosted elsewhere, the Zenodo record should clearly identify:

- stable location,
- exact version/release,
- filename,
- checksum if available,
- what role that external artifact plays.

---

## 6. Copy the DOI into submission materials

After Zenodo mints the DOI:

- [ ] add DOI to `ARTIFACT_APPENDIX.md`
- [ ] optionally add DOI to `README.md`
- [ ] include DOI in the AE submission materials
- [ ] ensure the paper appendix references the same DOI

---

## 7. Final consistency check

Confirm:

- [ ] the Zenodo snapshot matches the reviewed artifact,
- [ ] the DOI resolves publicly or according to AE instructions,
- [ ] the files reviewers need are present,
- [ ] the Artifact Appendix and abstract refer to the same version.

---

## 8. Suggested release notes template

Title example:

`MLCAD 2026 artifact evaluation snapshot`

Description example:

- frozen snapshot of the STITCH artifact reviewed for MLCAD 2026,
- includes source code, reviewer documentation, environment files, and evaluation scripts,
- intended for artifact evaluation and archival citation.
