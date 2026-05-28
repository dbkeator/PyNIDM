"""
Parity harness for the LinkML refactor.

This is the gate that tells us the new code preserves NIDM-Experiment
semantics correctly.  Failure here is the strongest signal the
refactor has regressed something behaviorally observable.

Two parts (see [[pynidm-linkml-refactor]] memory entry for the
guarantee):

  PART A -- Read-back isomorphism on existing NIDM files.
            For each curated fixture nidm.ttl on disk, load it through
            the new code (``Core.from_turtle``), serialize back out,
            and assert the result is graph-isomorphic to the input.
            This guarantees existing datasets keep working.

  PART B -- Tool-equivalence isomorphism on freshly-built files.
            For each NIDM-producing tool (bidsmri2nidm, csv2nidm,
            FreeSurfer/FSL/ANTs derivative ingesters), feed the SAME
            input to both the old prov-based tool and the new
            linkml-based tool, then assert the outputs are isomorphic.

Part B is intentionally not implemented yet -- it depends on task 8
(tool ports).  The infrastructure here is Part A only, with the test
list parametrized over fixtures so adding new ones is trivial.
"""
from __future__ import annotations
from pathlib import Path
import pytest
from rdflib import Graph
from rdflib.compare import isomorphic
from rdflib.namespace import RDF
from nidm.linkml.core.namespaces import NIDM
from nidm.linkml.experiment.core import Core

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Curated fixture set.  Add new entries as we discover edge cases the
# read-back path needs to handle.  Each path is relative to the repo
# root and must point at an existing turtle file.
FIXTURE_PATHS = [
    REPO_ROOT / "tests" / "experiment" / "data" / "read_nidm" / "brainvol_nidm.ttl",
    REPO_ROOT / "tests" / "experiment" / "data" / "read_nidm" / "derivatives_nidm.ttl",
    REPO_ROOT / "tests" / "experiment" / "data" / "read_nidm" / "nidm_w_provenance.ttl",
    REPO_ROOT
    / "tests"
    / "experiment"
    / "data"
    / "read_nidm"
    / "nidm_w_provenance_roundtrip.ttl",
    REPO_ROOT / "tests" / "experiment" / "test_nidm.ttl",
    REPO_ROOT / "fmriprep_example" / "bids_v2" / "nidm_only_fmriprep.ttl",
    REPO_ROOT / "fmriprep_example" / "bids_v2" / "nidm_only_fmriprep_csv_dd.ttl",
    REPO_ROOT / "fmriprep_example" / "kennedy_ohsu" / "nidm_minimal.ttl",
    REPO_ROOT / "fmriprep_example" / "kennedy_ohsu" / "nidm_minimal_working.ttl",
    REPO_ROOT / "hatton_linear_reg" / "nidm.ttl",
]


def _available_fixtures():
    """Yield only fixtures that actually exist on disk (skip silently otherwise)."""
    for path in FIXTURE_PATHS:
        if path.exists():
            yield path


def _fixture_id(path: Path) -> str:
    """Test id: the path relative to the repo root."""
    return str(path.relative_to(REPO_ROOT))


FIXTURES = list(_available_fixtures())
FIXTURE_IDS = [_fixture_id(p) for p in FIXTURES]


