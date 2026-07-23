# PyNIDM Developer Manual

The full, up-to-date developer manual is published on ReadTheDocs and built from
[`docs/source/developer_manual.rst`](docs/source/developer_manual.rst):

- **Developer manual:**
  https://pynidm.readthedocs.io/en/latest/developer_manual.html

It covers:

- Why the prov-free LinkML refactor happened and where it landed
- Package layout and the prov-free boundary (reverse-shims, the `[legacy]` extra)
- The four-layer model: schema → generated Pydantic → wrapper classes → tools
- **The schema is the source of truth** — `nidm_schema.yaml` and
  `python scripts/regen_schema.py`
- The wrapper layer (`LinkMLBackedNode`), serialization, loading, and the query layer
- **How to change the model** (worked walkthrough) and how to add a CLI tool
- Testing, including the `test_prov_free.py` regression guard
- Common gotchas and a glossary

> This file is a pointer. Please edit the reStructuredText source at
> `docs/source/developer_manual.rst` rather than this stub.
