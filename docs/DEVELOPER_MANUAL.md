# PyNIDM Developer Manual — LinkML Refactor

A walkthrough of the new schema-driven, RDFLib-native PyNIDM
architecture for developers who want to maintain, extend, or just
understand the codebase.

**Snapshot:** 2026-05-28, branch `linkml-refactor`, HEAD `13a63b7`,
660 tests passing.

> **Status note.**  This manual covers the *new* (LinkML/RDFLib)
> implementation in `src/nidm/linkml/`.  The *legacy* implementation
> in `src/nidm/experiment/` and `src/nidm/core/` is still on disk and
> still works — but is being progressively replaced.  Where the
> manual mentions a "legacy" function, it lives in the old tree; a
> "new" function lives in the new tree.

---

## Table of contents

1. [Why we refactored](#1-why-we-refactored)
2. [The 30-second mental model](#2-the-30-second-mental-model)
3. [The schema is the source of truth](#3-the-schema-is-the-source-of-truth)
4. [The wrapper layer](#4-the-wrapper-layer)
5. [Utils.py — the helper toolkit](#5-utilspy--the-helper-toolkit)
6. [Tool ports — worked example #1: bidsmri2nidm](#6-tool-ports--worked-example-1-bidsmri2nidm)
7. [Tool ports — worked example #2: csv2nidm](#7-tool-ports--worked-example-2-csv2nidm)
8. [How to add a new tool](#8-how-to-add-a-new-tool)
9. [How to extend the schema](#9-how-to-extend-the-schema)
10. [Testing patterns](#10-testing-patterns)
11. [Common gotchas](#11-common-gotchas)
12. [Glossary](#12-glossary)

---

## 1. Why we refactored

The legacy PyNIDM was built on top of `prov-toolbox` (the `prov`
Python package).  Three problems compounded over time:

1. **`prov-toolbox` predates rdflib's modern API and adds an extra
   indirection layer.**  Every "add a triple" call went through a
   `prov.Document` → `prov.QualifiedName` → conversion-back-to-rdflib
   chain that was slow, verbose, and brittle.
2. **The data model was hand-written, scattered, and out of sync with
   the spec.**  Adding a new field meant editing the wrapper class
   *and* the constants file *and* (sometimes) the legacy Utils.
3. **The CLI tools (`bidsmri2nidm`, `csv2nidm`, ...) duplicated a lot
   of attribute-mapping logic** that should have lived in shared
   helpers.

The refactor addresses all three:

| Before | After |
|---|---|
| `prov.Document` + ad-hoc `rdflib.Graph` mixing | Pure `rdflib.Graph` |
| Hand-written constants in `nidm.core` | LinkML schema generates Pydantic; constants are URIRef helpers |
| Each tool re-implements attribute mapping | Shared `add_attributes_with_cde`, `_write_nidm_graph`, etc. |
| `read_nidm`: 540 lines, prov-coupled | `read_nidm`: ~100 lines, rdflib-native |
| `add_attributes_with_cde`: 30+ lines, prov | `add_attributes_with_cde`: 5 lines, rdflib |

The end state: a thin, schema-driven, test-covered codebase that other
contributors can extend without learning prov-toolbox semantics.

---

## 2. The 30-second mental model

There are four layers, from "ground truth" to "how the user sees it":

```
┌──────────────────────────────────────────────────────────┐
│  Layer 1: LinkML schema (nidm_schema.yaml)               │
│  ↓ gen-pydantic                                          │
│  Layer 2: Generated Pydantic classes                     │
│  (src/nidm/linkml/generated/nidm_schema_pydantic.py)     │
│  ↓ wrapped by                                            │
│  Layer 3: Wrapper classes (Project, Session, ...)        │
│  (src/nidm/linkml/experiment/*.py)                       │
│  ↓ used by                                               │
│  Layer 4: CLI tools (bidsmri2nidm, csv2nidm, ...)        │
│  (src/nidm/linkml/experiment/tools/*.py)                 │
└──────────────────────────────────────────────────────────┘
```

When a tool wants to emit `(Project) → dcterms:title → "ABIDE"`:

- The tool calls `Project(title="ABIDE")`.
- The Pydantic class validates `title` is a valid field on `Project`.
- The wrapper's `_emit_field_triples()` looks up the slot's `slot_uri`
  in the generated class's `linkml_meta` (which is sourced from the
  schema), expands the CURIE (`dcterms:title` → `<http://purl.org/dc/terms/title>`),
  and emits the triple onto an `rdflib.Graph`.

**No layer hard-codes which predicate to use.**  Change the schema's
`slot_uri`, regenerate, and the wrapper picks up the new mapping.

---

## 3. The schema is the source of truth

**File:** `src/nidm/experiment/schema/nidm_schema.yaml`

This is the LinkML schema describing every class and slot in the
NIDM-Experiment model.  A snippet:

```yaml
classes:
  Project:
    class_uri: nidm:Project
    is_a: ProvActivity
    slots:
      - title
      - license
      - author
slots:
  title:
    slot_uri: dcterms:title
    range: string
  license:
    slot_uri: dcterms:license
    range: string
```

Two things in this snippet do real work later:

- **`class_uri: nidm:Project`** — the wrapper uses this to emit the
  `rdf:type` triple for a Project subject.  Override in the schema if
  you want a different type.
- **`slot_uri: dcterms:title`** — the wrapper expands this CURIE into
  the full URI when emitting the triple for that field.  This is why
  `Project(title="X")` ends up writing `(<project>, <dcterms:title>, "X")`.

### Regenerating the Pydantic layer

```bash
python scripts/regen_schema.py
```

This invokes `gen-pydantic` on `nidm_schema.yaml` and writes two files
into `src/nidm/linkml/generated/`:

- `nidm_schema_pydantic.py` — the generated Pydantic classes.  **Do
  not hand-edit this file.**  It's in `flake8` / `black` / `isort`
  excludes for that reason.
- `nidm_schema_meta.py` — a sidecar map of `ENUM_MEANINGS[(class, value)] →
  meaning_curie` and `FIELD_TO_ENUM_CLASS[(class, field)] → enum_class_name`.
  This exists because `gen-pydantic` doesn't preserve the `meaning:`
  annotations on enum values; we generate the sidecar to recover them
  so the wrapper layer can resolve `ImageContrastTypeEnum.T1Weighted`
  back to its `nidm:T1Weighted` URI.

After regen, run the test suite (`pytest tests/linkml/ -x`) to catch
breakage.

---

## 4. The wrapper layer

**Directory:** `src/nidm/linkml/experiment/`

The wrapper layer is what most callers touch.  Every NIDM class
(Project, Session, Acquisition, ...) has a wrapper module here.  The
inheritance chain is:

```
LinkMLBackedNode (linkml_node.py)
  ↑
  ├── Core (core.py)            — base class with the shared rdflib.Graph
  ↑
  ├── Project (project.py)
  ├── Session (session.py)
  ├── Acquisition (acquisition.py)
  │     └── MRAcquisition, PETAcquisition, AssessmentAcquisition (specializations)
  ├── AcquisitionObject (acquisition_object.py)
  │     └── MRObject, PETObject, AssessmentObject, DemographicsObject, ...
  ├── Person, SoftwareAgent, Association
  ├── Derivative, DerivativeObject
  ├── DataElement, PersonalDataElement
  ├── ExportActivity
  └── Collection
```

### What `LinkMLBackedNode` does

This is the meta-class that every wrapper inherits from.  It does
three things:

1. **Sets `pydantic_class`** to a generated Pydantic class.  The
   wrapper uses this for field validation and slot introspection.
2. **On `__init__`, walks the Pydantic class's `linkml_meta`** to
   emit one `rdf:type` triple (from `class_uri`) and one triple per
   non-None field (from each slot's `slot_uri`).
3. **Coerces wrapper-valued kwargs to their identifier strings.**
   So `MRObject(was_generated_by=acq)` works even though the schema
   stores `was_generated_by` as a string slot — the wrapper sees
   that you passed an `Acquisition` and substitutes its identifier.

### Specialization pattern

Subclasses like `MRAcquisition` add their own per-instance `rdf:type`
triples (e.g. an MR-specific URI) without re-declaring slots:

```python
class MRAcquisition(Acquisition):
    pydantic_class = gen.MRAcquisition

    def __init__(self, session, **fields):
        # extra_types lets the wrapper layer emit per-instance rdf:types
        # beyond what the schema declares for this class.
        super().__init__(
            session,
            extra_types=[NIDM["MagneticResonanceImaging"]],
            **fields,
        )
```

The same pattern lets `Collection` add `bids:Dataset` as an extra
type, `AssessmentObject` add `onli:assessment-instrument`, etc.

### Load-mode constructor

A second, less-used entry point: `wrapper.from_existing_subject(graph, uri)`.

```python
from nidm.linkml.experiment import Project
project = Project.from_existing_subject(graph, project_uri)
```

This *doesn't* emit any triples.  It binds the wrapper to an existing
subject in *graph* so you can navigate it (`project.get_sessions()`,
etc.).  This is what `read_nidm` uses to wrap a freshly-parsed NIDM
file.

### When to use the wrapper API vs raw rdflib

- **Use the wrapper API** when the field is a schema slot.  It gives
  you Pydantic validation + automatic predicate lookup.
- **Use raw `obj.graph.add((s, p, o))`** when you need a predicate
  the schema doesn't model — BIDS-specific JSON sidecar keys, ad-hoc
  attributes, etc.  This is exactly what the tools do.

---

## 5. Utils.py — the helper toolkit

**File:** `src/nidm/linkml/experiment/utils.py`

This is the ported version of the legacy 4139-line `nidm.experiment.Utils`,
broken into 8 chunks during the port (commit boundaries preserved in git
history).  Roughly:

| Chunk | What it covers |
|---|---|
| 15.1 | `safe_string`, `validate_uuid`, `tuple_keys_to_simple_keys`, `get_rdf_literal_type`, `find_in_namespaces`, `csv_dd_to_json_dd` |
| 15.2 | `add_git_annex_sources`, `add_datalad_dataset_uuid` |
| 15.3 | `add_attributes_with_cde` (the workhorse — emits one triple from a CDE-aware lookup), `add_export_provenance` |
| 15.4 | `read_nidm` — the rdflib-native load function |
| 15.5a | Fuzzy term-matching helpers (`fuzzy_match_terms_from_graph` etc.) + `keys_exists`, `match_participant_id_field`, `detect_json_format`, `redcap_datadictionary_to_json`, `write_json_mapping_file` |
| 15.5b | `map_variables_to_terms` — the keystone interactive helper |
| 15.5c | `find_concept_interactive`, `define_new_concept`, `annotate_data_element` |
| 15.6 | `DD_UUID`, `DD_to_nidm` — RedCap data dict → NIDM CDE graph |
| 15.7 | SciCrunch / InterLex / OWL / GitHub helpers (`QuerySciCrunchElasticSearch`, `InitializeInterlexRemote`, `load_nidm_owl_files`, `authenticate_github`, etc.) |

The headline functions you'll touch most:

- **`add_attributes_with_cde(obj, cde, row_variable, value)`** — emit
  one triple on *obj* for *row_variable*'s mapped CDE predicate.  Used
  by every CSV-style tool when materializing a row.
- **`add_export_provenance(...)`** — append the canonical
  Activity/Agent/Entity prov chain that says "this tool, this version,
  at this time, produced this file."  Used by every tool's
  `_write_nidm_graph` step.
- **`map_variables_to_terms(...)`** — interactively map dataframe
  columns to NIDM/InterLex concepts.  Returns `(column_to_terms, cde)`.
  Tools call this once per assessment to build the CDE graph.
- **`read_nidm(path)`** — load a NIDM file and return a `Project`
  wrapper.

### Pattern: lazy imports for heavy deps

`utils.py` uses lazy imports for `ontquery`, `cognitiveatlas`,
`github`, `chardet`, `pandas` (in helpers that don't always need it).
This is so `import nidm.linkml.experiment.utils` doesn't pull the
entire scientific Python stack at startup.

---

## 6. Tool ports — worked example #1: bidsmri2nidm

**File:** `src/nidm/linkml/experiment/tools/bidsmri2nidm.py`

The first big tool ported.  Reading the legacy version (`nidm.experiment.tools.bidsmri2nidm`)
gives you the spec; the new version below has the same CLI shape but
sits on the new wrapper layer.

### The 4 phases

Each phase was a separate commit on `linkml-refactor`:

- **Phase A** (`e6515af`): The CLI harness — argparse with `-d`, `-o`,
  `--per_subject`, `--jsonld`, `--bidsignore`, `--no_concepts`,
  `--json_map`, `--log`.  Plus `dataset_description.json` descent (the
  per-key mapping via `BIDS_Constants.dataset_description`) and the
  `--per_subject` loop with shared project/dataset UUIDs.  Output
  goes through `_write_nidm_graph` which appends export provenance.
- **Phase B** (`b99c2e3`): `participants.tsv` → `Person` / `Session` /
  `AssessmentAcquisition` / `AssessmentObject`.  Strips whitespace
  from headers, handles both `sub-01`-prefixed and bare-id forms, and
  optionally creates a `bids:sidecar_file`-typed object for
  `participants.json` linked via `prov:wasInfluencedBy`.
- **Phase C** (`4097ec4`): The heavy `addimagingsessions` per-scan
  attribute extraction.  Sidecar JSON descent (`sub-XX_T1w.json` next
  to the scan), root-level T1w.json descent, `BIDS_Constants.scans`
  mapping, `BIDS_Constants.json_keys` → DICOM/NIDM predicates,
  sha512 hash via `getsha512`, git-annex sources via
  `add_git_annex_sources`.
- **Phase D** (`9be136c`): CDE attachment via the participants.tsv
  variable map.  Calls `map_variables_to_terms` once for the unmapped
  columns, builds the BIDS-Constant CDE entries (`_emit_bids_constant_cde_entry`),
  attaches per-row triples via `add_attributes_with_cde`.

### Key helper functions banked

These are reused by `csv2nidm` and would be reused by future
BIDS-adjacent tools:

- `getRelPathToBIDS(filepath, bids_root, bidsuri_format=False)` —
  produces `bids::sub-01/anat/sub-01_T1w.nii.gz`-style paths.
- `getsha512(filename)` — SHA-512 hex digest.
- `check_encoding(filename)` — chardet wrapper.
- `addbidsignore(directory, filename)` — adds-once to `.bidsignore`.
- `_write_nidm_graph(project, collection, cde, cde_pheno, outputfile, ...)` —
  the canonical "merge graph + cde + cde_pheno + export prov, serialize"
  sequence.

### Call shape

```python
# programmatic
from nidm.linkml.experiment.tools.bidsmri2nidm import bidsmri2project, _write_nidm_graph

project, collection, cde, cde_pheno = bidsmri2project(directory, args=None)
_write_nidm_graph(project, collection, cde, cde_pheno,
                  outputfile="out.ttl",
                  bidsignore=False,
                  directory=directory)
```

```bash
# CLI
bidsmri2nidm -d /path/to/bids -o nidm.ttl --no_concepts
```

---

## 7. Tool ports — worked example #2: csv2nidm

**File:** `src/nidm/linkml/experiment/tools/csv2nidm.py`

Ported in 3 phases.  Reuses ~80% of bidsmri2nidm's helpers — that
overlap is intentional.

### The 3 phases

- **Phase A** (`062f3ec`): CLI harness + new-NIDM-file path.  CSV/TSV
  reading via `_read_input_dataframe`, data-dict resolution (REDCap /
  CSV map / raw JSON via `_resolve_json_map`), per-row Session +
  AssessmentAcquisition + AssessmentObject + Person creation via
  `_materialize_row`.
- **Phase B** (`d009961`): The `-nidm` add-to-existing path.  Uses
  SPARQL via `_query_subject_ids` to enumerate existing
  `(prov:Person, ndar:src_subject_id)` pairs, matches CSV rows to
  existing subjects (`_find_person_for_csv_row` with legacy-style
  lenient ID matching that strips leading zeros), creates new
  AssessmentObjects on the existing project graph, and writes back
  with a `.bak` backup via `_write_existing_nidm_back`.
- **Phase C** (`f6c19f6`): `-derivative` + software metadata.  Adds
  `_validate_derivative_input_columns`, `_load_software_metadata`,
  `find_session_for_subjectid` (via the Query shim), and
  `_materialize_derivative_row` which creates a `Derivative` +
  `DerivativeObject` linked to a source acquisition via `prov:used`,
  attaches a `SoftwareAgent` carrying the metadata, and emits two
  qualified associations (subject + software).

### Quirks banked

- **`SoftwareAgent.url` is not a schema slot.**  Added as a raw
  `schema:url` triple after construction.
- **`Derivative` lacks `add_qualified_association`** (which lives on
  `Acquisition`).  csv2nidm has `_add_qualified_association_to_derivative`
  that builds the Association + `prov:qualifiedAssociation` triple
  manually.  This would be a nice candidate to lift to
  `LinkMLBackedNode` during a future polish pass.
- **`read_nidm` doesn't always preserve canonical prefix bindings.**
  csv2nidm calls `bind_default_namespaces(project.graph)` after every
  `read_nidm` so the wrapper layer's CURIE expansion (`schema:name`
  etc.) works regardless of what the file declared.

---

## 8. How to add a new tool

Steps in roughly the order I'd do them:

### Step 1: Read the legacy version

`src/nidm/experiment/tools/<tool_name>.py`.  Identify:

- The argparse surface.
- The "input" reading step (CSV? BIDS dir? NIDM file?).
- The "materialization" step (which wrapper classes get created per
  row / scan / subject).
- The "output" writing step.

### Step 2: Pick a port pattern

The two big tool ports demonstrate two patterns:

- **bidsmri2nidm pattern (4 phases)**: harness → input parsing →
  per-record materialization → CDE attachment.  Use this when the
  tool consumes a structured input (BIDS, REDCap, etc.).
- **csv2nidm pattern (3 phases)**: harness → new-file path →
  add-to-existing path → derivative variant.  Use this when the tool
  can also *modify* existing NIDM files.

### Step 3: Land Phase A: CLI + harness

Reuse `_pynidm_version`, `_runtime_platform`, `add_export_provenance`,
`getRelPathToBIDS` from `bidsmri2nidm.py` where possible.  If your
tool emits a single new NIDM file, copy `_write_nidm_graph` and adapt.

### Step 4: Add tests as you go

Write the test file in `tests/linkml/test_<tool_name>.py` *with* the
code, not after.  The `_FakeArgs` pattern (a minimal namespace-shaped
class) lets you test argparse-coupled code without hand-rolling argv.

### Step 5: Verify

```bash
pytest tests/linkml/test_<tool_name>.py -v
pre-commit run --all-files
```

Pre-commit may auto-reformat — that's fine, just `git add` + commit
the result.

### Step 6: Update the progress memory

The Cowork auto-memory tracks per-tool progress.  After your tool
lands, add a line to `MEMORY.md` and a per-tool memory file.

---

## 9. How to extend the schema

You'll do this when you need a new class or slot that the current
schema doesn't model.

### Step 1: Edit `src/nidm/experiment/schema/nidm_schema.yaml`

```yaml
classes:
  YourNewClass:
    class_uri: nidm:YourNewClass
    is_a: ProvEntity
    slots:
      - your_new_slot
slots:
  your_new_slot:
    slot_uri: nidm:yourNewSlot
    range: string
```

### Step 2: Regenerate

```bash
python scripts/regen_schema.py
```

This rewrites `src/nidm/linkml/generated/nidm_schema_pydantic.py`.
Don't hand-edit that file.

### Step 3: Write the wrapper

```python
# src/nidm/linkml/experiment/your_new_class.py
from .linkml_node import LinkMLBackedNode
from ..generated import nidm_schema_pydantic as gen

class YourNewClass(LinkMLBackedNode):
    pydantic_class = gen.YourNewClass

    def __init__(self, parent, **fields):
        super().__init__(parent, **fields)
```

For specializations that need extra rdf:types, pass `extra_types=[...]`
to `super().__init__`.

### Step 4: Expose it

Add to `src/nidm/linkml/experiment/__init__.py`:

```python
from .your_new_class import YourNewClass
__all__ = [..., "YourNewClass"]
```

### Step 5: Test it

```python
# tests/linkml/test_your_new_class.py
from nidm.linkml.experiment import Project, YourNewClass
from rdflib.namespace import RDF
from nidm.linkml.core.namespaces import NIDM

def test_constructs_and_emits_type():
    p = Project()
    n = YourNewClass(p, your_new_slot="value")
    assert (n.identifier, RDF.type, NIDM.YourNewClass) in n.graph
```

---

## 10. Testing patterns

### Patterns banked from the existing 660-test suite

- **`_FakeArgs`**: a minimal namespace-shaped class for testing
  argparse-coupled code without hand-rolling argv.  Used in
  `test_csv2nidm.py` and `test_bidsmri2nidm_slim.py`.

- **Fixture-builders return Paths**: helpers like `_write_dataset_description`,
  `_write_t1w_scan`, `_write_csv` take `tmp_path` and a few kwargs,
  build a real file, and return the Path.  Use this so a test's
  setup is one or two function calls.

- **End-to-end fixtures use the tools themselves**: `_build_existing_nidm_file`
  in `test_csv2nidm.py` uses `csv2nidm_project` to create a base NIDM
  file for the add-to-existing tests.  Don't hand-roll rdflib graphs
  when a tool can produce one for you.

- **Mocking `builtins.input` for interactive helpers**:
  `monkeypatch.setattr("builtins.input", lambda _: "1")` lets you
  drive `ask_idfield`, `annotate_data_element`, etc. without prompting.

- **Mocking HTTP / heavy deps with `patch.dict("sys.modules", ...)`**:
  for `cognitiveatlas`, `ontquery`, `github`.  See `test_utils_chunk5c.py`
  and `test_utils_chunk7.py`.

- **`covering json_map` for `map_variables_to_terms`**: when a test
  uses a CSV column not in BIDS_Constants, the test must supply a
  json_map covering it, or `map_variables_to_terms` falls back to
  `annotate_data_element` which calls `input()` and the test hangs.

### Running tests

```bash
pytest tests/linkml/ -x                          # all linkml tests, stop on first fail
pytest tests/linkml/test_<file>.py -v            # one file, verbose
pytest tests/linkml/test_<file>.py::test_name    # one test
pytest tests/linkml/ -k "csv2nidm and derivative"  # filter by name
```

### Pre-commit

```bash
pre-commit run --all-files     # run on every tracked file
pre-commit run --files X Y     # run on specific files
```

If a hook modifies files, just `git add` + `git commit` again.

---

## 11. Common gotchas

### "Unknown CURIE prefix in 'schema:name'"

The wrapper layer expands CURIEs by walking the graph's namespace
bindings.  After `read_nidm`, those bindings reflect what the file
declared, which may not include all the canonical prefixes (`schema:`,
`onli:`, etc.).  Call `bind_default_namespaces(project.graph)`
explicitly after `read_nidm` if you need the canonical set.

### Pydantic ValidationError: "Extra inputs are not permitted"

You passed a kwarg the schema doesn't model.  Either:

- Add the slot to the schema and regenerate, *or*
- Add the triple manually after construction:
  `obj.graph.add((obj.identifier, predicate, value))`

### Pre-commit modifies the file and the commit fails

That's how pre-commit signals "I changed things; please review and
re-commit".  `git diff`, then `git add` + `git commit` again.  No
special incantation needed.

### Tests hang in `annotate_data_element`

A test triggered `map_variables_to_terms` with a column the json_map
doesn't cover, so the function fell through to its interactive
`input()` prompt.  Either pass `associate_concepts=False` *and* a
json_map covering every column, or only use columns the test's
json_map covers.

### `from prov.model import Identifier, QualifiedName` in tests/legacy

Legacy code that hasn't been ported yet still uses prov-toolbox.
That's expected.  The new code should never import from `prov.*`.

### A new flake8 U100 unused-arg warning

If you intentionally accept a param you don't use yet (e.g. for future
phase compatibility), annotate it:

```python
def foo(
    important,
    legacy_arg,  # noqa: U100 -- reserved for phase B integration
):
```

---

## 12. Glossary

- **CDE** — Common Data Element.  A reusable variable description
  (label, definition, valueType, etc.) shared across datasets.
- **CURIE** — Compact URI.  `dcterms:title` is a CURIE; it expands
  to `<http://purl.org/dc/terms/title>` via the declared prefix.
- **DD()** — `DD(source='X.csv', variable='age')` is a namedtuple
  that gets stringified to make compound dict keys in the variable
  mapping output.
- **InterLex** — A vocabulary registry hosted on SciCrunch.  The
  variable-mapping flow queries it via Elastic search.
- **LinkML** — The schema modeling language used to describe the
  NIDM-Experiment data model.  See [linkml.io](https://linkml.io).
- **NIDM** — Neuroimaging Data Model — the umbrella W3C-PROV-derived
  spec this codebase implements.
- **PROV** — The W3C provenance ontology.  Activities, Entities,
  Agents, and the qualified relationships between them.
- **prov-toolbox / `prov`** — The Python library wrapping PROV that
  the legacy codebase used.  Being removed by this refactor.
- **rdflib** — The pure-Python RDF library this refactor uses
  directly.
- **slot** — LinkML's term for a property/attribute on a class.
- **slot_uri** — The RDF predicate URI that the slot maps to.
- **`bind_default_namespaces`** — Helper in
  `nidm.linkml.core.namespaces` that binds the canonical prefix set
  on an rdflib Graph.
- **`from_existing_subject`** — Wrapper classmethod that binds a
  wrapper to an existing graph subject *without* emitting any new
  triples.  Used by `read_nidm`.

---

## Appendix: where to find things at a glance

| If you want to... | Look at... |
|---|---|
| Add a NIDM class or slot | `src/nidm/experiment/schema/nidm_schema.yaml`, then `python scripts/regen_schema.py` |
| Add a per-instance rdf:type to an existing class | The wrapper's `extra_types=[...]` kwarg |
| Add a new BIDS sidecar JSON key mapping | `src/nidm/linkml/core/bids_constants.py` (`json_keys` dict) |
| Add a tool | Pattern: `src/nidm/linkml/experiment/tools/csv2nidm.py`.  Test pattern: `tests/linkml/test_csv2nidm.py` |
| Trace what triples a wrapper emits | `LinkMLBackedNode.__init__` → `_emit_field_triples()` → `_emit_one_field()` in `src/nidm/linkml/experiment/linkml_node.py` |
| Understand the SPARQL Query helpers | They live in legacy `nidm.experiment.Query` and are exposed via the shim `nidm.linkml.experiment.query`.  See `csv2nidm.py`'s `find_session_for_subjectid` and `match_acquistion_task_run_from_session` for usage |
| See the canonical prefix set | `NAMESPACES` dict in `src/nidm/linkml/core/namespaces.py` |
| Find what's been done vs what's left | The Cowork auto-memory + TRANSFER.md |

---

*Last updated: 2026-05-28.  When this manual gets stale, update the
HEAD commit hash at the top and the gotchas list.*
