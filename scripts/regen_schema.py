#!/usr/bin/env python3
"""
Regenerate Pydantic dataclasses from the NIDM LinkML schema.

Reads:   src/nidm/experiment/schema/nidm_schema.yaml
Writes:  src/nidm/linkml/generated/nidm_schema_pydantic.py

This script is the single source of truth for regenerating the Pydantic
class file under nidm.linkml.generated.  It is intentionally short and
imperative -- run it after every schema change.

Usage
-----
    # from the repo root
    pip install '.[linkml]'          # one-time, installs linkml toolchain
    python scripts/regen_schema.py

Notes
-----
* We invoke the LinkML PydanticGenerator programmatically rather than
  shelling out to the `gen-pydantic` CLI so the script works regardless
  of which Python environment the CLI was installed into.
* The generated file is committed to the repo so downstream consumers
  do not need linkml installed.  Only contributors who edit the schema
  need the [linkml] extras.
"""
from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "src" / "nidm" / "experiment" / "schema" / "nidm_schema.yaml"
OUTPUT_PATH = REPO_ROOT / "src" / "nidm" / "linkml" / "generated" / "nidm_schema_pydantic.py"
META_OUTPUT_PATH = REPO_ROOT / "src" / "nidm" / "linkml" / "generated" / "nidm_schema_meta.py"

HEADER = dedent(
    '''\
    """
    Auto-generated Pydantic classes for the NIDM-Experiment LinkML schema.

    DO NOT EDIT BY HAND.  Regenerate with::

        python scripts/regen_schema.py

    Source schema: src/nidm/experiment/schema/nidm_schema.yaml
    """
    # ruff: noqa  -- generated file
    # fmt: off
    '''
)


def main() -> int:
    if not SCHEMA_PATH.exists():
        print(f"ERROR: schema not found at {SCHEMA_PATH}", file=sys.stderr)
        return 1

    try:
        from linkml.generators.pydanticgen import PydanticGenerator
    except ImportError:
        print(
            "ERROR: linkml is not installed in this environment.\n"
            "Install it with:  pip install '.[linkml]'  (from the repo root)",
            file=sys.stderr,
        )
        return 2

    print(f"Reading schema:  {SCHEMA_PATH.relative_to(REPO_ROOT)}")
    generator = PydanticGenerator(str(SCHEMA_PATH))
    body = generator.serialize()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(HEADER + body)
    print(f"Wrote generated module: {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {len(body.splitlines())} lines, {len(body)} bytes")

    # Also generate the meta module (enum meanings, field->enum maps).
    # gen-pydantic does not preserve permissible_value `meaning:` URIs or
    # per-field `range:` info, so we parse the YAML directly and emit
    # static lookup tables alongside the Pydantic classes.
    _write_meta_module()

    print("\nDone.  Smoke-test with:  python scripts/smoketest_generated.py")
    return 0


def _write_meta_module() -> None:
    """
    Write src/nidm/linkml/generated/nidm_schema_meta.py with two static
    maps derived from the YAML schema:

      ENUM_MEANINGS[(enum_class_name, permissible_value)] -> meaning_curie
      FIELD_TO_ENUM_CLASS[(class_name, field_name)] -> enum_class_name

    The wrapper layer uses these to translate enum-valued fields to
    their meaning URIs without having to introspect Pydantic
    annotations or re-parse the YAML at runtime.
    """
    import yaml

    with open(SCHEMA_PATH) as f:
        schema = yaml.safe_load(f)

    schema_enums = schema.get("enums") or {}
    schema_classes = schema.get("classes") or {}

    enum_meanings: dict = {}
    for enum_name, enum_def in schema_enums.items():
        for pv_name, pv_def in (enum_def.get("permissible_values") or {}).items():
            if isinstance(pv_def, dict) and pv_def.get("meaning"):
                enum_meanings[(enum_name, pv_name)] = pv_def["meaning"]

    field_to_enum: dict = {}
    for cls_name, cls_def in schema_classes.items():
        for attr_name, attr_def in (cls_def.get("attributes") or {}).items():
            if not isinstance(attr_def, dict):
                continue
            range_name = attr_def.get("range")
            if range_name and range_name in schema_enums:
                field_to_enum[(cls_name, attr_name)] = range_name

    lines = [
        '"""',
        'Auto-generated meaning maps for the NIDM LinkML schema.',
        '',
        'DO NOT EDIT BY HAND.  Regenerate with::',
        '',
        '    python scripts/regen_schema.py',
        '',
        'Source schema: src/nidm/experiment/schema/nidm_schema.yaml',
        '',
        'gen-pydantic does not preserve permissible_value ``meaning:`` URIs or',
        'per-slot ``range:`` info on the generated classes, so the wrapper',
        'layer reads them from these static maps instead.',
        '"""',
        '# ruff: noqa  -- generated file',
        '# fmt: off',
        '',
        '# (enum_class_name, permissible_value_name) -> meaning CURIE',
        'ENUM_MEANINGS = {',
    ]
    for (enum_name, pv_name), meaning in sorted(enum_meanings.items()):
        lines.append(f"    ({enum_name!r}, {pv_name!r}): {meaning!r},")
    lines.append("}")
    lines.append("")
    lines.append("# (class_name, field_name) -> enum_class_name")
    lines.append("FIELD_TO_ENUM_CLASS = {")
    for (cls_name, field_name), enum_name in sorted(field_to_enum.items()):
        lines.append(f"    ({cls_name!r}, {field_name!r}): {enum_name!r},")
    lines.append("}")
    lines.append("")

    META_OUTPUT_PATH.write_text("\n".join(lines))
    print(
        f"Wrote meta module:      {META_OUTPUT_PATH.relative_to(REPO_ROOT)}"
        f"  ({len(enum_meanings)} enum meanings,"
        f" {len(field_to_enum)} field->enum mappings)"
    )


if __name__ == "__main__":
    raise SystemExit(main())
