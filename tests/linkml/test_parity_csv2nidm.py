"""Legacy-vs-LinkML graph-parity gate for ``csv2nidm``.

Mirrors :mod:`tests.linkml.test_parity_bidsmri2nidm`: it builds small CSV
fixtures, runs BOTH the legacy prov-toolbox converter and the LinkML converter
on *identical copies* of the same input via ``subprocess``, and asserts the two
outputs are **typed-shape equal** (using the proven comparator in
:mod:`scripts.parity_compare`).  The goal is to prove the LinkML ``csv2nidm``
output is identical to the legacy tool's, in every mode.

Modes covered
-------------
1. FRESH assessment file  (``-csv ... -json_map ... -no_concepts -out out.ttl``)
2. ADD-to-existing        (``-csv ... -json_map ... -nidm base.ttl -no_concepts``)
3. DERIVATIVE fresh-file  (``-csv ... -json_map ... -derivative software.csv
   -no_concepts -out out.ttl``)

Skip semantics
--------------
The gate only runs where BOTH converters import (the parity env with the
``[legacy]`` extra installed).  A plain LinkML env has no legacy
``nidm.experiment.tools.csv2nidm`` / ``prov`` and skips cleanly at module load
rather than erroring.

Runner semantics
----------------
``map_variables_to_terms`` writes a ``*_annotations.json`` sidecar into the
output directory, and both tools mutate/append their inputs, so each tool is run
inside its OWN copy of the fixture (``shutil.copytree``) with output written into
that same copy.  This prevents one tool's sidecar / in-place rewrite from leaking
into the other tool's run and producing a false divergence.

Runnability
-----------
Both modules carry an ``if __name__ == "__main__":`` guard that calls
``csv2nidm_main()`` (legacy: ``src/nidm/experiment/tools/csv2nidm.py`` ~1252;
LinkML: ``src/nidm/linkml/experiment/tools/csv2nidm.py`` ~1328), so BOTH are
``-m``-runnable and are invoked by module exactly like the bidsmri2nidm gate --
no need to fall back to the ``csv2nidm`` console script.  The two share identical
flag names (``-csv``, ``-json_map``, ``-no_concepts``, ``-nidm``, ``-out``,
``-derivative``), so a single command shape drives both.
"""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

# --- skip cleanly unless the legacy tool is importable (parity env only) ----
pytest.importorskip("prov")
try:  # legacy converter must import, else this is a plain LinkML env
    import nidm.experiment.tools.csv2nidm  # noqa: F401
except Exception as exc:  # pragma: no cover -- exercised only in linkml-only env
    pytest.skip(
        f"legacy csv2nidm unavailable ({exc}); parity gate needs the " "[legacy] extra",
        allow_module_level=True,
    )

# --- import the proven typed-shape comparator from scripts/ -----------------
# The comparator is a repo-root ``scripts`` module (not an installed package),
# so make sure the repo root is importable regardless of pytest's import mode.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from scripts.parity_compare import compare, format_diff  # noqa: E402
from nidm.linkml.core.constants import DD  # noqa: E402

LEGACY_MODULE = "nidm.experiment.tools.csv2nidm"
LINKML_MODULE = "nidm.linkml.experiment.tools.csv2nidm"


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _write_csv(path: Path, header: list, rows: list) -> Path:
    lines = [",".join(header)]
    for r in rows:
        lines.append(",".join(str(c) for c in r))
    path.write_text("\n".join(lines) + "\n")
    return path


def _write_covering_map(path: Path, *, source: str, variables: list, id_var: str):
    """Write a NIDM-format JSON data dictionary keyed by ``DD(source=<csv
    basename>, variable=<col>)`` so ``map_variables_to_terms`` never falls
    through to an interactive prompt under ``-no_concepts``.

    *source* must be the CSV basename both tools pass into
    ``map_variables_to_terms`` (they use ``basename(csv_file)`` as the
    ``assessment_name``), so the keys match on both sides.  *id_var* is annotated
    with ``NIDM_SUBJECTID`` so both tools auto-detect it as the subject-id column
    (``detect_idfield``); every other variable gets a distinct example concept.
    """
    from nidm.linkml.core import constants as _C

    payload = {}
    for var in variables:
        if var == id_var:
            isabout = [{"@id": str(_C.NIDM_SUBJECTID), "label": "subject_id"}]
        else:
            isabout = [{"@id": f"http://example.org/{var}", "label": var}]
        payload[str(DD(source=source, variable=var))] = {
            "label": var,
            "description": f"{var} value",
            "source_variable": var,
            "isAbout": isabout,
        }
    path.write_text(json.dumps(payload))
    return path