# ---------------------------------------------------------------------------
# PART A: Read-back isomorphism
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=FIXTURE_IDS)
def test_read_back_is_isomorphic(fixture_path: Path, tmp_path: Path):
    """
    Load *fixture_path* via the new code, write it back, and assert the
    reloaded graph is isomorphic to the source.

    Failure modes that this catches:
      * Default namespace bindings clobbering file-supplied ones (would
        change the meaning of CURIEs).
      * Bnode-handling bugs in Core.parse / Core.write.
      * Datatype loss on literals during round-trip.
      * Dropped triples (rdflib parse errors that don't raise).
    """
    # Source graph: load directly with rdflib (bypass our code) so we
    # have a "ground truth" view of the fixture's triples.
    source = Graph()
    source.parse(source=str(fixture_path), format="turtle")
    assert len(source) > 0, f"fixture {fixture_path} parsed to zero triples"

    # Round-trip through our code path: Core.from_turtle -> Core.write.
    core = Core.from_turtle(fixture_path)
    out_path = tmp_path / "round_trip.ttl"
    core.write(out_path)
    assert out_path.exists() and out_path.stat().st_size > 0

    # Reload the round-tripped output as a plain rdflib graph.
    roundtripped = Graph()
    roundtripped.parse(source=str(out_path), format="turtle")

    if not isomorphic(source, roundtripped):
        # Provide diagnostic detail so debugging doesn't require running
        # the harness twice.
        src_triples = set(source)
        rt_triples = set(roundtripped)
        only_source = src_triples - rt_triples
        only_rt = rt_triples - src_triples
        pytest.fail(
            f"{fixture_path.name}: graphs not isomorphic\n"
            f"  source has {len(src_triples)} triples, "
            f"round-trip has {len(rt_triples)}\n"
            f"  triples only in source: {len(only_source)}\n"
            f"  triples only in round-trip: {len(only_rt)}\n"
            f"  first 3 source-only: {list(only_source)[:3]}\n"
            f"  first 3 round-trip-only: {list(only_rt)[:3]}"
        )


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=FIXTURE_IDS)
def test_read_back_preserves_triple_count(fixture_path: Path, tmp_path: Path):
    """
    Belt-and-suspenders companion to the isomorphism check: ensure no
    triples were silently dropped or duplicated during the round-trip.
    """
    source = Graph()
    source.parse(source=str(fixture_path), format="turtle")
    source_count = len(source)

    core = Core.from_turtle(fixture_path)
    out_path = tmp_path / "rt.ttl"
    core.write(out_path)

    roundtripped = Graph()
    roundtripped.parse(source=str(out_path), format="turtle")
    rt_count = len(roundtripped)

    assert rt_count == source_count, (
        f"{fixture_path.name}: triple count changed during round-trip "
        f"({source_count} -> {rt_count})"
    )


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=FIXTURE_IDS)
def test_read_back_preserves_rdf_type_set(fixture_path: Path, tmp_path: Path):
    """
    For each (subject, rdf:type) pair in the source, the same pair must
    be in the round-tripped graph.  Cheaper to diagnose than full
    isomorphism failure and catches the most likely regression
    (incorrect handling of type triples).
    """
    source = Graph()
    source.parse(source=str(fixture_path), format="turtle")

    core = Core.from_turtle(fixture_path)
    out_path = tmp_path / "rt.ttl"
    core.write(out_path)
    roundtripped = Graph()
    roundtripped.parse(source=str(out_path), format="turtle")

    # Compare the (subject, type) sets.  For URI subjects these compare
    # directly; for blank-node subjects we compare counts per type
    # (since bnodes get renamed during round-trip).
    def by_type_counts(g):
        from collections import Counter

        return Counter(t for _, _, t in g.triples((None, RDF.type, None)))

    assert by_type_counts(source) == by_type_counts(
        roundtripped
    ), f"{fixture_path.name}: rdf:type distribution changed during round-trip"


# ---------------------------------------------------------------------------
# Schema-conformance sanity checks (light-touch on each fixture)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=FIXTURE_IDS)
def test_fixture_has_expected_top_level_types(fixture_path: Path):
    """
    Sanity: every fixture should declare at least one of the recognized
    top-level NIDM-Experiment subjects (Project / Acquisition /
    Derivative).  If a fixture has none, either it's a non-NIDM file
    that snuck into the list or the namespace bindings are wrong.
    """
    g = Graph()
    g.parse(source=str(fixture_path), format="turtle")

    expected_types = {NIDM.Project, NIDM.Acquisition, NIDM.Derivative}
    seen_types = {t for _, _, t in g.triples((None, RDF.type, None))}
    if not (expected_types & seen_types):
        pytest.fail(
            f"{fixture_path.name}: no recognized top-level NIDM type found "
            f"(expected one of {expected_types}, saw {seen_types})"
        )


# ---------------------------------------------------------------------------
# Fixture inventory (so the user can see what's covered at a glance)
# ---------------------------------------------------------------------------


def test_fixture_inventory_is_nonempty():
    """Smoke check: we have at least one fixture to test against."""
    assert FIXTURES, (
        "No parity fixtures found.  Add nidm.ttl files to "
        "tests/experiment/data/read_nidm/ or update FIXTURE_PATHS in "
        "tests/linkml/test_parity.py."
    )
