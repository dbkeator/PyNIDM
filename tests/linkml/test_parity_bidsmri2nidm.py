"""Legacy-vs-LinkML graph-parity gate ("Part B") for ``bidsmri2nidm``.

This test builds small BIDS fixtures, runs BOTH the legacy prov-toolbox
converter and the LinkML converter on the *same* input via ``subprocess``, and
asserts the two outputs are **typed-shape equal** (using the proven comparator
in :mod:`scripts.parity_compare`).  It exists because a ``--per_subject``
regression -- where an un-padded ``participants.tsv`` ``participant_id`` failed
to match a zero-padded BIDS subject directory, silently dropping the whole
participants.tsv provenance in per-subject mode -- shipped uncaught.  The gate
covers single-file mode, ``--per_subject`` mode, and the exact ABIDE
leading-zero-mismatch case, so any future divergence in any mode fails here.

Skip semantics
--------------
The gate only runs in an environment where BOTH converters import (the parity
env with the ``[legacy]`` extra installed).  A plain LinkML env has no legacy
``nidm.experiment.tools.bidsmri2nidm`` / ``prov`` and skips cleanly at module
load rather than erroring.

Both converters are invoked identically::

    python -m nidm.experiment.tools.bidsmri2nidm        -d <dir> -json_map <m> -no_concepts -o <out> [--per_subject]
    python -m nidm.linkml.experiment.tools.bidsmri2nidm -d <dir> -json_map <m> -no_concepts -o <out> [--per_subject]

The LinkML module is ``-m``-runnable (it has an ``if __name__ == "__main__":``
guard that calls ``main()``), so we invoke it by module exactly like the legacy
tool -- no need to fall back to the ``bidsmri2nidm`` console script.
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
    import nidm.experiment.tools.bidsmri2nidm  # noqa: F401
except Exception as exc:  # pragma: no cover -- exercised only in linkml-only env
    pytest.skip(
        f"legacy bidsmri2nidm unavailable ({exc}); parity gate needs the "
        "[legacy] extra",
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

LEGACY_MODULE = "nidm.experiment.tools.bidsmri2nidm"
LINKML_MODULE = "nidm.linkml.experiment.tools.bidsmri2nidm"


# ---------------------------------------------------------------------------
# Fixture builders (self-contained; mirror tests/linkml/test_bidsmri2nidm_slim.py)
# ---------------------------------------------------------------------------


def _write_dataset_description(
    bids_root: Path,
    *,
    name: str = "Parity Test Dataset",
    bids_version: str = "1.5.0",
    license_: str = "CC0",
) -> None:
    payload = {
        "Name": name,
        "BIDSVersion": bids_version,
        "License": license_,
        "Authors": ["J. Smith", "A. Doe"],
    }
    (bids_root / "dataset_description.json").write_text(json.dumps(payload))


def _write_t1w_scan(bids_root: Path, subject: str = "sub-01") -> Path:
    anat = bids_root / subject / "anat"
    anat.mkdir(parents=True, exist_ok=True)
    scan = anat / f"{subject}_T1w.nii.gz"
    # Non-empty + deterministic: both tools hash identical bytes, so the SHA-512
    # triples match regardless of how each tool treats empty files (avoids a
    # spurious divergence that an empty placeholder could introduce).
    scan.write_bytes(b"T1w parity fixture content\n")
    return scan


def _write_bold_scan(bids_root: Path, subject: str = "sub-01") -> Path:
    func = bids_root / subject / "func"
    func.mkdir(parents=True, exist_ok=True)
    scan = func / f"{subject}_task-rest_bold.nii.gz"
    scan.write_bytes(b"bold parity fixture content\n")
    return scan


def _write_participants_tsv(bids_root: Path, rows: str) -> Path:
    target = bids_root / "participants.tsv"
    target.write_text(rows)
    return target


def _write_covering_map(path: Path, variables: list) -> Path:
    """Write a NIDM-format JSON data dictionary keyed by ``DD(...)`` tuples so
    ``map_variables_to_terms`` never falls through to an interactive prompt.

    The assessment source is ``participants.tsv`` -- that is the
    ``assessment_name`` both converters pass into ``map_variables_to_terms``
    when building the participants CDE, so the keys must match on both sides.
    ``participant_id`` is BIDS-known (skipped by both tools) but is included for
    good measure; ``sex`` is the genuinely-mapped column that would otherwise
    prompt.
    """
    from nidm.linkml.core import constants as _C

    isabout = {
        "participant_id": [{"@id": str(_C.NIDM_SUBJECTID), "label": "subject_id"}],
    }
    payload = {}
    for var in variables:
        payload[str(DD(source="participants.tsv", variable=var))] = {
            "label": var,
            "description": f"{var} value",
            "source_variable": var,
            "isAbout": isabout.get(
                var, [{"@id": f"http://example.org/{var}", "label": var}]
            ),
        }
    path.write_text(json.dumps(payload))
    return path


def _build_basic_fixture(root: Path) -> None:
    """T1w + bold for sub-01, with a participants.tsv carrying one covered var."""
    _write_dataset_description(root)
    _write_t1w_scan(root, subject="sub-01")
    _write_bold_scan(root, subject="sub-01")
    _write_participants_tsv(root, "participant_id\tsex\nsub-01\tM\n")


def _build_abide_padding_fixture(root: Path) -> None:
    """The exact bug just fixed: zero-padded BIDS subject directory
    (``sub-0051456``) but an UN-padded ``participant_id`` (``51456``) in
    participants.tsv.  The leading-zero-tolerant match must make both tools
    process the row identically in ``--per_subject`` mode."""
    _write_dataset_description(root)
    _write_t1w_scan(root, subject="sub-0051456")  # zero-padded directory
    _write_bold_scan(root, subject="sub-0051456")
    _write_participants_tsv(root, "participant_id\tsex\n51456\tM\n")  # un-padded id


# ---------------------------------------------------------------------------
# Runner + parity assertion
# ---------------------------------------------------------------------------


def _run(module: str, bids_dir: Path, json_map: Path, out: Path, per_subject: bool):
    """Run a bidsmri2nidm converter via ``-m`` and return the CompletedProcess.

    ``stdin`` is closed so that if either tool tries to prompt (i.e. the
    covering map failed to cover a column) it errors instead of hanging.
    """
    cmd = [
        sys.executable,
        "-m",
        module,
        "-d",
        str(bids_dir),
        "-json_map",
        str(json_map),
        "-no_concepts",
        "-o",
        str(out),
    ]
    if per_subject:
        cmd.append("--per_subject")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=600,
    )


def _collect_outputs(out: Path, per_subject: bool) -> dict:
    """Map a stable relative key -> produced Turtle file for a converter run."""
    if not per_subject:
        return {"nidm.ttl": out}
    # --per_subject writes <out>/sub-<id>/nidm.ttl for every subject.
    return {str(p.relative_to(out)): p for p in sorted(out.glob("sub-*/nidm.ttl"))}


def _run_both_and_assert(src: Path, json_map: Path, tmp_path: Path, per_subject: bool):
    """Run legacy + LinkML on identical copies of *src* and assert typed-shape
    equality of every produced Turtle file."""
    results = {}
    for label, module in (("legacy", LEGACY_MODULE), ("linkml", LINKML_MODULE)):
        # Each tool gets its OWN copy: map_variables_to_terms may write a
        # participants.json into the input dir, which would otherwise leak a
        # sidecar into the second tool's run and cause a false divergence.
        tool_dir = tmp_path / f"in_{label}"
        shutil.copytree(src, tool_dir)
        out = tmp_path / (f"out_{label}" if per_subject else f"out_{label}.ttl")
        proc = _run(module, tool_dir, json_map, out, per_subject)
        assert proc.returncode == 0, (
            f"{label} converter failed (rc={proc.returncode}):\n"
            f"--- stderr ---\n{proc.stderr}\n--- stdout ---\n{proc.stdout}"
        )
        outputs = _collect_outputs(out, per_subject)
        assert outputs, f"{label} produced no Turtle output under {out}"
        results[label] = outputs

    legacy_out, linkml_out = results["legacy"], results["linkml"]
    assert set(legacy_out) == set(linkml_out), (
        "legacy and LinkML produced different per-subject file sets:\n"
        f"  legacy: {sorted(legacy_out)}\n  linkml: {sorted(linkml_out)}"
    )
    for rel in sorted(legacy_out):
        equal, legacy_only, linkml_only = compare(legacy_out[rel], linkml_out[rel])
        assert equal, (
            f"typed-shape divergence between legacy and LinkML in {rel}:\n"
            + format_diff(legacy_only, linkml_only)
        )


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    [
        "single",  # 1. single-file mode, T1w + bold + covered participants var
        "per_subject",  # 2. same fixture in --per_subject mode (the regressed case)
        "abide_padding",  # 3. --per_subject, padded dir vs un-padded participant_id
    ],
)
def test_bidsmri2nidm_legacy_vs_linkml_parity(tmp_path: Path, case: str):
    src = tmp_path / "bids"
    src.mkdir()
    if case == "abide_padding":
        _build_abide_padding_fixture(src)
    else:
        _build_basic_fixture(src)

    json_map = _write_covering_map(tmp_path / "map.json", ["participant_id", "sex"])
    per_subject = case in ("per_subject", "abide_padding")
    _run_both_and_assert(src, json_map, tmp_path, per_subject)
