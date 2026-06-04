"""
BIDS -> NIDM-Experiment converter (RDFLib + LinkML wrapper layer).

Rebuilds the legacy ``nidm.experiment.tools.bidsmri2nidm`` on top of
the new wrapper API.  The port lands in phases; this revision is
"Phase A": full CLI + harness + ``dataset_description.json`` descent
+ the ``--per_subject`` output mode + shared project/dataset UUIDs
+ the ``_write_nidm_graph`` serialization step using
``add_export_provenance``.

The per-subject image-walk is still a single-pass slim implementation
in this revision; phases B and C replace it with the full
``participants.tsv -> Person/Demographics`` handling and the
full ``addimagingsessions`` per-datatype attribute extraction.

Module structure
----------------
*  ``getRelPathToBIDS`` / ``getsha512`` / ``check_encoding`` -- small
   filesystem helpers ported verbatim from legacy.
*  ``addbidsignore`` -- ensure a path is listed in ``.bidsignore``.
*  ``_write_nidm_graph`` -- serialize the project graph + CDE union
   to a turtle file, adding the export-provenance chain.
*  ``bidsmri2project`` -- the workhorse; returns
   ``(project, collection, cde, cde_pheno)``.
*  ``main`` -- argparse + ``--per_subject`` loop.

CLI
---
::

    bidsmri2nidm -d /path/to/bids [-o nidm.ttl] [--per_subject] \\
                 [--bidsignore] [--no_concepts] [--json_map FILE] \\
                 [--log LOGFILE] [--jsonld]

The console-script entry point is moved to this module in task 12
(cutover); until then, ``nidm.experiment.tools.bidsmri2nidm`` is
still the on-disk default.
"""
from __future__ import annotations
from argparse import ArgumentParser, RawTextHelpFormatter
import csv
import hashlib
from io import StringIO
import json
import logging
import os
from os.path import isfile, join
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional, Tuple
from rdflib import RDF, Graph, Literal, URIRef
from ..acquisition_object import AcquisitionObject
from ..assessment_acquisition import AssessmentAcquisition
from ..assessment_object import AssessmentObject
from ..collection import Collection
from ..mr_acquisition import MRAcquisition
from ..mr_object import MRObject
from ..person import Person
from ..pet_acquisition import PETAcquisition
from ..pet_object import PETObject
from ..project import Project
from ..session import Session
from ..utils import add_export_provenance, add_git_annex_sources
from ...core import bids_constants as BIDS_Constants
from ...core.namespaces import BIDS, NFO, PROV, SIO
from ...generated.nidm_schema_pydantic import ImageContrastTypeEnum, ImageUsageTypeEnum

