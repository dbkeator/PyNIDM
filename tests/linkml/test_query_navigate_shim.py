"""
Tests for the transitional shim modules
``nidm.linkml.experiment.query`` and ``nidm.linkml.experiment.navigate``.

Verifies:
  * Common public names are importable from the new namespace.
  * Each re-exported function is the SAME callable as the one on the
    legacy module (identity check via ``is``, not just same-name).
  * A small set of canonical queries actually runs against a fixture
    and returns the expected shape (URIRefs, DataFrames, etc.).
"""
from __future__ import annotations
from pathlib import Path
import pytest
from rdflib import URIRef
from nidm.experiment import Navigate as _legacy_navigate
from nidm.experiment import Query as _legacy_query
from nidm.linkml.experiment import navigate as new_navigate
from nidm.linkml.experiment import query as new_query

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = (
    REPO_ROOT / "tests" / "experiment" / "data" / "read_nidm" / "nidm_w_provenance.ttl"
)


# ---------------------------------------------------------------------------
# Identity: every shim-re-exported name points at the same callable as
# the legacy module's name.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "sparql_query_nidm",
        "GetProjectsUUID",
        "GetParticipantIDs",
        "GetMergedGraph",
        "GetProjectsMetadata",
        "GetDataElements",
        "URITail",
        "trimWellKnownURIPrefix",
        "expandNIDMAbbreviation",
    ],
)
def test_query_shim_re_exports_identical_callable(name):
    assert hasattr(
        new_query, name
    ), f"nidm.linkml.experiment.query missing expected name {name!r}"
    assert getattr(new_query, name) is getattr(
        _legacy_query, name
    ), f"{name!r} differs between new and legacy modules"


@pytest.mark.parametrize(
    "name",
    [
        "getProjects",
        "getSessions",
        "getAcquisitions",
        "getSubjects",
        "getSubjectUUIDsfromID",
        "getSubjectIDfromUUID",
        "getActivities",
        "getActivityData",
        "GetProjectAttributes",
        "GetAllPredicates",
        "GetDataelements",
        "GetDataelementDetails",
    ],
)
def test_navigate_shim_re_exports_identical_callable(name):
    assert hasattr(
        new_navigate, name
    ), f"nidm.linkml.experiment.navigate missing expected name {name!r}"
    assert getattr(new_navigate, name) is getattr(
        _legacy_navigate, name
    ), f"{name!r} differs between new and legacy modules"


# ---------------------------------------------------------------------------
# __all__ exposes the same surface
# ---------------------------------------------------------------------------


def test_query_all_matches_legacy_public_surface():
    """__all__ should mirror the legacy module's public name set."""
    expected = {name for name in dir(_legacy_query) if not name.startswith("_")}
    assert set(new_query.__all__) == expected


def test_navigate_all_matches_legacy_public_surface():
    expected = {name for name in dir(_legacy_navigate) if not name.startswith("_")}
    assert set(new_navigate.__all__) == expected


# ---------------------------------------------------------------------------
# End-to-end smoke: actually run a query through the shim
# ---------------------------------------------------------------------------


def test_get_projects_uuid_via_shim_returns_uris():
    """The shim is transparent -- this should produce the same result
    as calling the legacy module directly."""
    if not FIXTURE.exists():
        pytest.skip(f"fixture {FIXTURE} not available")

    uuids = new_query.GetProjectsUUID([str(FIXTURE)])
    assert isinstance(uuids, list)
    assert len(uuids) >= 1
    for u in uuids:
        assert isinstance(u, URIRef)


def test_sparql_query_nidm_via_shim_returns_dataframe():
    if not FIXTURE.exists():
        pytest.skip(f"fixture {FIXTURE} not available")

    sparql = """
        PREFIX nidm: <http://purl.org/nidash/nidm#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT DISTINCT ?p
        WHERE { ?p rdf:type nidm:Project }
    """
    df = new_query.sparql_query_nidm([str(FIXTURE)], sparql)
    # Returns a pandas DataFrame with at least one row.
    assert len(df) >= 1


def test_get_merged_graph_via_shim_returns_rdflib_graph():
    if not FIXTURE.exists():
        pytest.skip(f"fixture {FIXTURE} not available")

    from rdflib import Graph

    g = new_query.GetMergedGraph([str(FIXTURE)])
    assert isinstance(g, Graph)
    assert len(g) > 0


# ---------------------------------------------------------------------------
# Both names importable from the package
# ---------------------------------------------------------------------------


def test_query_and_navigate_importable_from_package():
    """`from nidm.linkml.experiment import query, navigate` should work."""
    from nidm.linkml.experiment import navigate as n
    from nidm.linkml.experiment import query as q

    assert q is new_query
    assert n is new_navigate
