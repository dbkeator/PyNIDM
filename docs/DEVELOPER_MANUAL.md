# PyNIDM Developer Manual

> **Moved.** This manual now lives in reStructuredText so it builds on
> ReadTheDocs alongside the rest of the docs. The single source of truth is:
>
> - Source: [`docs/source/developer_manual.rst`](source/developer_manual.rst)
> - Published: https://pynidm.readthedocs.io/en/latest/developer_manual.html
>
> Please make edits to the `.rst` source, not to this pointer.

It covers the schema-driven, RDFLib-native architecture: why the prov-free
LinkML refactor happened, the package layout and prov-free boundary
(reverse-shims + the `[legacy]` extra), the four-layer model (schema → generated
Pydantic → wrapper classes → tools), how the schema is the source of truth and
how to regenerate (`python scripts/regen_schema.py`), the wrapper layer,
serialization/loading, the query layer, a worked walkthrough for changing the
model, how to add a CLI tool, testing (including the `test_prov_free.py`
guard), gotchas, and a glossary.