__version__ = "0.4.0"  # Phase C: addimagingsessions full port
_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BIDS suffix / directory -> NIDM enum mapping (used in the slim subject loop;
# Phase C replaces it with the full per-datatype attribute extraction).
# ---------------------------------------------------------------------------

#: BIDS modality directory -> imaging modality.  Anything not listed is
#: treated as MRI by default (consistent with legacy behavior).
_DIRECTORY_TO_MODALITY = {
    "anat": "MR",
    "func": "MR",
    "dwi": "MR",
    "asl": "MR",
    "fmap": "MR",
    "pet": "PET",
}

#: BIDS modality directory -> image usage type.
_DIRECTORY_TO_USAGE = {
    "anat": ImageUsageTypeEnum.Anatomical,
    "func": ImageUsageTypeEnum.Functional,
    "dwi": ImageUsageTypeEnum.DiffusionWeighted,
}

#: BIDS filename suffix (between last `_` and `.`) -> image contrast.
_SUFFIX_TO_CONTRAST = {
    "T1w": ImageContrastTypeEnum.T1Weighted,
    "T2w": ImageContrastTypeEnum.T2Weighted,
    "T2starw": ImageContrastTypeEnum.T2StarWeighted,
    "dwi": ImageContrastTypeEnum.DiffusionWeighted,
    "asl": ImageContrastTypeEnum.ArterialSpinLabeling,
}

#: Filename patterns we recognize as scan data (suffix + extension).
_SCAN_FILE_RE = re.compile(
    r"^(?P<stem>.+?)_(?P<suffix>[A-Za-z0-9]+)\.(?P<ext>nii(?:\.gz)?)$"
)


# ---------------------------------------------------------------------------
# Filesystem helpers (legacy-parity)
# ---------------------------------------------------------------------------


def getRelPathToBIDS(filepath, bids_root, bidsuri_format: bool = False) -> str:
    """
    Return a path that is relative to the BIDS root.

    Drop-in port of the legacy helper.  When *bidsuri_format* is
    ``True`` the result is prefixed with ``bids::`` for use in
    NIDM-Experiment graphs.
    """
    path, file = os.path.split(filepath)
    relpath = path.replace(str(bids_root), "")
    file_relpath = os.path.join(relpath, file)
    if bidsuri_format:
        file_relpath = f'bids::{file_relpath.lstrip("/")}'
    return file_relpath


def getsha512(filename) -> str:
    """SHA-512 hex digest of *filename* (matches legacy)."""
    sha512_hash = hashlib.sha512()
    with open(filename, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha512_hash.update(byte_block)
    return sha512_hash.hexdigest()


def check_encoding(filename) -> Optional[str]:
    """Detect *filename*'s text encoding via chardet (matches legacy)."""
    import chardet  # lazy: heavy import, only needed for participants.tsv

    with open(filename, "rb") as f:
        result = chardet.detect(f.read())
    return result["encoding"]


def addbidsignore(directory, filename_to_add) -> None:
    """Append *filename_to_add* to ``directory/.bidsignore`` if not already there.

    Creates the file when missing.  Matches the legacy add-once semantics
    (a single substring match against the existing file contents).
    """
    _log.info("Adding file %s to %s/.bidsignore...", filename_to_add, directory)
    bidsignore_path = os.path.join(directory, ".bidsignore")
    if not isfile(bidsignore_path):
        with open(bidsignore_path, "w", encoding="utf-8") as text_file:
            print(filename_to_add, file=text_file)
        return
    with open(bidsignore_path, encoding="utf-8") as fp:
        if filename_to_add in fp.read():
            return
    with open(bidsignore_path, "a", encoding="utf-8") as text_file:
        print(filename_to_add, file=text_file)


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------


def _write_nidm_graph(
    project: Project,
    collection: Collection,
    cde: Graph,
    cde_pheno: List[Graph],
    outputfile,
    bidsignore: bool,
    directory,
    bidsignore_name: Optional[str] = None,
) -> None:
    """Serialize the union (project + cde + cde_pheno) to *outputfile*.

    Adds export-provenance via :func:`add_export_provenance` so the
    output mirrors the legacy NIDM-with-provenance shape.  When
    *bidsignore* is true, the resulting filename is added to the BIDS
    ``.bidsignore`` file at *directory*.
    """
    rdf_graph = Graph()
    rdf_graph.parse(source=StringIO(project.serialize_turtle()), format="turtle")
    rdf_graph = rdf_graph + cde
    for entry in cde_pheno or []:
        rdf_graph = rdf_graph + entry

    _log.info("Writing NIDM file %s ....", outputfile)

    if bidsignore:
        addbidsignore(directory, bidsignore_name or os.path.basename(outputfile))

    rdf_graph = add_export_provenance(
        rdf_graph=rdf_graph,
        collection=collection,
        outputfile=outputfile,
        pynidm_version=_pynidm_version(),
        tool_version=__version__,
        script_name="bidsmri2nidm.py",
        activity_label="Create NIDM RDF from BIDS dataset",
        output_format="turtle",
    )
    rdf_graph.serialize(destination=str(outputfile), format="turtle")


# ---------------------------------------------------------------------------
# dataset_description.json descent
# ---------------------------------------------------------------------------


def _load_dataset_description(directory) -> dict:
    """Return the parsed ``dataset_description.json`` or sys.exit on error.

    Matches the legacy contract: a missing file at the BIDS root is a
    fatal error (logged critical + sys.exit(-1)).
    """
    desc_path = os.path.join(directory, "dataset_description.json")
    if not os.path.isdir(directory):
        _log.critical("Error: BIDS directory %s does not exist!", directory)
        sys.exit(-1)
    try:
        with open(desc_path, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        _log.critical(
            "Cannot find dataset_description.json file which is required in the BIDS spec"
        )
        sys.exit(-1)


def _apply_dataset_description(
    project: Project, collection: Collection, dataset: dict
) -> None:
    """Map ``dataset_description.json`` keys onto project + collection.

    Keys present in :data:`BIDS_Constants.dataset_description` are
    forwarded to the appropriate predicate; ``Name`` lands on the
    project, list-valued keys (Authors, ReferencesAndLinks, ...) get
    one triple per entry on the collection, everything else lands on
    the collection as a single triple.  Unknown keys are silently
    dropped (legacy parity).
    """
    for key, value in dataset.items():
        if key not in BIDS_Constants.dataset_description:
            continue
        predicate = BIDS_Constants.dataset_description[key]
        if key == "Name":
            # Project name: join list values (preserves legacy quirk
            # where Name was sometimes a list).
            name = "".join(value) if isinstance(value, list) else value
            project.graph.add((project.identifier, predicate, _lit(name)))
        elif isinstance(value, list):
            for entry in value:
                collection.graph.add((collection.identifier, predicate, _lit(entry)))
        else:
            collection.graph.add((collection.identifier, predicate, _lit(value)))


def _lit(value):
    """Coerce *value* into an rdflib Literal."""
    return Literal(value)


# ---------------------------------------------------------------------------
# Programmatic entry point
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# participants.tsv handling (Phase B)
# ---------------------------------------------------------------------------


def _parse_subjid(participant_id: str) -> str:
    """Strip the ``sub-`` prefix when present (e.g. 'sub-01' -> '01').

    Tolerates both ``sub-XXXX`` and bare ``XXXX`` forms (matches the
    BIDS-files-in-the-wild quirk the legacy code handled).
    """
    parts = participant_id.split("-")
    return parts[1] if len(parts) > 1 else parts[0]


def _read_participants_tsv(directory) -> Tuple[List[str], List[dict]]:
    """Read ``directory/participants.tsv`` and return (fieldnames, rows).

    Returns ``([], [])`` if the file is missing.  Fieldnames are
    stripped of surrounding whitespace (some TSVs in the wild have
    trailing spaces in headers).  Detects encoding via chardet.
    """
    path = os.path.join(directory, "participants.tsv")
    if not os.path.isfile(path):
        return [], []
    encoding = check_encoding(path)
    with open(path, encoding=encoding) as csvfile:
        reader = csv.DictReader(csvfile, delimiter="\t")
        fieldnames = [f.strip() for f in (reader.fieldnames or [])]
        reader.fieldnames = fieldnames
        rows = list(reader)
    return fieldnames, rows


def _maybe_attach_participants_sidecar(
    acq: AssessmentAcquisition,
    acq_entity: AssessmentObject,
    collection: Collection,
    directory: str,
    bids_root: Path,
) -> Optional[AcquisitionObject]:
    """If ``directory/participants.json`` exists, create a sidecar
    AcquisitionObject typed ``bids:sidecar_file`` and link it via
    ``prov:wasInfluencedBy`` from *acq_entity*.

    Returns the sidecar wrapper (or None if no sidecar exists).
    """
    json_path = os.path.join(directory, "participants.json")
    if not os.path.isfile(json_path):
        return None
    sidecar = AcquisitionObject(acquisition=acq)
    sidecar.graph.add((sidecar.identifier, RDF.type, URIRef(BIDS["sidecar_file"])))
    sidecar.graph.add(
        (
            sidecar.identifier,
            NFO.filename,
            Literal(
                getRelPathToBIDS(
                    os.path.join(str(bids_root), "participants.json"),
                    str(bids_root),
                    bidsuri_format=True,
                )
            ),
        )
    )
    acq_entity.graph.add(
        (acq_entity.identifier, PROV.wasInfluencedBy, sidecar.identifier)
    )
    _add_collection_member(collection, sidecar)
    return sidecar


def _add_collection_member(collection: Collection, member) -> None:
    """Emit a ``prov:hadMember`` triple linking *collection* to *member*."""
    collection.graph.add((collection.identifier, PROV.hadMember, member.identifier))


def _process_participant_row(
    row: dict,
    project: Project,
    collection: Collection,
    sessions_by_subj: Dict[str, Session],
    persons_by_subj: Dict[str, Person],
    directory: str,
    bids_root: Path,
    subject_filter: Optional[str] = None,
) -> Optional[str]:
    """Materialize the NIDM nodes for one participants.tsv row.

    Creates a per-subject Session + AssessmentAcquisition + AssessmentObject
    + Person and registers them in *sessions_by_subj* / *persons_by_subj*
    so the imaging walk can reuse them.

    Returns the bare subject id (e.g. ``'01'``) when the row was processed,
    or ``None`` when skipped (subject_filter mismatch).
    """
    participant_id = row["participant_id"]
    subjid = _parse_subjid(participant_id)
    if subject_filter is not None and subjid != subject_filter:
        return None

    _log.info(subjid)
    session = Session(project)
    sessions_by_subj[subjid] = session

    acq = AssessmentAcquisition(session=session)
    acq_entity = AssessmentObject(acquisition=acq)
    _add_collection_member(collection, acq_entity)

    person = Person(project, subject_id=participant_id)
    persons_by_subj[subjid] = person

    # nfo:filename on the assessment entity -> bids::participants.tsv
    acq_entity.graph.add(
        (
            acq_entity.identifier,
            NFO.filename,
            Literal(
                getRelPathToBIDS(
                    os.path.join(str(bids_root), "participants.tsv"),
                    str(bids_root),
                    bidsuri_format=True,
                )
            ),
        )
    )
    acq.add_qualified_association(person, role=SIO.Subject)

    # Optional sidecar (participants.json -> bids:sidecar_file)
    _maybe_attach_participants_sidecar(
        acq, acq_entity, collection, directory, bids_root
    )
    return subjid


# ---------------------------------------------------------------------------
# Phase C: addimagingsessions -- per-scan attribute extraction
# ---------------------------------------------------------------------------


def _sidecar_json_path(scan_path: Path) -> Path:
    """Return the path to the JSON sidecar that pairs with *scan_path*.

    For ``sub-01_T1w.nii.gz`` the sidecar is ``sub-01_T1w.json`` in the
    same directory.  Strips both ``.nii.gz`` and ``.nii`` extensions
    before swapping in ``.json``.
    """
    name = scan_path.name
    for ext in (".nii.gz", ".nii"):
        if name.endswith(ext):
            stem = name[: -len(ext)]
            break
    else:
        stem = scan_path.stem
    return scan_path.with_name(stem + ".json")


def _load_sidecar_metadata(scan_path: Path) -> dict:
    """Return the JSON sidecar dict for *scan_path*, or ``{}`` if absent
    or malformed (matches legacy quiet-failure)."""
    sidecar = _sidecar_json_path(scan_path)
    if not sidecar.is_file():
        return {}
    try:
        return json.loads(sidecar.read_text())
    except json.JSONDecodeError:
        _log.warning("malformed sidecar JSON: %s; ignoring", sidecar)
        return {}


def _apply_json_keys(obj, metadata: dict) -> None:
    """Map BIDS sidecar JSON keys to NIDM predicates on *obj*.

    Iterates over *metadata* keys; when ``BIDS_Constants.json_keys``
    has a mapping, emit one triple on ``obj.graph`` with the mapped
    predicate.  List values are joined with empty string (matches
    legacy quirk for the per-scan sidecar; the root-level descent
    uses comma-join instead).
    """
    for key, value in metadata.items():
        normalized_key = key.replace(" ", "_")
        if normalized_key not in BIDS_Constants.json_keys:
            continue
        predicate = BIDS_Constants.json_keys[normalized_key]
        if isinstance(value, list):
            obj.graph.add(
                (obj.identifier, predicate, Literal("".join(str(e) for e in value)))
            )
        else:
            obj.graph.add((obj.identifier, predicate, Literal(value)))


def _apply_scan_contrast_and_usage(obj, suffix: str, datatype: str) -> None:
    """Emit nidm:hadImageContrastType + nidm:hadImageUsageType triples
    using ``BIDS_Constants.scans`` mappings.  Missing mappings are
    logged at INFO (matches legacy)."""
    from ...core import constants as _C

    if suffix in BIDS_Constants.scans:
        obj.graph.add(
            (obj.identifier, _C.NIDM_IMAGE_CONTRAST_TYPE, BIDS_Constants.scans[suffix])
        )
    else:
        _log.info(
            "WARNING: No matching image contrast type found in BIDS_Constants.py for %s",
            suffix,
        )
    if datatype in BIDS_Constants.scans:
        obj.graph.add(
            (obj.identifier, _C.NIDM_IMAGE_USAGE_TYPE, BIDS_Constants.scans[datatype])
        )
    else:
        _log.info(
            "WARNING: No matching image usage type found in BIDS_Constants.py for %s",
            datatype,
        )


def _emit_sha512_triple(
    obj,
    scan_full_path: Path,
    bids_root: Path,  # noqa: U100 -- accepted for caller symmetry, may be used later
) -> None:
    """Add a CRYPTO_SHA512 triple on *obj* if the file exists.

    Missing files are logged at INFO (matches legacy).
    """
    from ...core import constants as _C

    if scan_full_path.is_file():
        obj.graph.add(
            (obj.identifier, _C.CRYPTO_SHA512, Literal(getsha512(str(scan_full_path))))
        )
    else:
        _log.info(
            "WARNING file %s doesn't exist! No SHA512 sum stored in NIDM files...",
            scan_full_path,
        )


def _maybe_apply_root_level_json(
    obj, directory: str, json_filename: str, img_session: Optional[str] = None
) -> None:
    """Load *directory/json_filename* (or session-specific variant) and
    apply :data:`BIDS_Constants.json_keys` mappings to *obj*.

    Falls back silently when neither file exists.  Used for the
    legacy T1w.json / task-rest_bold.json descent at BIDS root.
    """
    root_path = os.path.join(directory, json_filename)
    payload: Optional[dict] = None
    if os.path.isfile(root_path):
        try:
            with open(root_path, encoding="utf-8") as f:
                payload = json.load(f)
        except OSError:
            payload = None
    elif img_session is not None:
        ses_path = os.path.join(directory, f"ses-{img_session}_{json_filename}")
        if os.path.isfile(ses_path):
            try:
                with open(ses_path, encoding="utf-8") as f:
                    payload = json.load(f)
            except OSError:
                payload = None
    if not payload:
        return
    for key, value in payload.items():
        if key not in BIDS_Constants.json_keys:
            continue
        predicate = BIDS_Constants.json_keys[key]
        if isinstance(value, list):
            obj.graph.add(
                (obj.identifier, predicate, Literal(",".join(map(str, value))))
            )
        else:
            obj.graph.add((obj.identifier, predicate, Literal(value)))


# Map BIDS datatype name -> the root-level JSON filename the legacy
# tool reads for that datatype.  Only datatypes that have a real
# descent target are listed; others fall through to no-op.
_ROOT_LEVEL_JSON_BY_DATATYPE = {
    "anat": "T1w.json",
    "func": "task-rest_bold.json",
}


def _process_scan_file(
    scan_path: Path,
    modality_name: str,
    acq,  # noqa: U100 -- accepted for events.tsv attachment in Phase D
    obj,
    directory: str,
    bids_root: Path,
    img_session: Optional[str] = None,
) -> None:
    """Attach per-scan metadata to *obj* (the AcquisitionObject wrapper).

    The caller has already created *acq* / *obj* with the right
    wrapper subclass (MR vs PET) and filename; this helper layers on:

      * contrast/usage type via BIDS_Constants.scans
      * sha512 hash via getsha512 (when file is non-empty)
      * git-annex sources via add_git_annex_sources
      * sidecar JSON descent (sub-XX_T1w.json next to the scan)
      * root-level T1w.json / task-rest_bold.json descent
    """
    suffix = _suffix_from_filename(scan_path.name) or ""
    _apply_scan_contrast_and_usage(obj, suffix, modality_name)
    _emit_sha512_triple(obj, scan_path, bids_root)
    add_git_annex_sources(obj=obj, filepath=str(scan_path), bids_root=str(bids_root))
    _apply_json_keys(obj, _load_sidecar_metadata(scan_path))
    root_json = _ROOT_LEVEL_JSON_BY_DATATYPE.get(modality_name)
    if root_json is not None:
        _maybe_apply_root_level_json(obj, directory, root_json, img_session)


def addimagingsessions(
    subject_id: str,
    session: Session,
    persons_by_subj: Dict[str, Person],
    bare_id: str,
    directory: str,
    bids_root: Path,
    collection: Collection,
    project: Project,
    img_session: Optional[str] = None,
) -> None:
    """Walk *subject_id*'s BIDS directory and emit one
    ``MRAcquisition``/``PETAcquisition`` per scan file, fully
    populated with sidecar metadata.

    Reuses the per-subject ``Person`` from *persons_by_subj* when
    available; creates a fresh one otherwise.
    """
    subject_dir = bids_root / subject_id
    if not subject_dir.is_dir():
        return

    person = persons_by_subj.get(bare_id)
    if person is None:
        person = Person(project, subject_id=subject_id)
        persons_by_subj[bare_id] = person

    for modality_dir in sorted(subject_dir.iterdir()):
        if not modality_dir.is_dir():
            continue
        modality_name = modality_dir.name
        if modality_name not in _DIRECTORY_TO_MODALITY:
            continue
        modality = _DIRECTORY_TO_MODALITY[modality_name]
        image_usage = _DIRECTORY_TO_USAGE.get(modality_name)

        for scan_path in sorted(modality_dir.iterdir()):
            if not scan_path.is_file():
                continue
            suffix = _suffix_from_filename(scan_path.name)
            if suffix is None:
                continue

            if modality == "PET":
                acq = PETAcquisition(session)
                obj = PETObject(acq, filename=_bids_filename(scan_path, bids_root))
            else:
                acq = MRAcquisition(session)
                contrast = _SUFFIX_TO_CONTRAST.get(suffix)
                obj = MRObject(
                    acq,
                    filename=_bids_filename(scan_path, bids_root),
                    image_contrast_type=contrast,
                    image_usage_type=image_usage,
                )
            acq.add_qualified_association(person, role=SIO.Subject)
            _add_collection_member(collection, obj)
            _process_scan_file(
                scan_path=scan_path,
                modality_name=modality_name,
                acq=acq,
                obj=obj,
                directory=directory,
                bids_root=bids_root,
                img_session=img_session,
            )


def bidsmri2project(
    directory,
    args=None,  # noqa: U100 -- consumed in Phase D (json_map, no_concepts flags)
    subject_filter: Optional[str] = None,
    project_uuid: Optional[str] = None,
    dataset_uuid: Optional[str] = None,
) -> Tuple[Project, Collection, Graph, List[Graph]]:
    """Build a NIDM Project + BIDS Dataset collection from a BIDS directory.

    Returns ``(project, collection, cde, cde_pheno)``:

      * ``project`` -- the Project wrapper.
      * ``collection`` -- the BIDS Dataset Collection wrapper.
      * ``cde`` -- an rdflib.Graph of common data elements for any
        participants.tsv variables that were mapped (Phase B+).
      * ``cde_pheno`` -- list of additional CDE graphs produced by
        :func:`map_variables_to_terms` calls (Phase D+).

    When ``project_uuid`` / ``dataset_uuid`` are supplied, the new
    Project / Collection reuse them rather than generating fresh
    UUIDs; this is how ``--per_subject`` mode keeps all per-subject
    files referencing the same nidm:Project / bids:Dataset.

    Phases A through D incrementally fill in the body; in this
    revision (Phase A) the subject walk uses the slim implementation
    while the harness and dataset_description handling are full.
    """
    directory = str(directory)
    cde = Graph()
    cde_pheno: List[Graph] = []

    dataset = _load_dataset_description(directory)

    project = Project(uuid=project_uuid) if project_uuid is not None else Project()
    collection = Collection(project, uuid=dataset_uuid, extra_types=[BIDS.Dataset])

    _apply_dataset_description(project, collection, dataset)

    bids_root = Path(directory).resolve()
    sessions_by_subj: Dict[str, Session] = {}
    persons_by_subj: Dict[str, Person] = {}

    # ------------------------------------------------------------------
    # Phase B -- participants.tsv -> Person / Session / AssessmentObject
    # ------------------------------------------------------------------
    fieldnames, rows = _read_participants_tsv(directory)
    for row in rows:
        _process_participant_row(
            row=row,
            project=project,
            collection=collection,
            sessions_by_subj=sessions_by_subj,
            persons_by_subj=persons_by_subj,
            directory=directory,
            bids_root=bids_root,
            subject_filter=subject_filter,
        )

    # ------------------------------------------------------------------
    # Phase C -- per-subject image walk via addimagingsessions.
    # Reuses Session/Person from participants.tsv when present, creates
    # fresh ones from the filesystem when participants.tsv is absent or
    # doesn't cover all subjects.
    # ------------------------------------------------------------------
    for subject_dir in sorted(bids_root.glob("sub-*")):
        if not subject_dir.is_dir():
            continue
        subject_id = subject_dir.name  # "sub-01"
        bare_id = (
            subject_id.removeprefix("sub-")
            if hasattr(str, "removeprefix")
            else subject_id[4:]
        )
        if subject_filter is not None and bare_id != subject_filter:
            continue

        session = sessions_by_subj.get(bare_id)
        if session is None:
            session = Session(project)
            sessions_by_subj[bare_id] = session

        addimagingsessions(
            subject_id=subject_id,
            session=session,
            persons_by_subj=persons_by_subj,
            bare_id=bare_id,
            directory=directory,
            bids_root=bids_root,
            collection=collection,
            project=project,
        )

    # fieldnames currently unused at top level; Phase D consumes them
    # for the CDE-attachment logic via map_variables_to_terms.
    del fieldnames

    return project, collection, cde, cde_pheno


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description=(
            "Represent a BIDS dataset as a NIDM RDF document.  When -no_concepts "
            "is not set, the user is interactively prompted to map participants.tsv "
            "variables to concepts (requires INTERLEX_API_KEY env var)."
        ),
        formatter_class=RawTextHelpFormatter,
    )
    parser.add_argument(
        "-d",
        dest="directory",
        required=True,
        help="Full path to BIDS dataset directory",
    )
    parser.add_argument(
        "-jsonld",
        "--jsonld",
        action="store_true",
        help="If flag set, output is json-ld not TURTLE",
    )
    parser.add_argument(
        "-bidsignore",
        "--bidsignore",
        action="store_true",
        default=False,
        help="If flag set, tool will add NIDM-related files to .bidsignore",
    )
    parser.add_argument(
        "-no_concepts",
        "--no_concepts",
        action="store_true",
        default=False,
        help="If flag set, tool will not do concept mapping",
    )
    mapvars = parser.add_argument_group("map variables to terms arguments")
    mapvars.add_argument(
        "-json_map",
        "--json_map",
        dest="json_map",
        required=False,
        default=False,
        help="Optional full path to user-supplied JSON file containing variable-term mappings.",
    )
    parser.add_argument(
        "-log",
        "--log",
        dest="logfile",
        required=False,
        default=None,
        help=(
            "Full path to directory to save log file.  Log file is "
            "bidsmri2nidm_[basename(directory)].log"
        ),
    )
    parser.add_argument(
        "-o",
        dest="outputfile",
        required=False,
        default="nidm.ttl",
        help="Output turtle filename (or directory in --per_subject mode).",
    )
    parser.add_argument(
        "-per_subject",
        "--per_subject",
        action="store_true",
        default=False,
        help=(
            "Emit one NIDM turtle file per subject, named sub-<id>_nidm.ttl.  "
            "By default they go in the BIDS directory; use -o to specify a "
            "different output directory."
        ),
    )
    return parser


def _resolve_per_subject_output_dir(args) -> str:
    """When --per_subject is set, the -o flag is interpreted as an output
    directory; falls back to the BIDS directory if -o wasn't supplied.
    Creates the directory when missing.  Matches legacy behavior."""
    if args.outputfile == "nidm.ttl":
        return args.directory
    out_dir = args.outputfile
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    return out_dir


def _list_subjects(directory) -> List[str]:
    """Return BIDS subject IDs (without the ``sub-`` prefix), sorted."""
    bids_root = Path(directory).resolve()
    subjects = []
    for sub_dir in sorted(bids_root.glob("sub-*")):
        if not sub_dir.is_dir():
            continue
        name = sub_dir.name
        if name.startswith("sub-."):
            continue
        subjects.append(name[len("sub-") :])
    return subjects


def main(argv: Optional[list] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    directory = args.directory

    if args.logfile is not None:
        logging.basicConfig(
            filename=join(
                args.logfile,
                "bidsmri2nidm_" + args.outputfile.split("/")[-2] + ".log",
            ),
            level=logging.DEBUG,
        )
        _log.info("bidsmri2nidm %s", args)

    if args.per_subject:
        out_dir = _resolve_per_subject_output_dir(args)
        # .bidsignore paths are only meaningful when output lands in the BIDS tree
        abs_bids = os.path.abspath(directory)
        abs_out = os.path.abspath(out_dir)
        out_inside_bids = abs_out == abs_bids or abs_out.startswith(abs_bids + os.sep)
        if args.bidsignore and not out_inside_bids:
            _log.warning(
                "Output directory %s is outside BIDS directory %s; per-subject "
                "files will not be added to .bidsignore",
                out_dir,
                directory,
            )

        # Share project + dataset UUIDs across per-subject runs.
        from ..core import getUUID

        shared_project_uuid = getUUID()
        shared_dataset_uuid = getUUID()

        for subj in _list_subjects(directory):
            _log.info("Building NIDM file for subject %s", subj)
            project, collection, cde, cde_pheno = bidsmri2project(
                directory,
                args,
                subject_filter=subj,
                project_uuid=shared_project_uuid,
                dataset_uuid=shared_dataset_uuid,
            )
            outputfile = os.path.join(out_dir, f"sub-{subj}_nidm.ttl")
            bidsignore_name = (
                os.path.relpath(os.path.abspath(outputfile), abs_bids)
                if (args.bidsignore and out_inside_bids)
                else None
            )
            _write_nidm_graph(
                project=project,
                collection=collection,
                cde=cde,
                cde_pheno=cde_pheno,
                outputfile=outputfile,
                bidsignore=bidsignore_name is not None,
                directory=directory,
                bidsignore_name=bidsignore_name,
            )
    else:
        project, collection, cde, cde_pheno = bidsmri2project(directory, args)
        outputfile = (
            os.path.join(directory, args.outputfile)
            if args.outputfile == "nidm.ttl"
            else args.outputfile
        )
        _write_nidm_graph(
            project=project,
            collection=collection,
            cde=cde,
            cde_pheno=cde_pheno,
            outputfile=outputfile,
            bidsignore=args.bidsignore,
            directory=directory,
            bidsignore_name=args.outputfile,
        )
    return 0


# ---------------------------------------------------------------------------
# Small internal helpers (used by the slim subject walk; will move to
# Phase C's addimagingsessions when that lands)
# ---------------------------------------------------------------------------


def _bids_filename(scan_path: Path, bids_root: Path) -> str:
    """Return a ``bids::``-prefixed relative path string."""
    rel = scan_path.resolve().relative_to(bids_root.resolve()).as_posix()
    return f"bids::{rel}"


def _suffix_from_filename(filename: str) -> Optional[str]:
    """Pull the BIDS suffix (e.g. 'T1w') out of a filename, or None."""
    m = _SCAN_FILE_RE.match(filename)
    return m.group("suffix") if m else None


def _pynidm_version() -> str:
    """Return the installed PyNIDM version, or 'unknown'."""
    try:
        from nidm import __version__ as v  # type: ignore[attr-defined]

        return str(v)
    except Exception:
        return "unknown"


def _runtime_platform() -> str:
    """Return e.g. 'Python 3.9.23' for the SoftwareAgent runtime_platform."""
    import platform

    return f"Python {platform.python_version()}"


if __name__ == "__main__":
    raise SystemExit(main())
