# PyNIDM User Manual

The full, up-to-date user manual is published on ReadTheDocs and built from
[`docs/source/index.rst`](docs/source/index.rst):

- **User manual (install, CLI tools, querying, examples):**
  https://pynidm.readthedocs.io/en/latest/

It covers:

- Installation (including the optional `pynidm[legacy]` extra)
- The NIDM model (graph hierarchy, participant linkage, data elements)
- Converting data to NIDM — `bidsmri2nidm` (BIDS) and `csv2nidm` (assessments/derivatives)
- Querying — `pynidm query` (SPARQL, the `-nl` resolver, the Oxigraph engine) and
  `pynidm queryai` (natural-language, AI-assisted)
- Visualization, conversion, merging, concatenation, and linear regression
- Worked SPARQL query examples

For architecture, the LinkML schema → code workflow, and how to extend the
model, see the **[Developer Manual](DEVELOPER_MANUAL.md)**.

> This file is a pointer. Please edit the reStructuredText source under
> `docs/source/` rather than this stub.
