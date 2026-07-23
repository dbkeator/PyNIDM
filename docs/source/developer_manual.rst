.. _developer_manual:

================
Developer Manual
================

A walkthrough of the schema-driven, RDFLib-native PyNIDM architecture for
developers who want to maintain, extend, or simply understand the codebase.

.. note::

   **State of the codebase.** PyNIDM has completed a full *prov-free LinkML
   refactor*. The maintained implementation lives in ``src/nidm/linkml/`` and
   depends only on `rdflib <https://rdflib.readthedocs.io>`_ — not the
   ``prov`` toolbox. The original prov-toolbox implementation
   (``src/nidm/experiment`` wrapper classes and ``src/nidm/core``) is still on
   disk for backward compatibility but is **optional**: it is installed only
   with the ``[legacy]`` extra (``pip install pynidm[legacy]``). New code
   should target ``nidm.linkml.experiment``.


.. contents:: On this page
   :local:
   :depth: 2


1. Why the refactor, and where it landed
=========================================

The legacy PyNIDM was built on top of ``prov-toolbox`` (the ``prov`` Python
package). Three problems compounded over time:

#. **prov-toolbox adds an indirection layer over rdflib.** Every "add a triple"
   call went through a ``prov.Document`` → ``prov.QualifiedName`` →
   convert-back-to-rdflib chain that was slow, verbose, and brittle.
#. **The data model was hand-written and scattered.** Adding a field meant
   editing a wrapper class *and* a constants file *and* sometimes ``Utils``.
#. **The CLI tools duplicated attribute-mapping logic** that belonged in
   shared helpers.

The refactor addressed all three, and is now complete:

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Before
     - After
   * - ``prov.Document`` + ad-hoc ``rdflib.Graph`` mixing
     - Pure ``rdflib.Graph`` (no ``prov`` import anywhere in ``nidm.linkml``)
   * - Hand-written constants in ``nidm.core``
     - A LinkML schema generates Pydantic classes; constants are ``URIRef`` helpers
   * - Each tool re-implements attribute mapping
     - Shared ``add_attributes_with_cde``, ``_write_nidm_graph``, export provenance
   * - ``read_nidm``: ~540 lines, prov-coupled
     - ``read_nidm``: rdflib-native
   * - ``prov`` a hard dependency
     - ``prov`` optional; default ``pip install pynidm`` pulls no prov

The end state is a thin, schema-driven, test-covered codebase that contributors
can extend without learning prov-toolbox semantics.


2. Package layout and the prov-free boundary
============================================

.. code-block:: text

   src/nidm/
   ├── linkml/                     # MAINTAINED, prov-free
   │   ├── experiment/
   │   │   ├── core.py             # Core: shared rdflib.Graph, serialization
   │   │   ├── linkml_node.py      # LinkMLBackedNode: schema->triples engine
   │   │   ├── project.py, session.py, acquisition.py, ...   # wrapper classes
   │   │   ├── query.py, navigate.py, cde.py                 # SPARQL query layer
   │   │   ├── dotgraph.py          # prov-free provenance visualization
   │   │   ├── utils.py             # read_nidm + the ported helper toolkit
   │   │   ├── _constants_compat.py # Constants bridge (see below)
   │   │   └── tools/               # CLI tools (bidsmri2nidm, csv2nidm, rest, ...)
   │   ├── core/
   │   │   ├── constants.py         # URIRef term constants
   │   │   ├── namespaces.py        # prefix -> rdflib.Namespace bindings
   │   │   └── bids_constants.py    # BIDS key -> NIDM predicate maps
   │   ├── generated/               # AUTO-GENERATED from the schema (do not edit)
   │   │   ├── nidm_schema_pydantic.py
   │   │   └── nidm_schema_meta.py
   │   └── workflows/               # LinkML NIDM-Statistics (placeholder)
   ├── experiment/                  # LEGACY (prov), optional [legacy] extra
   │   ├── __init__.py              # lazily imports wrappers; prov-free to import
   │   ├── Query.py, CDE.py, Navigate.py, tools/rest.py   # REVERSE-SHIMS -> nidm.linkml
   │   ├── schema/nidm_schema.yaml  # the LinkML schema (source of truth)
   │   └── ... prov wrapper classes ...
   └── core/                        # LEGACY constants (prov), optional

