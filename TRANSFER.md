# Laptop transfer — PyNIDM LinkML refactor

How to pick up the `linkml-refactor` work on a fresh machine.  Snapshot
date: 2026-05-28.  Branch HEAD: `13a63b7`.  Tests: 660 passing, 1 skipped.

---

## TL;DR

```bash
# 1. clone + check out the branch
git clone git@github.com:incf-nidash/PyNIDM.git
cd PyNIDM
git checkout linkml-refactor

# 2. create the conda env that the work was done in
conda create -n nidm_test_clean python=3.9 -y
conda activate nidm_test_clean

# 3. install in editable mode with the dev extras
pip install -e ".[devel]"

# 4. install pre-commit hooks (matches the keator-laptop-uci setup)
pre-commit install

# 5. verify everything still works
pytest tests/linkml/ -x
pre-commit run --all-files
```

Expected result: **660 tests passing, 1 skipped, ~5 minutes total
runtime, pre-commit fully green.**

---

## Detailed steps

### 1. Clone the repo and check out the branch

The active development is on `linkml-refactor`.  `master` is still the
prov-toolbox-based code.

```bash
git clone git@github.com:incf-nidash/PyNIDM.git
cd PyNIDM
git checkout linkml-refactor
git log --oneline -10   # confirm HEAD is at 13a63b7 or later
```

If you have local changes on `keator-laptop-uci` that haven't been
pushed yet:

```bash
# on the OLD laptop:
git status               # check for uncommitted work
git push origin linkml-refactor

# on the NEW laptop, after the clone:
git pull origin linkml-refactor
```

### 2. Recreate the conda env

The work was done in `nidm_test_clean` with Python 3.9.23.  Match that:

```bash
conda create -n nidm_test_clean python=3.9 -y
conda activate nidm_test_clean
```

Why a fresh env instead of exporting + importing the old one:
`conda env export` captures macOS-specific paths and build hashes that
don't transfer cleanly between machines.  A fresh install of the listed
extras gives you the same surface with portable resolution.

### 3. Install dependencies

```bash
# editable install + all dev/test/linkml extras
pip install -e ".[devel]"
```

`[devel]` pulls in:
- `pytest`, `pytest-cov`
- `linkml`, `linkml-runtime`, `pydantic`
- `pre-commit`

