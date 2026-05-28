"""
Tests for the ported NIDM URI constants in ``nidm.linkml.core.constants``
and ``nidm.linkml.core.bids_constants``.

Verifies:
  * Every constant is now a :class:`rdflib.URIRef` (not prov-toolbox's
    QualifiedName).
  * The URI values match the legacy ``nidm.core.Constants`` URIs
    bit-for-bit -- since ``QualifiedName.__str__`` returns the same
    URI string that ``URIRef.__str__`` does, this catches typo
    regressions in the port.
  * The BIDS_Constants port preserves the same dict shape (keys +
    target URIs).
"""
from __future__ import annotations
import pytest
from rdflib import URIRef
from nidm.core import BIDS_Constants as _legacy_bids
from nidm.core import Constants as _legacy
from nidm.linkml.core import bids_constants as new_bids
from nidm.linkml.core import constants as new

# ---------------------------------------------------------------------------
# Type check: every ported constant should be a URIRef
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        # NIDM-Experiment core
        "NIDM_PROJECT",
        "NIDM_SESSION",
        "NIDM_ACQUISITION_ACTIVITY",
        "NIDM_ACQUISITION_ENTITY",
        "NIDM_ACQUISITION_MODALITY",
        "NIDM_ASSESSMENT_ACQUISITION",
        "NIDM_ASSESSMENT_ENTITY",
        "NIDM_DEMOGRAPHICS_ENTITY",
        "NIDM_DATAELEMENT",
        "NIDM_PROJECT_NAME",
        "NIDM_PROJECT_DESCRIPTION",
        "NIDM_PROJECT_LICENSE",
        "NIDM_AUTHOR",
        "NIDM_FILENAME",
        "NIDM_FILE",
        "NIDM_SUBJECTID",
        # MRI scan types
        "NIDM_MRI",
        "NIDM_PET",
        "NIDM_MRI_T1",
        "NIDM_MRI_T2",
        "NIDM_MRI_T2_STAR",
        "NIDM_MRI_DWI_BVAL",
        "NIDM_MRI_DWI_BVEC",
        "NIDM_MRI_ANATOMIC_SCAN",
        "NIDM_MRI_FUNCTION_SCAN",
        # Roles
        "NIDM_PI",
        "NIDM_COI",
        "NIDM_PARTICIPANT",
        # Demographics
        "NIDM_AGE",
        "NIDM_SEX",
        "NIDM_GENDER",
        "NIDM_HANDEDNESS",
        "NIDM_DIAGNOSIS",
        "NIDM_FAMILY_NAME",
        "NIDM_GIVEN_NAME",
        # NIDM-Results sampling
        "NIDM_THRESHOLD",
        "NIDM_P_VALUE",
        "NIDM_CLUSTER",
        # Crypto / DataLad / DOI / Funding
        "CRYPTO_SHA512",
        "DATALAD_LOCATION",
        "NIDM_DOI",
        "NIDM_FUNDING",
        "NIDM_ACKNOWLEDGEMENTS",
        # OBO / STATO
        "OBO_STATISTIC",
        "STATO_OLS",
        "STATO_GLS",
        "STATO_TSTATISTIC",
        "STATO_ZSTATISTIC",
        # SCR software
        "SPM_SOFTWARE",
        "FSL_SOFTWARE",
    ],
)
def test_ported_constant_is_uriref(name):
    val = getattr(new, name)
    assert isinstance(val, URIRef), f"{name} is {type(val).__name__}, expected URIRef"


# ---------------------------------------------------------------------------
# URI parity: every ported constant should have the SAME URI string as the
# legacy constant.
# ---------------------------------------------------------------------------


def _legacy_uri(value):
    """
    Extract the full URI string from a legacy constant.  Legacy
    constants are either ``prov.model.QualifiedName`` (which
    stringifies as the CURIE ``nidm:Project``, but exposes the full
    URI via ``.uri``) or already a URI-like value (which stringifies
    to the URI).  Either way we want the URI for parity comparison.
    """
    uri_attr = getattr(value, "uri", None)
    return str(uri_attr) if uri_attr is not None else str(value)


@pytest.mark.parametrize(
    "name",
    [
        "NIDM_PROJECT",
        "NIDM_SESSION",
        "NIDM_ACQUISITION_ACTIVITY",
        "NIDM_ACQUISITION_ENTITY",
        "NIDM_ACQUISITION_MODALITY",
        "NIDM_ASSESSMENT_ACQUISITION",
        "NIDM_ASSESSMENT_ENTITY",
        "NIDM_DEMOGRAPHICS_ENTITY",
        "NIDM_DATAELEMENT",
        "NIDM_PROJECT_NAME",
        "NIDM_PROJECT_DESCRIPTION",
        "NIDM_PROJECT_LICENSE",
        "NIDM_AUTHOR",
        "NIDM_FILENAME",
        "NIDM_FILE",
        "NIDM_SUBJECTID",
        "NIDM_MRI",
        "NIDM_PET",
        "NIDM_MRI_T1",
        "NIDM_MRI_T2",
        "NIDM_MRI_T2_STAR",
        "NIDM_MRI_DWI_BVAL",
        "NIDM_MRI_DWI_BVEC",
        "NIDM_PI",
        "NIDM_COI",
        "NIDM_PARTICIPANT",
        "NIDM_AGE",
        "NIDM_SEX",
        "NIDM_GENDER",
        "NIDM_HANDEDNESS",
        "NIDM_DIAGNOSIS",
        "NIDM_FAMILY_NAME",
        "NIDM_GIVEN_NAME",
        "NIDM_THRESHOLD",
        "NIDM_P_VALUE",
        "NIDM_CLUSTER",
        "CRYPTO_SHA512",
        "DATALAD_LOCATION",
        "NIDM_DOI",
        "NIDM_FUNDING",
        "NIDM_ACKNOWLEDGEMENTS",
        "OBO_STATISTIC",
        "STATO_OLS",
        "STATO_GLS",
        "SPM_SOFTWARE",
        "FSL_SOFTWARE",
    ],
)
def test_ported_constant_uri_matches_legacy(name):
    new_val = getattr(new, name)
    legacy_val = getattr(_legacy, name)
    assert str(new_val) == _legacy_uri(legacy_val), (
        f"{name}: new={new_val!r}, legacy_uri={_legacy_uri(legacy_val)!r}, "
        f"legacy_repr={legacy_val!r}"
    )