The important boundaries:

* **Nothing in ``nidm.linkml`` imports ``prov`` or ``nidm.core`` or
  ``nidm.experiment``.** This is enforced by
  ``tests/linkml/test_prov_free.py``, which blocks ``prov`` at import time and
  asserts the shipped CLI still imports and runs.
* **The legacy query/navigation layer is now a set of reverse-shims.**
  ``nidm.experiment.Query``, ``nidm.experiment.CDE``, ``nidm.experiment.Navigate``
  and ``nidm.experiment.tools.rest`` are thin modules that re-export the real
  implementations from ``nidm.linkml``. (This direction is the *opposite* of
  the transitional state during the refactor.)
* **The legacy wrapper classes** (``Project``, ``Session``, ... under
  ``nidm.experiment``) require ``prov``. ``nidm.experiment.__init__`` imports
  them inside a ``try/except ImportError`` so that importing a reverse-shim does
  not pull ``prov``; accessing a wrapper without the extra raises a helpful
  ``pip install pynidm[legacy]`` error.


3. The 30-second mental model
=============================

There are four layers, from ground truth to what the user sees:

.. code-block:: text

   Layer 1: LinkML schema (nidm_schema.yaml)              <- source of truth
     |  python scripts/regen_schema.py
   Layer 2: Generated Pydantic classes
            (src/nidm/linkml/generated/nidm_schema_pydantic.py)
     |  wrapped by
   Layer 3: Wrapper classes (Project, Session, ...)
            (src/nidm/linkml/experiment/*.py)
     |  used by
   Layer 4: CLI tools (bidsmri2nidm, csv2nidm, query, ...)
            (src/nidm/linkml/experiment/tools/*.py)

When a tool wants to emit ``(Project) → dctypes:title → "ABIDE"``:

* The tool calls ``Project(title="ABIDE")``.
* The generated Pydantic class validates that ``title`` is a valid field.
* The wrapper's ``_emit_field_triples()`` looks up the slot's ``slot_uri`` in
  the generated class's ``linkml_meta`` (sourced from the schema), expands the
  CURIE (``dctypes:title`` → ``<http://purl.org/dc/dcmitype/title>``), and
  emits the triple onto an ``rdflib.Graph``.

**No layer hard-codes which predicate to use.** Change the schema's
``slot_uri``, regenerate, and the wrapper picks up the new mapping for free.


4. The schema is the source of truth
====================================

**File:** ``src/nidm/experiment/schema/nidm_schema.yaml``

This LinkML schema describes every class and slot in the NIDM-Experiment model.
A real excerpt:

.. code-block:: yaml

   classes:
     Project:
       class_uri: nidm:Project
       annotations:
         additional_rdf_types: prov:Activity
       description: Top-level container for a research project or study.
       attributes:
         identifier:
           range: uriorcurie
           identifier: true
         title:
           slot_uri: dctypes:title
           range: string
         is_part_of:               # (on child classes, e.g. Session)
           slot_uri: dct:isPartOf
           range: uriorcurie
         sessions:                 # structural/containment slot -- NO slot_uri
           range: Session
           multivalued: true
           inlined_as_list: true

Three schema conventions drive runtime behavior:

* **``class_uri``** — the wrapper emits one ``rdf:type`` triple for it.
* **``annotations.additional_rdf_types``** — extra ``rdf:type`` triples emitted
  for every instance (e.g. every ``Project`` is also a ``prov:Activity``).
* **``slot_uri``** — an attribute *with* a ``slot_uri`` becomes an RDF predicate
  and is emitted as a triple. An attribute *without* one (e.g. ``sessions``,
  ``acquisitions``) is a **containment/structural** slot the wrapper
  deliberately does not emit — containment is expressed by the *child* pointing
  back via ``dct:isPartOf`` / ``prov:wasGeneratedBy``.

Enum permissible values carry a ``meaning:`` CURIE
(e.g. ``T1Weighted: {meaning: nidm:T1Weighted}``) so an enum value round-trips
to its NIDM URI.

Regenerating the generated layer
--------------------------------

.. code-block:: bash

   pip install '.[linkml]'          # one-time: installs the linkml toolchain
   python scripts/regen_schema.py   # reads the YAML, writes generated/*.py
   python scripts/smoketest_generated.py   # sanity-check the generated classes

``scripts/regen_schema.py`` invokes the LinkML ``PydanticGenerator``
programmatically (equivalent to ``gen-pydantic nidm_schema.yaml``) and writes
**two** files into ``src/nidm/linkml/generated/``:

* ``nidm_schema_pydantic.py`` — the generated Pydantic classes. **Never
  hand-edit this file.** It is excluded from flake8/black/isort.
* ``nidm_schema_meta.py`` — sidecar lookup tables ``ENUM_MEANINGS`` and
  ``FIELD_TO_ENUM_CLASS``. These exist because ``gen-pydantic`` does not
  preserve enum ``meaning:`` URIs or per-field ``range`` info; the script
  recovers them by parsing the YAML directly so the wrapper layer can resolve
  ``ImageContrastTypeEnum.T1Weighted`` back to ``nidm:T1Weighted``.

Both generated files are committed, so downstream users do not need ``linkml``
installed — only contributors editing the schema do.


5. The wrapper layer
====================

**Directory:** ``src/nidm/linkml/experiment/``

Most callers touch the wrappers. Every NIDM class has a wrapper module. The
inheritance chain:

.. code-block:: text

   Core (core.py)                    # shared rdflib.Graph, serialization, UUIDs
     └── LinkMLBackedNode (linkml_node.py)   # schema-driven triple emission
           ├── Project, Session, Acquisition, AcquisitionObject
           ├── Person, SoftwareAgent, Association, Collection
           ├── Derivative, DerivativeObject
           ├── DataElement -> PersonalDataElement
           └── ExportActivity
                 # specializations:
                 #   MRAcquisition, PETAcquisition, AssessmentAcquisition (of Acquisition)
                 #   MRObject, PETObject, AssessmentObject, DemographicsObject (of AcquisitionObject)

What ``LinkMLBackedNode`` does
------------------------------

Each wrapper sets a class attribute ``pydantic_class = gen.<ClassName>``. On
``__init__`` the base class:

#. **Coerces wrapper-valued kwargs to identifier strings** — so
   ``AcquisitionObject(was_generated_by=acq)`` works even though the schema
   stores ``was_generated_by`` as a string slot.
#. **Validates via the generated Pydantic model**
   (``self._model = pydantic_class(**fields)``).
#. **Emits triples by introspecting ``linkml_meta`` at runtime** —
   ``_emit_type_triples()`` (from ``class_uri`` + ``additional_rdf_types`` +
   per-instance ``extra_types``) and ``_emit_field_triples()`` (one triple per
   non-None ``slot_uri`` field; enums resolved via ``ENUM_MEANINGS`` /
   ``FIELD_TO_ENUM_CLASS``; URI-shaped strings become ``URIRef``, primitives
   become typed ``Literal``).

The payoff: **schema changes flow through without touching wrapper code.**
Because predicate/type/enum logic is read from the generated metadata rather
than hard-coded per wrapper, the wrappers stay in lockstep with the schema.

Specialization pattern
----------------------

Subclasses add per-instance ``rdf:type`` triples without re-declaring slots, via
the ``extra_types`` kwarg:

.. code-block:: python

   class AssessmentObject(AcquisitionObject):
       pydantic_class = gen.AssessmentObject

       def __init__(self, acquisition, **fields):
           super().__init__(
               acquisition,
               extra_types=[ONLI["assessment-instrument"]],
               **fields,
           )

The same pattern lets ``Collection`` add ``bids:Dataset``, etc. Pure Python
markers that add no RDF (e.g. ``MRAcquisition``) simply inherit the parent's
``pydantic_class``.

Load-mode constructor
---------------------

``Wrapper.from_existing_subject(graph, identifier)`` binds a wrapper to an
existing subject **without emitting triples**, so you can navigate a parsed
file. This is what ``read_nidm`` uses.

.. code-block:: python

   from nidm.linkml.experiment import Project
   project = Project.from_existing_subject(graph, project_uri)

When to use the wrapper API vs raw rdflib
-----------------------------------------

* **Wrapper API** — when the field is a schema slot; you get Pydantic
  validation and automatic predicate lookup.
* **Raw ``obj.graph.add((s, p, o))``** — when you need a predicate the schema
  does not model (BIDS sidecar keys, ad-hoc attributes). This is exactly what
  the tools do for BIDS-specific data.


6. Serialization and loading
============================

All serialization lives on ``Core`` (inherited by every wrapper). Build a graph
by constructing wrappers against a shared ``rdflib.Graph``, then serialize:

.. code-block:: python

   from nidm.linkml.experiment import Project, Session, Acquisition

   project = Project(title="ABIDE")
   session = Session(project)
   acq = Acquisition(session)

   print(project.serialize_turtle())            # Turtle string
   project.serialize_jsonld()                    # JSON-LD
   project.serialize_trig()                      # TriG (named graph)
   project.write("out.ttl", format="turtle")     # to disk
   project.save_DotGraph("out.svg", format="svg")  # provenance diagram

There is no single ``serialize()`` — the format-specific methods (and their
camelCase aliases, kept for porting) are the API. **The ``rdflib.Graph`` is the
data**, so every triple round-trips.

**Visualization** is prov-free: ``dotgraph.build_nidm_dotgraph(graph)`` builds a
``pydot.Dot`` directly from RDF triples (nodes categorized as
``prov:Activity`` / ``Entity`` / ``Agent``, ``qualifiedAssociation`` blank nodes
collapsed into direct edges). ``save_dotgraph`` renders svg/png/pdf via the
graphviz ``dot`` executable (a soft runtime dependency; svg works without it).

**Loading:** ``nidm.linkml.experiment.utils.read_nidm(path)`` parses any
rdflib-readable RDF, finds the first ``nidm:Project`` subject, wraps it via
``from_existing_subject``, and reconstructs the child wrappers (Sessions via
``dct:isPartOf``, AcquisitionObjects via ``prov:wasGeneratedBy``, etc.).

.. tip::

   ``read_nidm`` preserves whatever prefixes the file declared, which may omit
   canonical ones. If you then build with the wrapper API and hit
   "Unknown CURIE prefix", call
   ``nidm.linkml.core.namespaces.bind_default_namespaces(project.graph)`` to
   restore the canonical prefix set.


7. The query layer
==================

The SPARQL query API is now native to ``nidm.linkml`` (legacy
``nidm.experiment.Query`` / ``Navigate`` / ``CDE`` / ``tools.rest`` are
reverse-shims that re-export it).

* ``nidm.linkml.experiment.query`` — ``sparql_query_nidm(nidm_file_list, query,
  ...)``, ``GetMergedGraph``, ``OpenGraph``, the ``GetProject*`` /
  ``GetParticipant*`` families, and URI helpers (``URITail``,
  ``trimWellKnownURIPrefix``, ``expandUUID``, ``matchPrefix``). The query engine
  uses Oxigraph when ``oxrdflib`` is installed (set
  ``PYNIDM_QUERY_ENGINE=auto|oxigraph|rdflib``), else falls back to rdflib.
* ``nidm.linkml.experiment.navigate`` — higher-level traversal
  (``getProjects``, ``getSessions``, ``getActivityData``,
  ``GetProjectAttributes``, ``GetDataelements``, ...).
* ``nidm.linkml.experiment.cde`` — ``getCDEs`` / ``download_cde_files`` for the
  bundled FreeSurfer / FSL / ANTS Common Data Element graphs.
* ``nidm.linkml.experiment.tools.rest`` — the ``RestParser`` that backs
  ``pynidm query`` URI routes.

.. note::

   ``_constants_compat.Constants`` is a small bridge exposing a
   ``Constants``-shaped object (assembled from ``core.constants`` +
   ``core.namespaces``) to these relocated modules so they carry no prov
   dependency. Its ``namespaces`` map is filtered to exactly the legacy key set
   so ``matchPrefix`` / ``trimWellKnownURIPrefix`` compression is byte-identical
   to legacy output. When the legacy tree is eventually removed, this bridge can
   fold into ``core.constants`` directly.


8. utils.py — the helper toolkit
================================

**File:** ``src/nidm/linkml/experiment/utils.py`` (the rdflib-native port of the
legacy 4139-line ``nidm.experiment.Utils``).

The functions you will touch most:

* ``read_nidm(path)`` — load a NIDM file, return a ``Project`` wrapper.
* ``add_attributes_with_cde(obj, cde, row_variable, value)`` — emit one triple
  on *obj* for *row_variable*'s mapped CDE predicate. Used by every CSV-style
  tool when materializing a row.
* ``add_export_provenance(...)`` — append the canonical Activity/Agent/Entity
  chain "this tool, this version, at this time, produced this file". Used by
  every tool's write step.
* ``map_variables_to_terms(...)`` — interactively map dataframe columns to
  NIDM/InterLex concepts; returns ``(column_to_terms, cde)``.
* ``csv_dd_to_json_dd`` / ``DD_to_nidm`` — data-dictionary conversion helpers.

``utils.py`` uses lazy imports for heavy deps (``ontquery``, ``cognitiveatlas``,
``github``, ``chardet``) so ``import nidm.linkml.experiment.utils`` does not pull
the entire scientific-Python stack at startup.


9. How to change the model (worked walkthrough)
===============================================

This is the core maintenance workflow. Two cases.

Case A — add or modify a slot on an existing class
--------------------------------------------------

Say you want ``Project`` to carry a ``doi``.

**Step 1 — edit the schema** (``src/nidm/experiment/schema/nidm_schema.yaml``):

.. code-block:: yaml

   classes:
     Project:
       attributes:
         doi:
           slot_uri: dct:identifier
           range: string
           description: Digital Object Identifier for the dataset

**Step 2 — regenerate:**

.. code-block:: bash

   python scripts/regen_schema.py
   python scripts/smoketest_generated.py

**Step 3 — nothing to hand-edit.** ``LinkMLBackedNode`` emits the new predicate
automatically because it reads ``slot_uri`` from the regenerated metadata. You
can immediately do:

.. code-block:: python

   Project(title="ABIDE", doi="10.1234/abide")
   # emits (<project>, <http://purl.org/dc/terms/identifier>, "10.1234/abide")

(If the field deserves a caller-facing convenience or coercion, add a keyword to
the relevant wrapper's ``__init__``.)

**Step 4 — test.** Run ``pytest tests/linkml/ -x``, especially
``tests/linkml/test_parity.py`` (the round-trip correctness gate).

Case B — add a new class
------------------------

**Step 1 — add the class** in the YAML with ``class_uri``, any
``annotations.additional_rdf_types``, and its attributes/``slot_uri``\ s.

**Step 2 — regenerate** (``python scripts/regen_schema.py``).

**Step 3 — write the wrapper** in ``src/nidm/linkml/experiment/your_class.py``:

.. code-block:: python

   from .linkml_node import LinkMLBackedNode
   from ..generated import nidm_schema_pydantic as gen


   class YourClass(LinkMLBackedNode):
       pydantic_class = gen.YourClass

       def __init__(self, parent, **fields):
           # If this is a child node, link it back to its parent:
           fields.setdefault("is_part_of", str(parent.identifier))
           super().__init__(parent, **fields)

For per-instance extra rdf:types, pass ``extra_types=[...]`` to
``super().__init__``.

**Step 4 — expose it** in ``src/nidm/linkml/experiment/__init__.py``
(``from .your_class import YourClass`` and add to ``__all__``). If the parent
should track it, add an ``add_*``/``get_*`` facade on the parent wrapper.

**Step 5 — make it load** (if it should be reconstructed from a file): add a
walk branch in ``_populate_project_children()`` in
``src/nidm/linkml/experiment/utils.py``.

**Step 6 — test:**

.. code-block:: python

   from nidm.linkml.experiment import Project, YourClass
   from rdflib.namespace import RDF
   from nidm.linkml.core.namespaces import NIDM

   def test_constructs_and_emits_type():
       p = Project()
       n = YourClass(p, your_slot="value")
       assert (n.identifier, RDF.type, NIDM.YourClass) in n.graph


10. How to add a CLI tool
=========================

The shipped tools live in ``src/nidm/linkml/experiment/tools/`` and register
themselves on the ``pynidm`` click group.

#. **Read the tool's intent** — what does it read (CSV? BIDS dir? NIDM file?),
   what wrapper classes does it materialize per record, and how does it write
   output?
#. **Reuse the shared helpers** — ``add_export_provenance``,
   ``add_attributes_with_cde``, ``getRelPathToBIDS``, ``getsha512``,
   ``check_encoding``, and (for single-file emitters) the ``_write_nidm_graph``
   sequence in ``bidsmri2nidm.py``.
#. **Wire it into the CLI.** A click subcommand decorates a function with
   ``@cli.command()`` where ``cli`` comes from
   ``nidm.linkml.experiment.tools.click_base``; then add the module to the
   imports in ``click_main.py`` (importing it runs the registration side
   effect). An argparse tool (like ``bidsmri2nidm``/``csv2nidm``) exposes a
   ``main()`` and a ``console_scripts`` entry in ``setup.cfg``.
#. **Write tests alongside the code** in ``tests/linkml/test_<tool>.py``. The
   ``_FakeArgs`` pattern (a minimal namespace-shaped object) tests
   argparse-coupled code without hand-rolling argv; fixture builders take
   ``tmp_path`` and return real files.
#. **Verify:** ``pytest tests/linkml/test_<tool>.py -v`` and
   ``pre-commit run --all-files`` (pre-commit may auto-reformat — just
   ``git add`` and re-commit).


11. Testing
===========

.. code-block:: bash

   pytest tests/linkml/ -x                       # maintained suite, stop on first fail
   pytest tests/linkml/test_<file>.py -v         # one file
   pytest tests/linkml/ -k "csv2nidm and derivative"   # filter by name
   pytest tests/experiment/ -q                   # legacy suite (needs the [legacy] extra)

Key suites:

* ``tests/linkml/test_parity.py`` — round-trip / isomorphism correctness gate.
  It parametrizes over the repo-tracked fixtures in ``FIXTURE_PATHS``; drop your
  own ``.ttl`` files into the gitignored ``tests/linkml/local_fixtures/`` to
  stress-test locally without changing anyone else's collected count. When you
  add a *shared* fixture, add it to ``FIXTURE_PATHS`` **and commit the file**.
* ``tests/linkml/test_prov_free.py`` — the **prov-removal guard**. It installs
  an import blocker that makes ``import prov`` fail, purges cached
  ``prov``/``nidm`` modules, and asserts (a) the shipped ``pynidm`` CLI and the
  query/navigate/cde/rest layers still import, (b) the legacy reverse-shims
  import prov-free, and (c) accessing a legacy wrapper without ``prov`` raises a
  helpful ``pynidm[legacy]`` error. **If you add code to ``nidm.linkml``, keep
  it prov-free or this test will fail.**

To run the legacy suite you need ``prov``: ``pip install -e '.[devel]'`` (which
includes the ``[legacy]`` extra) or ``pip install -e '.[legacy]'``.


12. Common gotchas
==================

**"Unknown CURIE prefix in 'schema:name'" after read_nidm.**
The wrapper expands CURIEs from the graph's namespace bindings, which reflect
what the file declared. Call ``bind_default_namespaces(project.graph)`` to
restore the canonical set.

**Pydantic ``ValidationError: Extra inputs are not permitted``.**
You passed a kwarg the schema does not model. Either add the slot to the schema
and regenerate, or add the triple manually:
``obj.graph.add((obj.identifier, predicate, value))``.

**Keep ``nidm.linkml`` prov-free.**
Do not ``import prov`` (or anything that transitively imports it, e.g.
``nidm.core``/``nidm.experiment`` internals) from ``nidm.linkml``. The reverse-
shims and ``test_prov_free.py`` depend on this boundary.

**Pre-commit modifies files and the commit fails.**
That is pre-commit signaling it reformatted; ``git add`` the changes and commit
again.

**Tests hang in ``annotate_data_element``.**
A test triggered ``map_variables_to_terms`` with a column its json_map does not
cover, so it fell through to an interactive ``input()`` prompt. Pass
``associate_concepts=False`` and a json_map covering every column, or only use
covered columns.


13. Glossary
============

CDE
  Common Data Element — a reusable variable description (label, definition,
  valueType) shared across datasets.

CURIE
  Compact URI. ``dctypes:title`` expands to
  ``<http://purl.org/dc/dcmitype/title>`` via the declared prefix.

LinkML
  The schema-modeling language describing the NIDM-Experiment model. See
  `linkml.io <https://linkml.io>`_.

NIDM
  Neuroimaging Data Model — the W3C-PROV-derived spec this codebase implements.

PROV
  The W3C provenance ontology: Activities, Entities, Agents, and qualified
  relations between them.

slot / slot_uri
  LinkML's term for a class property, and the RDF predicate URI it maps to.

reverse-shim
  A legacy module (e.g. ``nidm.experiment.Query``) that re-exports the real,
  relocated implementation from ``nidm.linkml`` for backward compatibility.

``from_existing_subject``
  Wrapper classmethod that binds a wrapper to an existing graph subject without
  emitting new triples. Used by ``read_nidm``.


14. Appendix: where to find things
==================================

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - If you want to...
     - Look at...
   * - Add a NIDM class or slot
     - ``src/nidm/experiment/schema/nidm_schema.yaml``, then ``python scripts/regen_schema.py``
   * - Add a per-instance rdf:type to a class
     - the wrapper's ``extra_types=[...]`` kwarg
   * - Add a BIDS sidecar JSON key mapping
     - ``src/nidm/linkml/core/bids_constants.py``
   * - Trace what triples a wrapper emits
     - ``LinkMLBackedNode._emit_field_triples()`` in ``src/nidm/linkml/experiment/linkml_node.py``
   * - Understand the SPARQL query helpers
     - ``src/nidm/linkml/experiment/query.py`` and ``navigate.py`` (native here; legacy paths are reverse-shims)
   * - See the canonical prefix set
     - ``NAMESPACES`` in ``src/nidm/linkml/core/namespaces.py``
   * - Confirm the codebase stays prov-free
     - ``tests/linkml/test_prov_free.py``