def _write_software_metadata(path: Path) -> Path:
    """Software-metadata CSV carrying the 7 columns both tools require for
    ``-derivative``: title, description, version, url, cmdline, platform, ID
    (legacy ~430-438; LinkML ``_SOFTWARE_METADATA_REQUIRED``)."""
    path.write_text(
        "title,description,version,url,cmdline,platform,ID\n"
        "FSL,FSL software,6.0,http://fsl.org/,fsl_anat,Linux,ilx_1234\n"
    )
    return path


# ---------------------------------------------------------------------------
# Runner + parity assertion
# ---------------------------------------------------------------------------


def _run(module: str, args: list) -> subprocess.CompletedProcess:
    """Run a csv2nidm converter via ``-m`` and return the CompletedProcess.

    ``stdin`` is closed so that if either tool tries to prompt (i.e. the covering
    map failed to cover a column) it errors instead of hanging.
    """
    cmd = [sys.executable, "-m", module] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=600,
    )


def _run_both_and_assert(src: Path, tmp_path: Path, build_args, output_rel: str):
    """Run legacy + LinkML on identical copies of *src* and assert typed-shape
    equality of the produced Turtle file.

    *build_args(work_dir)* returns the flag list (referencing files *inside*
    ``work_dir``) for a run; *output_rel* is the Turtle file to compare, relative
    to ``work_dir``.  Each tool gets its own ``copytree`` copy so a sidecar or an
    in-place ``-nidm`` rewrite can't leak into the other tool's run.
    """
    results = {}
    for label, module in (("legacy", LEGACY_MODULE), ("linkml", LINKML_MODULE)):
        work = tmp_path / f"work_{label}"
        shutil.copytree(src, work)
        proc = _run(module, build_args(work))
        assert proc.returncode == 0, (
            f"{label} converter failed (rc={proc.returncode}):\n"
            f"--- stderr ---\n{proc.stderr}\n--- stdout ---\n{proc.stdout}"
        )
        out = work / output_rel
        assert out.exists() and out.stat().st_size > 0, (
            f"{label} produced no Turtle output at {out}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
        results[label] = out

    equal, legacy_only, linkml_only = compare(results["legacy"], results["linkml"])
    assert equal, (
        "typed-shape divergence between legacy and LinkML csv2nidm output:\n"
        + format_diff(legacy_only, linkml_only)
    )


def _build_base_nidm(tmp_path: Path) -> Path:
    """Build a base assessment NIDM file (used by the ADD-to-existing mode) with
    one tool, so both add-runs start from an identical on-disk base.  Returns the
    path to the produced Turtle file."""
    build = tmp_path / "base_build"
    build.mkdir()
    csv = _write_csv(
        build / "base.csv",
        ["participant_id"],
        [["sub-01"], ["sub-02"], ["sub-03"]],
    )
    jmap = _write_covering_map(
        build / "map.json",
        source="base.csv",
        variables=["participant_id"],
        id_var="participant_id",
    )
    base = build / "base.ttl"
    # Built with the LinkML tool; the SAME bytes are then copied to both tools'
    # work dirs, so the add-run comparison is fair regardless of which tool built
    # the base.
    proc = _run(
        LINKML_MODULE,
        ["-csv", str(csv), "-json_map", str(jmap), "-no_concepts", "-out", str(base)],
    )
    assert proc.returncode == 0 and base.exists(), (
        "failed to build base NIDM file for add-to-existing mode:\n"
        f"--- stderr ---\n{proc.stderr}\n--- stdout ---\n{proc.stdout}"
    )
    return base


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def test_csv2nidm_fresh_assessment_parity(tmp_path: Path):
    """Mode 1: fresh assessment file from a CSV with participant_id + a numeric
    and a string assessment column, 3 rows."""
    src = tmp_path / "src"
    src.mkdir()
    _write_csv(
        src / "data.csv",
        ["participant_id", "age", "group"],
        [
            ["sub-01", 25, "control"],
            ["sub-02", 30, "patient"],
            ["sub-03", 22, "control"],
        ],
    )
    _write_covering_map(
        src / "map.json",
        source="data.csv",
        variables=["participant_id", "age", "group"],
        id_var="participant_id",
    )

    def build_args(work: Path):
        return [
            "-csv",
            str(work / "data.csv"),
            "-json_map",
            str(work / "map.json"),
            "-no_concepts",
            "-out",
            str(work / "out.ttl"),
        ]

    _run_both_and_assert(src, tmp_path, build_args, "out.ttl")


def test_csv2nidm_add_to_existing_parity(tmp_path: Path):
    """Mode 2: append assessment data to an existing NIDM file.  Both tools run
    ``-nidm`` (which rewrites the file in place + a .bak); the compared output is
    the mutated base copy, not any ``-out`` file (both tools ignore ``-out`` on
    the add path)."""
    base = _build_base_nidm(tmp_path)

    src = tmp_path / "src"
    src.mkdir()
    _write_csv(
        src / "more.csv",
        ["participant_id", "age"],
        [["sub-01", 25], ["sub-02", 30], ["sub-03", 22]],
    )
    _write_covering_map(
        src / "map2.json",
        source="more.csv",
        variables=["participant_id", "age"],
        id_var="participant_id",
    )
    # Each tool mutates its own copy of the base file in place.
    shutil.copy2(base, src / "base.ttl")

    def build_args(work: Path):
        return [
            "-csv",
            str(work / "more.csv"),
            "-json_map",
            str(work / "map2.json"),
            "-nidm",
            str(work / "base.ttl"),
            "-no_concepts",
        ]

    _run_both_and_assert(src, tmp_path, build_args, "base.ttl")


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SANCTIONED DIVERGENCE (project-lead decision): csv2nidm -derivative "
        "intentionally uses the modern nidm:Derivative / nidm:DerivativeObject "
        "model, whereas legacy used nidm:AcquisitionObject + nidm:SoftwareAgent. "
        "No provenance is lost -- the nidm:SoftwareAgent (title/description/"
        "hasVersion/URL) plus cmdline/platform are all preserved on the Derivative "
        "-- only the container node type differs. strict=True so this alerts us if "
        "the derivative output ever silently reverts to matching legacy. See "
        "docs/source/developer_manual.rst 'Known legacy divergences'."
    ),
)
def test_csv2nidm_derivative_freshfile_parity(tmp_path: Path):
    """Mode 3: fresh-file derivative build (``-derivative`` + ``-out``, no
    ``-nidm``).  The input CSV must carry ses/task/run/source_url (dropped before
    mapping), and the software-metadata CSV carries the 7 required columns.

    This is an EXPECTED divergence: legacy modeled derivatives as
    nidm:AcquisitionObject + nidm:SoftwareAgent; the LinkML port
    (``csv2nidm_derivative_project``) uses nidm:Derivative / nidm:DerivativeObject
    (the intended modern model) while preserving all software provenance.  Marked
    xfail(strict=True) so a silent revert to the legacy model is caught."""
    src = tmp_path / "src"
    src.mkdir()
    _write_csv(
        src / "deriv.csv",
        ["participant_id", "ses", "task", "run", "source_url", "fa"],
        [
            ["sub-01", "1", "rest", "1", "http://example.org/d1", 0.7],
            ["sub-02", "1", "rest", "1", "http://example.org/d2", 0.6],
        ],
    )
    # Only participant_id + the measure column (fa) need mapping; the structural
    # ses/task/run/source_url columns are dropped before map_variables_to_terms.
    _write_covering_map(
        src / "map.json",
        source="deriv.csv",
        variables=["participant_id", "fa"],
        id_var="participant_id",
    )
    _write_software_metadata(src / "software.csv")

    def build_args(work: Path):
        return [
            "-csv",
            str(work / "deriv.csv"),
            "-json_map",
            str(work / "map.json"),
            "-derivative",
            str(work / "software.csv"),
            "-no_concepts",
            "-out",
            str(work / "out.ttl"),
        ]

    _run_both_and_assert(src, tmp_path, build_args, "out.ttl")