The core install pulls in `rdflib`, `pandas`, `prov` (still needed
because the legacy `nidm.experiment` module hasn't been deleted yet —
task #12 in the refactor plan covers the cutover).

If pip warns about a build failure on `datalad` or `pyontutils`, those
are heavy deps used by a couple of helper functions but aren't blocking
for most work.  You can `pip install --no-deps -e .` to skip them and
add them back individually if you hit an `ImportError`.

### 4. Install pre-commit hooks

```bash
pre-commit install
```

This wires `git commit` to run black/isort/flake8/codespell + the
end-of-file/trailing-whitespace fixers before each commit.  Without
this, you can still commit with `--no-verify`, but the hooks help catch
the same things the CI would.

The config is `.pre-commit-config.yaml`.  The flake8 config (which
selectors / which directories to ignore) lives in `tox.ini` under
`[flake8]`.

### 5. Verify the setup

```bash
pytest tests/linkml/ -x
```

Expected: **660 passed, 1 skipped, ~5 min**.

The 1 skip is `test_read_nidm_round_trip_isomorphic` in
`tests/linkml/test_utils_chunk4.py` — it's gated on a curated NIDM
fixture that may not be present in every clone (it lives in
`tests/experiment/data/read_nidm/`).  If your clone has the fixture the
test will run, otherwise it skips cleanly.

```bash
pre-commit run --all-files
```

Expected: **all hooks pass**.

---

## What's where

```
PyNIDM/
├── src/nidm/
│   ├── experiment/                  # LEGACY (prov-toolbox-based); still in tree
│   │   ├── tools/                   #   ↳ legacy CLI tools (bidsmri2nidm, csv2nidm, ...)
│   │   ├── Utils.py                 #   ↳ legacy 4139-line Utils
│   │   └── schema/nidm_schema.yaml  # ⭐ THE source-of-truth LinkML schema
│   ├── linkml/                      # NEW (RDFLib + LinkML); active development
│   │   ├── core/                    #   ↳ Constants + BIDS_Constants + namespaces
│   │   ├── experiment/              #   ↳ wrapper classes + Utils port + tools
│   │   │   ├── tools/               #     ↳ NEW tools (bidsmri2nidm, csv2nidm)
│   │   │   └── utils.py             #     ↳ NEW Utils, ported from legacy
│   │   └── generated/               #   ↳ gen-pydantic output from the schema
│   ├── core/                        # LEGACY Constants / BIDS_Constants
│   └── workflows/                   # LEGACY (NIDM-Statistics); NOT YET PORTED (task 10)
├── tests/linkml/                    # NEW test suite (660 tests)
├── scripts/                         # regen_schema.py + smoketest helpers
├── TRANSFER.md                      # this file
├── docs/DEVELOPER_MANUAL.md         # codebase walkthrough
└── pyproject.toml / setup.cfg / tox.ini   # build + lint config
```

The cardinal rule banked from the refactor: **`src/nidm/experiment/schema/nidm_schema.yaml`
is the single source of truth.**  Pydantic classes are *generated* from it.
Wrappers introspect those generated classes to drive RDF emission.  If
you need a new slot or class, edit the schema, regenerate, then write
the wrapper layer.

---

## Regenerating the LinkML Pydantic classes

You shouldn't need to do this often, but when you do:

```bash
python scripts/regen_schema.py
```

This runs `gen-pydantic` (from the `linkml` package) against
`src/nidm/experiment/schema/nidm_schema.yaml` and writes the result to
`src/nidm/linkml/generated/nidm_schema_pydantic.py`.  It also rebuilds
the `nidm_schema_meta.py` sidecar that the wrapper layer uses for
enum-meaning lookup and field-to-enum mapping.

After regen, run the test suite to catch any breakage:

```bash
pytest tests/linkml/ -x
```

The generated file is excluded from flake8 / black via `tox.ini` and
`.pre-commit-config.yaml`, so pre-commit shouldn't complain about it.

---

## Where to resume

The refactor task list is tracked in Cowork's auto-memory:
`spaces/.../memory/MEMORY.md` and the per-task progress entries.
Open the project in Claude / Cowork and the context will reload.

Outstanding work, in roughly descending priority:

| # | Task | Notes |
|---|---|---|
| 8 (continued) | Port the remaining 19 CLI tools | nidm_query, nidm_utils, click_main, etc.  bidsmri2nidm and csv2nidm are the templates. |
| 10 | Port `src/nidm/workflows/` | NIDM-Statistics + provone.  Independent block. |
| 11 | Migrate the legacy test suite onto the new package | Run the ~3000 legacy tests against new wrappers. |
| 12 | Cutover | Swap `setup.cfg` console_scripts to point at `nidm.linkml`; deprecate the legacy `nidm.experiment` and `nidm.core` modules. |
| 7 (Part B) | Legacy-vs-new parity harness | Byte-level isomorphism on the curated fixture set.  Needs BNode canonicalization. |
| 13 | README + RTD docs + developer manual | The first iteration of the manual is `docs/DEVELOPER_MANUAL.md`. |
| 14 | Final verification | Full old + new + parity test sweeps + divergence review. |

---

## Things to watch for

1. **`prov` is still in `install_requires`** because the legacy
   `nidm.experiment` and `nidm.core` modules import it.  After
   cutover (task 12) it can be dropped.

2. **The new `read_nidm` is `~100` lines** vs the legacy `~540`.  This
   was a 5× simplification by going rdflib-native instead of routing
   through prov-toolbox.  Worth banking as a template for future port
   work.

3. **Pre-commit hooks auto-format on commit.**  If a commit fails
   because black/isort modified files, the changes are already on
   disk — just `git add` them and re-run `git commit`.

4. **The two big tools (bidsmri2nidm, csv2nidm) were ported in 4
   phases and 3 phases respectively.**  Each phase landed in its own
   commit with tests.  See `docs/DEVELOPER_MANUAL.md` for what each
   phase did and the helpers it banked.

5. **The interactive helpers in `utils.py`** (`map_variables_to_terms`,
   `find_concept_interactive`, `annotate_data_element`,
   `define_new_concept`) call `input()` directly.  Tests mock
   `builtins.input` to drive them.

---

## Quick smoke test

If you just want to verify the install works without running the full
suite:

```python
# 5-second sanity check
from nidm.linkml.experiment import Project, Session, MRAcquisition, MRObject
p = Project()
s = Session(p)
a = MRAcquisition(s)
o = MRObject(a, filename="test.nii.gz")
print(p.serialize_turtle()[:500])
```

You should see a turtle representation of a Project + Session +
MRAcquisition + MRObject with the right rdf:type triples.

---

## If something goes wrong

The most likely failure modes on a fresh machine:

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: prov` | Editable install didn't pull deps | `pip install -e ".[devel]"` |
| `import linkml` fails | `[linkml]` extra wasn't installed | `pip install linkml linkml-runtime pydantic` |
| `pre-commit` not found | Not on the conda env's PATH | `conda activate nidm_test_clean` |
| Tests fail with `chardet` ImportError | Missing optional dep | `pip install chardet` |
| Several xfails about pybids | Old pybids version | `pip install -U pybids` |
| `git commit` blocks on huge `.git/objects/tmp_obj_*` warnings | Stale FUSE-mount artifacts (Cowork sandbox quirk) | Ignore the warnings; the commit still goes through |

Otherwise: `pytest tests/linkml/ -x` will narrow it down quickly.