# ---------------------------------------------------------------------------
# Plain-string constants (REST API keys, isAbout URIs, CDE file locations)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "NIDM_REST_NUM_SUBJECTS",
        "NIDM_REST_MAX_AGE",
        "NIDM_REST_MIN_AGE",
        "NIDM_REST_GENDER",
        "NIDM_REST_AGE",
        "NIDM_IS_ABOUT_AGE",
        "NIDM_IS_ABOUT_HANDEDNESS",
        "NIDM_IS_ABOUT_GENDER",
    ],
)
def test_plain_string_constants_match_legacy(name):
    assert getattr(new, name) == getattr(_legacy, name)


def test_cde_file_locations_match():
    assert new.CDE_FILE_LOCATIONS == _legacy.CDE_FILE_LOCATIONS


def test_dd_namedtuple_compatibility():
    """Legacy ``Constants.DD`` is a namedtuple used by CSV mappers."""
    dd = new.DD(source="x.csv", variable="age")
    assert dd.source == "x.csv"
    assert dd.variable == "age"


# ---------------------------------------------------------------------------
# Dropped: NIDMDocument, q_graph, *_QNAME, PROVONE_*, nidm_experiment_terms
# (deliberately not ported).  Verify they are NOT present in the new module
# so anyone refactoring against the new path gets a clear ImportError.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "NIDMDocument",  # prov.ProvDocument subclass
        "q_graph",  # prov-toolbox internal
        "OBO_STATISTIC_QNAME",  # prov-toolbox qname helper output
        "PROVONE_N_MAP",  # ProvONE prov-toolbox compat
        "PROVONE_RECORD_ATTRIBUTES",
        "nidm_experiment_terms",  # legacy JSON-LD helper list
    ],
)
def test_explicitly_dropped_names_are_absent(name):
    assert not hasattr(
        new, name
    ), f"Did not expect {name!r} on the new constants module"


# ---------------------------------------------------------------------------
# BIDS_Constants port: same dict shape, same value URIs
# ---------------------------------------------------------------------------


def test_dataset_description_keys_match():
    assert set(new_bids.dataset_description.keys()) == set(
        _legacy_bids.dataset_description.keys()
    )


def test_dataset_description_uris_match():
    for k, new_v in new_bids.dataset_description.items():
        legacy_v = _legacy_bids.dataset_description[k]
        assert str(new_v) == _legacy_uri(legacy_v), (
            f"BIDS dataset_description[{k!r}]: "
            f"new={new_v}, legacy_uri={_legacy_uri(legacy_v)}"
        )


def test_participants_keys_match():
    assert set(new_bids.participants.keys()) == set(_legacy_bids.participants.keys())


def test_scans_keys_match():
    assert set(new_bids.scans.keys()) == set(_legacy_bids.scans.keys())


def test_scans_uris_match():
    for k, new_v in new_bids.scans.items():
        legacy_v = _legacy_bids.scans[k]
        assert str(new_v) == _legacy_uri(legacy_v), (
            f"BIDS scans[{k!r}]: " f"new={new_v}, legacy_uri={_legacy_uri(legacy_v)}"
        )


def test_json_keys_match():
    assert set(new_bids.json_keys.keys()) == set(_legacy_bids.json_keys.keys())


def test_json_keys_uris_match():
    for k, new_v in new_bids.json_keys.items():
        legacy_v = _legacy_bids.json_keys[k]
        assert str(new_v) == _legacy_uri(legacy_v), (
            f"BIDS json_keys[{k!r}]: "
            f"new={new_v}, legacy_uri={_legacy_uri(legacy_v)}"
        )


# ---------------------------------------------------------------------------
# Round-trip usability: a ported constant works as an RDF predicate
# ---------------------------------------------------------------------------


def test_ported_constants_usable_as_graph_predicates():
    """Drop-in test: a ported constant works in graph.add()."""
    from rdflib import Graph, Literal

    g = Graph()
    subject = URIRef("http://example.org/proj")
    g.add((subject, new.NIDM_PROJECT_NAME, Literal("Test Project")))
    g.add((subject, new.NIDM_PROJECT_LICENSE, Literal("CC0")))
    assert (subject, new.NIDM_PROJECT_NAME, Literal("Test Project")) in g
    assert len(list(g.predicates(subject))) == 2
