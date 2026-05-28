"""
Tests for the slim BIDS->NIDM converter at
``nidm.linkml.experiment.tools.bidsmri2nidm``.

These exercise the end-to-end "real tool" path: build a minimal BIDS
dataset in a temp dir, run the slim converter, and verify the
resulting graph matches the expected wrapper-emitted shape.

These are NOT parity tests against the legacy bidsmri2nidm -- the
slim port intentionally drops features (CDE attachment, Interlex
mapping, git-annex sources, sidecar JSON descent, ...) so the
outputs won't be isomorphic.  See task 8 in the refactor plan for
the deferred-feature list.
"""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from rdflib import Graph
from rdflib.namespace import RDF
from nidm.linkml.core.namespaces import (
    BIDS,
    DCTYPES,
    NDAR,
    NFO,
    NIDM,
    PROV,
    SCHEMA,
    SIO,
)
from nidm.linkml.experiment.tools.bidsmri2nidm import bidsmri2project, main

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _write_dataset_description(
    bids_root: Path,
    *,
    name: str = "Test Dataset",
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
    scan.write_bytes(b"")  # empty placeholder is fine for slim tool
    return scan


def _write_bold_scan(bids_root: Path, subject: str = "sub-01") -> Path:
    func = bids_root / subject / "func"
    func.mkdir(parents=True, exist_ok=True)
    scan = func / f"{subject}_task-rest_bold.nii.gz"
    scan.write_bytes(b"")
    return scan


def _write_pet_scan(bids_root: Path, subject: str = "sub-01") -> Path:
    pet = bids_root / subject / "pet"
    pet.mkdir(parents=True, exist_ok=True)
    scan = pet / f"{subject}_pet.nii.gz"
    scan.write_bytes(b"")
    return scan


# ---------------------------------------------------------------------------
# Basic graph shape
# ---------------------------------------------------------------------------


def test_minimal_bids_produces_expected_top_level_subjects(tmp_path: Path):
    _write_dataset_description(tmp_path)
    _write_t1w_scan(tmp_path)

    project = bidsmri2project(tmp_path)
    g = project.graph

    # Exactly one Project subject.
    projects = list(g.subjects(RDF.type, NIDM.Project))
    assert len(projects) == 1
    # One Session.
    sessions = list(g.subjects(RDF.type, NIDM.Session))
    assert len(sessions) == 1
    # One Acquisition (carried by MRAcquisition specialization).
    acqs = list(g.subjects(RDF.type, NIDM.Acquisition))
    assert len(acqs) == 1
    # One AcquisitionObject.
    objs = list(g.subjects(RDF.type, NIDM.AcquisitionObject))
    assert len(objs) == 1
    # One Person.
    persons = list(g.subjects(RDF.type, PROV.Person))
    assert len(persons) == 1
    # One SoftwareAgent.
    agents = list(g.subjects(RDF.type, PROV.SoftwareAgent))
    assert len(agents) == 1
    # One Collection (bids:Dataset).
    collections = list(g.subjects(RDF.type, BIDS.Dataset))
    assert len(collections) == 1


def test_project_title_pulled_from_dataset_description(tmp_path: Path):
    _write_dataset_description(tmp_path, name="The ABIDE Imaging Project")
    _write_t1w_scan(tmp_path)
    project = bidsmri2project(tmp_path)
    titles = list(project.graph.objects(project.identifier, DCTYPES.title))
    assert [str(t) for t in titles] == ["The ABIDE Imaging Project"]


def test_collection_carries_bids_version_and_dataset_type(tmp_path: Path):
    _write_dataset_description(tmp_path, bids_version="1.6.0")
    _write_t1w_scan(tmp_path)
    project = bidsmri2project(tmp_path)
    g = project.graph

    # The Collection subject is the one typed bids:Dataset.
    collections = list(g.subjects(RDF.type, BIDS.Dataset))
    assert len(collections) == 1
    coll = collections[0]
    versions = list(g.objects(coll, BIDS.BIDSVersion))
    assert [str(v) for v in versions] == ["1.6.0"]
    # It's also prov:Collection + prov:Entity per the schema.
    coll_types = set(g.objects(coll, RDF.type))
    assert PROV.Collection in coll_types
    assert PROV.Entity in coll_types


# ---------------------------------------------------------------------------
# T1w scan -> MR / Anatomical / T1Weighted
# ---------------------------------------------------------------------------


def test_t1w_scan_emits_expected_modality_and_contrast(tmp_path: Path):
    _write_dataset_description(tmp_path)
    _write_t1w_scan(tmp_path)
    project = bidsmri2project(tmp_path)
    g = project.graph

    obj = list(g.subjects(RDF.type, NIDM.AcquisitionObject))[0]

    modalities = list(g.objects(obj, NIDM.hadAcquisitionModality))
    contrasts = list(g.objects(obj, NIDM.hadImageContrastType))
    usages = list(g.objects(obj, NIDM.hadImageUsageType))

    assert modalities == [NIDM.MagneticResonanceImaging]
    assert contrasts == [NIDM.T1Weighted]
    assert usages == [NIDM.Anatomical]


def test_t1w_filename_uses_bids_prefix(tmp_path: Path):
    _write_dataset_description(tmp_path)
    _write_t1w_scan(tmp_path)
    project = bidsmri2project(tmp_path)
    obj = list(project.graph.subjects(RDF.type, NIDM.AcquisitionObject))[0]
    filenames = list(project.graph.objects(obj, NFO.filename))
    assert len(filenames) == 1
    assert str(filenames[0]) == "bids::sub-01/anat/sub-01_T1w.nii.gz"


# ---------------------------------------------------------------------------
# BOLD fMRI scan -> Functional
# ---------------------------------------------------------------------------


def test_bold_scan_emits_functional_usage(tmp_path: Path):
    _write_dataset_description(tmp_path)
    _write_bold_scan(tmp_path)
    project = bidsmri2project(tmp_path)
    g = project.graph
    obj = list(g.subjects(RDF.type, NIDM.AcquisitionObject))[0]
    usages = list(g.objects(obj, NIDM.hadImageUsageType))
    assert usages == [NIDM.Functional]


# ---------------------------------------------------------------------------
# PET scan -> PET modality, no contrast/usage
# ---------------------------------------------------------------------------


def test_pet_scan_emits_pet_modality(tmp_path: Path):
    _write_dataset_description(tmp_path)
    _write_pet_scan(tmp_path)
    project = bidsmri2project(tmp_path)
    g = project.graph
    obj = list(g.subjects(RDF.type, NIDM.AcquisitionObject))[0]
    modalities = list(g.objects(obj, NIDM.hadAcquisitionModality))
    assert modalities == [NIDM.PositronEmissionTomography]


# ---------------------------------------------------------------------------
# Participant linkage via prov:qualifiedAssociation
# ---------------------------------------------------------------------------


def test_acquisition_is_linked_to_person_via_qualified_association(tmp_path: Path):
    _write_dataset_description(tmp_path)
    _write_t1w_scan(tmp_path)
    project = bidsmri2project(tmp_path)
    g = project.graph

    acq = list(g.subjects(RDF.type, NIDM.Acquisition))[0]
    person = list(g.subjects(RDF.type, PROV.Person))[0]

    # acq -> prov:qualifiedAssociation -> assoc
    assocs = list(g.objects(acq, PROV.qualifiedAssociation))
    assert len(assocs) == 1
    assoc = assocs[0]

    # assoc -> prov:agent -> person
    agents = list(g.objects(assoc, PROV.agent))
    assert agents == [person]

    # assoc -> prov:hadRole -> sio:Subject
    roles = list(g.objects(assoc, PROV.hadRole))
    assert roles == [SIO.Subject]


def test_person_carries_subject_id(tmp_path: Path):
    _write_dataset_description(tmp_path)
    _write_t1w_scan(tmp_path, subject="sub-0050002")
    project = bidsmri2project(tmp_path)
    g = project.graph
    person = list(g.subjects(RDF.type, PROV.Person))[0]
    ids = list(g.objects(person, NDAR.src_subject_id))
    assert [str(i) for i in ids] == ["sub-0050002"]


# ---------------------------------------------------------------------------
# Multiple subjects
# ---------------------------------------------------------------------------


def test_multiple_subjects_produce_distinct_sessions_and_persons(tmp_path: Path):
    _write_dataset_description(tmp_path)
    _write_t1w_scan(tmp_path, subject="sub-01")
    _write_t1w_scan(tmp_path, subject="sub-02")
    _write_t1w_scan(tmp_path, subject="sub-03")

    project = bidsmri2project(tmp_path)
    g = project.graph

    sessions = list(g.subjects(RDF.type, NIDM.Session))
    persons = list(g.subjects(RDF.type, PROV.Person))
    acqs = list(g.subjects(RDF.type, NIDM.Acquisition))

    assert len(sessions) == 3
    assert len(persons) == 3
    assert len(acqs) == 3


# ---------------------------------------------------------------------------
# Export provenance
# ---------------------------------------------------------------------------


def test_export_activity_records_software_agent(tmp_path: Path):
    _write_dataset_description(tmp_path)
    _write_t1w_scan(tmp_path)
    project = bidsmri2project(tmp_path)
    g = project.graph

    agents = list(g.subjects(RDF.type, PROV.SoftwareAgent))
    assert len(agents) == 1
    agent = agents[0]

    names = list(g.objects(agent, SCHEMA.name))
    assert [str(n) for n in names] == ["PyNIDM"]

    # An ExportActivity (a prov:Activity that is NOT also nidm:Acquisition
    # / nidm:Session / nidm:Project / nidm:Derivative) should reference it.
    exports = [s for s in g.subjects(PROV.wasAssociatedWith, agent)]
    assert len(exports) >= 1


# ---------------------------------------------------------------------------
# Output file written
# ---------------------------------------------------------------------------


def test_output_path_writes_turtle_file(tmp_path: Path):
    _write_dataset_description(tmp_path)
    _write_t1w_scan(tmp_path)
    out_path = tmp_path / "out.ttl"

    bidsmri2project(tmp_path, output_path=out_path)
    assert out_path.exists() and out_path.stat().st_size > 0

    # Round-trippable.
    reloaded = Graph()
    reloaded.parse(source=str(out_path), format="turtle")
    assert len(reloaded) > 0


# ---------------------------------------------------------------------------
# Custom project_uuid / dataset_uuid
# ---------------------------------------------------------------------------


def test_supplied_project_uuid_is_used(tmp_path: Path):
    _write_dataset_description(tmp_path)
    _write_t1w_scan(tmp_path)
    project = bidsmri2project(
        tmp_path, project_uuid="aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb"
    )
    assert "aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb" in str(project.identifier)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_missing_bids_dir_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        bidsmri2project(tmp_path / "nope")


def test_empty_bids_dir_still_emits_project(tmp_path: Path):
    """No dataset_description, no subjects -- should still produce a
    valid (if empty) Project + export-provenance graph."""
    project = bidsmri2project(tmp_path)
    g = project.graph
    assert len(list(g.subjects(RDF.type, NIDM.Project))) == 1
    # No subjects -> no sessions -> no acquisitions.
    assert list(g.subjects(RDF.type, NIDM.Session)) == []


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def test_cli_main_writes_output(tmp_path: Path):
    _write_dataset_description(tmp_path)
    _write_t1w_scan(tmp_path)
    out_path = tmp_path / "cli.ttl"

    rc = main(
        [
            "--bids_dir",
            str(tmp_path),
            "--output_file",
            str(out_path),
        ]
    )
    assert rc == 0
    assert out_path.exists() and out_path.stat().st_size > 0
