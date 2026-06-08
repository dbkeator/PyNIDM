"""
CSV/TSV -> NIDM-Experiment converter (RDFLib + LinkML wrapper layer).

Rebuilds the legacy ``nidm.experiment.tools.csv2nidm`` on top of the
new wrapper API.  Phase A covers:

  * Full CLI: ``-csv``, ``-json_map``, ``-csv_map``, ``-redcap``,
    ``-no_concepts``, ``-log``, ``-out``, ``-dataset_id``,
    ``-derivative`` (parse only; full -derivative handling lands in
    phase B), ``-nidm`` (parse only; add-to-existing path lands in
    phase B).
  * CSV/TSV reading.
  * Data-dictionary resolution (REDCap dict, CSV map, raw JSON).
  * One :class:`Project` + per-row ``Session`` +
    ``AssessmentAcquisition`` + ``AssessmentObject`` + ``Person``.
  * CDE attachment via :func:`map_variables_to_terms` +
    :func:`add_attributes_with_cde` for each ``(column, value)`` cell.
  * Output via :func:`_write_nidm_graph` (same helper as bidsmri2nidm).

Phase B will add the ``-nidm`` and ``-derivative`` paths.
"""
from __future__ import annotations
from argparse import ArgumentParser
import logging
import os
from os.path import basename, dirname, join
import sys
from typing import Any, List, Optional, Tuple
import pandas as pd
from rdflib import Graph
from .bidsmri2nidm import _pynidm_version, _runtime_platform  # reuse from bidsmri2nidm
from ..assessment_acquisition import AssessmentAcquisition
from ..assessment_object import AssessmentObject
from ..derivative import Derivative
from ..derivative_object import DerivativeObject
from ..person import Person
from ..project import Project
from ..session import Session
from ..software_agent import SoftwareAgent
from ..utils import (
    add_attributes_with_cde,
    add_export_provenance,
    csv_dd_to_json_dd,
    map_variables_to_terms,
    read_nidm,
    redcap_datadictionary_to_json,
)
from ...core import constants as _C
from ...core.namespaces import NFO, SIO

__version__ = "0.3.0"  # Phase C: -derivative + software metadata
_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# id-field detection helpers (ported from legacy)
# ---------------------------------------------------------------------------


def detect_idfield(column_to_terms: dict) -> Optional[str]:
    """Find the participant-id column in *column_to_terms*.

    Scans each entry's ``isAbout`` list for a URI matching
    ``NIDM_SUBJECTID``.  Returns the variable name (the part between
    ``variable=`` and ``)`` in the DD()-stringified key), or None
    when no match is found.
    """
    target = str(_C.NIDM_SUBJECTID)
    for key, value in column_to_terms.items():
        if "isAbout" not in value:
            continue
        for concept in value["isAbout"]:
            for isabout_key, isabout_value in concept.items():
                if isabout_key in ("url", "@id") and isabout_value == target:
                    return (
                        key.split("variable")[1]
                        .split("=")[1]
                        .split(")")[0]
                        .lstrip("'")
                        .rstrip("'")
                    )
    return None


def ask_idfield(df) -> str:
    """Interactively prompt for the subject-id column.

    Legacy parity helper; csv2nidm calls this when ``detect_idfield``
    returns None and no existing NIDM file is supplied.
    """
    option = 1
    for column in df.columns:
        print(f"{option}: {column}")
        option += 1
    selection = input("Please select the subject ID field from the list above: ")
    while (not selection.isdigit()) or (int(selection) > int(option)):
        selection = input("Please select the subject ID field from the list above: \t")
    return df.columns[int(selection) - 1]


# ---------------------------------------------------------------------------
# Data-dictionary resolution
# ---------------------------------------------------------------------------


def _resolve_json_map(args) -> Optional[Any]:
    """Resolve the data-dictionary source from CLI args.

    Order of precedence (matches legacy):
      1. ``-redcap`` -> convert RedCap CSV to JSON via
         :func:`redcap_datadictionary_to_json`.
      2. ``-json_map`` -> use the path directly.
      3. ``-csv_map`` -> convert via :func:`csv_dd_to_json_dd`.
      4. Otherwise None.
    """
    if getattr(args, "redcap", None):
        return redcap_datadictionary_to_json(args.redcap, basename(args.csv_file))
    if getattr(args, "json_map", None):
        return args.json_map
    csv_map = getattr(args, "csv_map", None)
    if csv_map:
        if not csv_map.lower().endswith(".csv"):
            print("ERROR: -csv_map parameter must be a CSV file with .csv extension...")
            sys.exit(-1)
        return csv_dd_to_json_dd(csv_map)
    return None


def _read_input_dataframe(csv_file: str) -> pd.DataFrame:
    """Read *csv_file* into a DataFrame.

    Accepts ``.csv`` (comma-separated) and ``.tsv`` (tab-separated).
    Anything else sys.exits with a legacy-style error message.
    """
    if csv_file.endswith(".csv"):
        return pd.read_csv(csv_file)
    if csv_file.endswith(".tsv"):
        return pd.read_csv(csv_file, sep="\t", engine="python")
    print(
        "ERROR: input file must have .csv (comma-separated) or .tsv "
        "(tab separated) extensions/file types.  Please change your "
        "input file appropriately and re-run."
    )
    print("no NIDM file created!")
    sys.exit(-1)


# ---------------------------------------------------------------------------
# Per-row materialization
# ---------------------------------------------------------------------------


def _materialize_row(
    df_row: pd.Series,
    df_columns: List[str],
    project: Project,
    cde: Graph,
    id_field: Optional[str],
    assessment_name: str,  # noqa: U100 -- reserved for DD-key derivation in Phase B
    csv_file_path: str,
) -> None:
    """Emit one Session + AssessmentAcquisition + AssessmentObject + Person
    for *df_row* and attach a CDE-style attribute triple for each cell.

    *id_field* is the column carrying the participant identifier; when
    None, no Person is created and the per-row data still lands on its
    own AssessmentObject (matches the legacy fall-through path).
    """
    session = Session(project)
    acq = AssessmentAcquisition(session=session)
    acq_entity = AssessmentObject(acquisition=acq)

    # nfo:filename on the assessment entity -> the CSV file.
    from rdflib import Literal as _Lit

    acq_entity.graph.add(
        (acq_entity.identifier, NFO.filename, _Lit(basename(csv_file_path)))
    )

    person: Optional[Person] = None
    if id_field is not None and id_field in df_columns:
        person = Person(project, subject_id=str(df_row[id_field]))
        acq.add_qualified_association(person, role=SIO.Subject)

    # Each non-id-field column emits a CDE attribute triple.
    for column in df_columns:
        if column == id_field:
            continue
        value = df_row[column]
        if pd.isna(value):
            continue
        add_attributes_with_cde(
            obj=acq_entity, cde=cde, row_variable=column, value=value
        )


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------


def _write_nidm_graph(
    project: Project,
    cde: Graph,
    output_file: str,
    activity_label: str = "Add CSV data to NIDM file",
) -> None:
    """Serialize the union (project + cde) to *output_file*.

    Adds export-provenance via :func:`add_export_provenance` so the
    output mirrors the legacy NIDM-with-provenance shape.
    """
    rdf_graph = Graph()
    from io import StringIO

    rdf_graph.parse(source=StringIO(project.serialize_turtle()), format="turtle")
    rdf_graph = rdf_graph + cde

    _log.info("Writing NIDM file %s ....", output_file)

    rdf_graph = add_export_provenance(
        rdf_graph=rdf_graph,
        collection=None,
        outputfile=output_file,
        pynidm_version=_pynidm_version(),
        tool_version=__version__,
        script_name="csv2nidm.py",
        activity_label=activity_label,
        output_format="turtle",
    )
    rdf_graph.serialize(destination=str(output_file), format="turtle")
    # Use runtime_platform so it's not "unused" in module-level imports;
    # add_export_provenance handles platform internally but we keep the
    # accessor available for future tool agents.
    _ = _runtime_platform


# ---------------------------------------------------------------------------
# Phase B: -nidm add-to-existing helpers
# ---------------------------------------------------------------------------


def _query_subject_ids(project: Project) -> List[Tuple[Any, str]]:
    """Return ``[(person_uri, src_subject_id), ...]`` from *project*.

    Runs a SPARQL query against the loaded NIDM graph to enumerate
    every prov:Person and its ndar:src_subject_id.  Returns an empty
    list when the graph has no persons.
    """
    query = """
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/>
        SELECT ?person ?id WHERE {
            ?person a prov:Person ;
                    ndar:src_subject_id ?id .
        }
    """
    return [(row[0], str(row[1])) for row in project.graph.query(query)]


def _find_person_for_csv_row(
    df_value: str, subject_index: List[Tuple[Any, str]]
) -> Optional[Any]:
    """Find the prov:Person URI for *df_value* in the existing NIDM file.

    Mirrors the legacy lenient matching: strip leading zeros from both
    sides and check substring containment (matches the BIDS quirk
    where participants.tsv has 'sub-01' and df rows have '01' or vice
    versa).
    """
    needle = str(df_value).lstrip("0")
    for person_uri, src_id in subject_index:
        src_stripped = src_id.lstrip("0")
        if src_stripped in needle or src_stripped == needle:
            return person_uri
        if src_id in str(df_value):
            return person_uri
    return None


def _attach_csv_row_to_existing_project(
    df_row: pd.Series,
    df_columns: List[str],
    project: Project,
    cde: Graph,
    person_uri: Any,
    id_field: Optional[str],
    csv_file_path: str,
) -> None:
    """Add one Session + AssessmentAcquisition + AssessmentObject to
    *project* for *df_row*, linking the new acquisition to the existing
    *person_uri* via ``add_qualified_association`` on the wrapper.
    """
    from rdflib import Literal as _Lit

    session = Session(project)
    acq = AssessmentAcquisition(session=session)
    acq_entity = AssessmentObject(acquisition=acq)
    acq_entity.graph.add(
        (acq_entity.identifier, NFO.filename, _Lit(basename(csv_file_path)))
    )
    # Link the new acquisition to the existing Person via a Person
    # wrapper.from_existing_subject so the qualifiedAssociation lands.
    existing_person = Person.from_existing_subject(project.graph, person_uri)
    acq.add_qualified_association(existing_person, role=SIO.Subject)

    for column in df_columns:
        if column == id_field:
            continue
        value = df_row[column]
        if pd.isna(value):
            continue
        add_attributes_with_cde(
            obj=acq_entity, cde=cde, row_variable=column, value=value
        )


def csv2nidm_add_to_existing(
    csv_file: str,
    nidm_file: str,
    *,
    json_map=None,
    associate_concepts: bool = False,
    dataset_identifier: Optional[str] = None,
    id_field: Optional[str] = None,
) -> Tuple[Project, Graph, int]:
    """Add CSV data to an existing NIDM file in place.

    Returns ``(project, cde_graph, rows_added)``.  When zero rows
    matched any existing subject, the caller can skip the serialization
    step (matches legacy ``data_added`` short-circuit).
    """
    df = _read_input_dataframe(csv_file)
    out_dir = dirname(nidm_file)
    assessment_name = basename(csv_file)

    column_to_terms, cde = map_variables_to_terms(
        df=df,
        assessment_name=assessment_name,
        directory=out_dir,
        output_file=nidm_file,
        json_source=json_map,
        associate_concepts=associate_concepts,
    )
    del dataset_identifier  # reserved for Phase C / dataset hashing

    if id_field is None:
        id_field = detect_idfield(column_to_terms) if column_to_terms else None
    if id_field is None:
        # Legacy falls back to interactive prompt; programmatic callers
        # should pass id_field explicitly.
        id_field = ask_idfield(df)

    # Re-read with id_field constrained to string (matches legacy:
    # avoids losing leading zeros on zero-padded subject IDs).
    df = (
        pd.read_csv(csv_file, dtype={id_field: str})
        if csv_file.endswith(".csv")
        else pd.read_csv(csv_file, dtype={id_field: str}, sep="\t")
    )

    project = read_nidm(nidm_file)
    subject_index = _query_subject_ids(project)
    rows_added = 0
    df_columns = list(df.columns)
    for _, row in df.iterrows():
        person_uri = _find_person_for_csv_row(row[id_field], subject_index)
        if person_uri is None:
            continue
        _attach_csv_row_to_existing_project(
            df_row=row,
            df_columns=df_columns,
            project=project,
            cde=cde,
            person_uri=person_uri,
            id_field=id_field,
            csv_file_path=csv_file,
        )
        rows_added += 1

    return project, cde, rows_added


def _write_existing_nidm_back(
    project: Project,
    cde: Graph,
    nidm_file: str,
    backup: bool = True,
) -> None:
    """Serialize *project* + *cde* back to *nidm_file*, optionally
    backing the original up to ``<file>.bak`` first."""
    from shutil import copy2

    if backup:
        copy2(src=nidm_file, dst=nidm_file + ".bak")
    rdf_graph = Graph()
    from io import StringIO

    rdf_graph.parse(source=StringIO(project.serialize_turtle()), format="turtle")
    rdf_graph = rdf_graph + cde
    rdf_graph = add_export_provenance(
        rdf_graph=rdf_graph,
        collection=None,
        outputfile=nidm_file,
        pynidm_version=_pynidm_version(),
        tool_version=__version__,
        script_name="csv2nidm.py",
        activity_label="Add CSV data to NIDM file",
        output_format="turtle",
    )
    rdf_graph.serialize(destination=nidm_file, format="turtle")


# ---------------------------------------------------------------------------
# Phase C: -derivative + software metadata
# ---------------------------------------------------------------------------

#: Columns the input CSV MUST carry when -derivative is in play.
_DERIVATIVE_INPUT_REQUIRED = ("ses", "task", "run", "source_url")

#: Columns the software-metadata CSV (passed to -derivative) MUST carry.
_SOFTWARE_METADATA_REQUIRED = (
    "title",
    "description",
    "version",
    "url",
    "cmdline",
    "platform",
    "ID",
)


def _validate_derivative_input_columns(df: pd.DataFrame) -> None:
    """Ensure the input CSV has ses/task/run/source_url columns.

    Sys-exits with the legacy error message when any are missing.
    """
    missing = [c for c in _DERIVATIVE_INPUT_REQUIRED if c not in df.columns]
    if missing:
        print(
            "ERROR: -csv data file must have 'ses','task', 'run', 'source_url' "
            "columns (even if empty) when the -derivative parameter is provided."
        )
        sys.exit(1)


def _load_software_metadata(derivative_path: str) -> pd.DataFrame:
    """Load the software-metadata CSV/TSV and validate its columns."""
    if derivative_path.endswith(".csv"):
        meta = pd.read_csv(derivative_path)
    elif derivative_path.endswith(".tsv"):
        meta = pd.read_csv(derivative_path, sep="\t", engine="python")
    else:
        print(
            "ERROR: -derivative parameter must point at a .csv or .tsv file."
        )
        sys.exit(1)
    missing = [c for c in _SOFTWARE_METADATA_REQUIRED if c not in meta.columns]
    if missing:
        print(
            "ERROR: -derivative software metadata file must contain columns "
            "title, description, version, url, cmdline, platform, ID (even if "
            "empty).  Missing: %s" % ", ".join(missing)
        )
        sys.exit(1)
    return meta


def find_session_for_subjectid(
    session_num: Optional[str], subjectid: str, nidm_file: str
) -> Optional[Any]:
    """Look up a Session URI by its bids:session_number for *subjectid*.

    Delegates to ``GetParticipantSessionsMetadata`` (via the Query
    shim) and scans the returned DataFrame for the row whose
    ``p`` (predicate) is ``bids:session_number`` and whose ``o``
    (object) matches *session_num*.
    """
    from ...core import constants as _C
    from ..query import GetParticipantSessionsMetadata

    if session_num is None:
        return None
    session_metadata = GetParticipantSessionsMetadata([nidm_file], subjectid)
    derivative_session = None
    bids_session_number = _C.BIDS["session_number"]
    for _, row in session_metadata.iterrows():
        if str(row["p"]) == str(bids_session_number) and str(row["o"]) == session_num:
            derivative_session = row["session_uuid"]
            break
    return derivative_session


def match_acquistion_task_run_from_session(
    subject_id: str,
    session_uuid: Optional[Any],
    task: Optional[str],
    run: Optional[str],
    nidm_file: str,
) -> Tuple[Optional[Any], Optional[Any]]:
    """Look up the acquisition entity + activity matching *task* / *run*.

    Returns ``(acq_entity_uri, acq_activity_uri)`` from the first
    matching row of the appropriate Query helper, or ``(None, None)``
    when no match is found.

    When *session_uuid* is None, walks every session for the subject
    until a match is found (matches legacy).
    """
    from ..query import (
        GetAcquisitionEntityFromSubjectSessionRun,
        GetAcquisitionEntityFromSubjectSessionTask,
        GetAcquisitionEntityFromSubjectSessionTaskRun,
        GetParticipantSessionsMetadata,
    )

    def _first_row(df):
        for _, row in df.iterrows():
            return row.get("acq_entity"), row.get("acq_activity")
        return None, None

    def _lookup(session_uri):
        if task and run:
            return _first_row(
                GetAcquisitionEntityFromSubjectSessionTaskRun(
                    nidm_file_list=[nidm_file],
                    subject_id=subject_id,
                    session_uuid=session_uri,
                    run=run,
                    task=task,
                )
            )
        if run and not task:
            return _first_row(
                GetAcquisitionEntityFromSubjectSessionRun(
                    nidm_file_list=[nidm_file],
                    subject_id=subject_id,
                    session_uuid=session_uri,
                    run=run,
                )
            )
        if task and not run:
            return _first_row(
                GetAcquisitionEntityFromSubjectSessionTask(
                    nidm_file_list=[nidm_file],
                    subject_id=subject_id,
                    session_uuid=session_uri,
                    task=task,
                )
            )
        return None, None

    if session_uuid is not None:
        return _lookup(session_uuid)

    # Walk every session for the subject.
    session_acts = GetParticipantSessionsMetadata([nidm_file], subject_id)
    for _, session in session_acts.iterrows():
        entity, activity = _lookup(session["session_uuid"])
        if entity is not None:
            return entity, activity
    return None, None


def _create_software_agent_for_derivative(
    project: Project, software_metadata: pd.DataFrame
) -> SoftwareAgent:
    """Create a SoftwareAgent wrapper carrying the supplied metadata.

    Uses the first row of *software_metadata* (legacy convention -- one
    row per CSV).  Title / description / version / url / cmdline /
    platform all get attached as named slots on the wrapper.
    """

    def _scalar(col):
        return software_metadata[col].to_string(index=False).strip()

    return SoftwareAgent(
        project,
        name=_scalar("title"),
        software_version=_scalar("version"),
        command=_scalar("cmdline"),
        runtime_platform=_scalar("platform"),
        url=_scalar("url"),
    )


def _materialize_derivative_row(
    df_row: pd.Series,
    df_columns: List[str],
    project: Project,
    cde: Graph,
    id_field: str,
    software_metadata: pd.DataFrame,
    nidm_file: str,
) -> bool:
    """Materialize one Derivative + DerivativeObject for *df_row*.

    Returns ``True`` when the row produced output (i.e. the
    task/run/session matched an existing acquisition), ``False`` when
    no source acquisition could be found and we silently skipped.
    """
    from rdflib import Literal as _Lit

    subjectid = str(df_row[id_field]).lstrip("0")
    session_num = str(df_row.get("ses", "nan"))
    if session_num in ("nan", ""):
        session_num = None
    task = str(df_row.get("task", "nan"))
    if task in ("nan", ""):
        task = None
    run = str(df_row.get("run", "nan"))
    if run in ("nan", ""):
        run = None

    derivative_session = find_session_for_subjectid(
        session_num, subjectid, nidm_file
    )
    source_acq_entity, source_activity = match_acquistion_task_run_from_session(
        subject_id=subjectid,
        session_uuid=derivative_session,
        task=task,
        run=run,
        nidm_file=nidm_file,
    )
    if source_acq_entity is None:
        return False

    # Create the derivative + entity.
    der = Derivative(project=project)
    der_entity = DerivativeObject(derivative=der)

    # prov:used link from the derivative activity to the matched
    # source acquisition activity.
    der.graph.add(
        (der.identifier, PROV.used, source_activity)
    )

    # Add row metadata to the derivative entity.
    skipped_columns = {id_field, "ses", "task", "run", "subject_id", "source_url"}
    for column in df_columns:
        if column in skipped_columns:
            continue
        value = df_row[column]
        if pd.isna(value):
            continue
        add_attributes_with_cde(
            obj=der_entity, cde=cde, row_variable=column, value=value
        )

    # source_url -> prov:Location on the derivative entity.
    if "source_url" in df_columns and not pd.isna(df_row["source_url"]):
        der_entity.graph.add(
            (der_entity.identifier, PROV.Location, _Lit(df_row["source_url"]))
        )

    # Look up the existing Person for this subject so we can attach a
    # qualified association.
    subject_index = _query_subject_ids(project)
    person_uri = _find_person_for_csv_row(subjectid, subject_index)
    if person_uri is not None:
        person = Person.from_existing_subject(project.graph, person_uri)
        der.add_qualified_association(person, role=SIO.Subject)

    # Software agent + role.
    software_agent = _create_software_agent_for_derivative(project, software_metadata)
    der.add_qualified_association(
        software_agent,
        role=_C.NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE,
    )
    return True


def csv2nidm_add_derivative_to_existing(
    csv_file: str,
    nidm_file: str,
    derivative_file: str,
    *,
    json_map=None,
    associate_concepts: bool = False,
    dataset_identifier: Optional[str] = None,
    id_field: Optional[str] = None,
) -> Tuple[Project, Graph, int]:
    """Add derivative data to an existing NIDM file.

    Returns ``(project, cde_graph, rows_added)``.  When zero rows
    matched any existing acquisition the caller can skip writing the
    file back (matches legacy ``data_added`` short-circuit).
    """
    df = _read_input_dataframe(csv_file)
    _validate_derivative_input_columns(df)
    software_metadata = _load_software_metadata(derivative_file)

    # Drop the derivative-required columns before running
    # map_variables_to_terms so it doesn't complain about un-annotated
    # ses/task/run/source_url columns.
    df_for_mapping = df.drop(
        columns=list(_DERIVATIVE_INPUT_REQUIRED), errors="ignore"
    )

    out_dir = dirname(nidm_file)
    assessment_name = basename(csv_file)

    # Use the software product URL as the CDE namespace so derivative
    # data elements land in the software's namespace.
    software_title = software_metadata["title"].to_string(index=False).strip()
    software_url = software_metadata["url"].to_string(index=False).strip()
    cde_namespace = {software_title: software_url}

    column_to_terms, cde = map_variables_to_terms(
        df=df_for_mapping,
        assessment_name=assessment_name,
        directory=out_dir,
        output_file=nidm_file,
        json_source=json_map,
        associate_concepts=associate_concepts,
        cde_namespace=cde_namespace,
    )
    del dataset_identifier  # reserved for future hash-id integration

    if id_field is None:
        id_field = detect_idfield(column_to_terms) if column_to_terms else None
    if id_field is None:
        id_field = ask_idfield(df)

    # Re-read the CSV with id_field as string (preserves zero-padded IDs).
    df = (
        pd.read_csv(csv_file, dtype={id_field: str})
        if csv_file.endswith(".csv")
        else pd.read_csv(csv_file, dtype={id_field: str}, sep="\t")
    )
    df_columns = list(df.columns)

    project = read_nidm(nidm_file)
    rows_added = 0
    for _, row in df.iterrows():
        if _materialize_derivative_row(
            df_row=row,
            df_columns=df_columns,
            project=project,
            cde=cde,
            id_field=id_field,
            software_metadata=software_metadata,
            nidm_file=nidm_file,
        ):
            rows_added += 1
    return project, cde, rows_added


# ---------------------------------------------------------------------------
# Programmatic entry point
# ---------------------------------------------------------------------------


def csv2nidm_project(
    csv_file: str,
    *,
    output_file: Optional[str] = None,
    json_map=None,
    associate_concepts: bool = False,
    dataset_identifier: Optional[str] = None,
    id_field: Optional[str] = None,
) -> Tuple[Project, Graph]:
    """Build a NIDM project from a CSV/TSV file.

    Returns ``(project, cde_graph)``.  ``project.graph`` is the
    materialized NIDM-Experiment graph; ``cde_graph`` contains the
    CDE triples produced by :func:`map_variables_to_terms`.

    *associate_concepts=False* (the default for programmatic use)
    skips interactive concept-association prompts.  *id_field* may
    be supplied directly to bypass the auto-detect + interactive
    fallback in :func:`detect_idfield` / :func:`ask_idfield`.
    """
    df = _read_input_dataframe(csv_file)
    out_dir = dirname(output_file) if output_file else dirname(csv_file)
    assessment_name = basename(csv_file)

    column_to_terms, cde = map_variables_to_terms(
        df=df,
        assessment_name=assessment_name,
        directory=out_dir,
        output_file=output_file or os.path.join(out_dir, "nidm.ttl"),
        json_source=json_map,
        associate_concepts=associate_concepts,
    )

    if id_field is None:
        id_field = detect_idfield(column_to_terms) if column_to_terms else None

    project = Project()
    if dataset_identifier is not None:
        from rdflib import Literal as _Lit

        project.graph.add(
            (
                project.identifier,
                _C.NIDM["dataset_identifier"],
                _Lit(dataset_identifier),
            )
        )

    df_columns = list(df.columns)
    for _, row in df.iterrows():
        _materialize_row(
            df_row=row,
            df_columns=df_columns,
            project=project,
            cde=cde,
            id_field=id_field,
            assessment_name=assessment_name,
            csv_file_path=csv_file,
        )

    return project, cde


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description=(
            "Load a CSV / TSV file, optionally map its variables to NIDM/InterLex "
            "concepts via -json_map / -csv_map / -redcap, and write the result as "
            "a NIDM RDF file.  When -nidm is supplied (Phase B), data is appended "
            "to an existing NIDM file instead of creating a new one."
        )
    )
    parser.add_argument(
        "-csv", dest="csv_file", required=True, help="Full path to CSV file to convert"
    )
    dd_group = parser.add_mutually_exclusive_group()
    dd_group.add_argument(
        "-json_map",
        dest="json_map",
        required=False,
        help="Full path to user-supplied JSON file containing variable-term mappings.",
    )
    dd_group.add_argument(
        "-csv_map",
        dest="csv_map",
        required=False,
        help=(
            "Full path to user-supplied CSV-version of data dictionary "
            "with columns: source_variable, label, description, valueType, "
            "measureOf, isAbout, unitCode, minValue, maxValue."
        ),
    )
    dd_group.add_argument(
        "-redcap",
        dest="redcap",
        required=False,
        help="Full path to a user-supplied RedCap formatted data dictionary.",
    )
    parser.add_argument(
        "-nidm",
        dest="nidm_file",
        required=False,
        help="Optional full path of NIDM file to add CSV->NIDM converted graph to.",
    )
    parser.add_argument(
        "-no_concepts",
        action="store_true",
        required=False,
        help="Skip interactive concept association (requires a -json_map / -csv_map "
        "/ -redcap covering all variables).",
    )
    parser.add_argument(
        "-log",
        "--log",
        dest="logfile",
        required=False,
        default=None,
        help="Full path to directory to save log file.",
    )
    parser.add_argument(
        "-dataset_id",
        "--dataset_id",
        dest="dataset_identifier",
        required=False,
        default=None,
        help="Optional dataset identifier (DOI is recommended).  When set, "
        "unique data element IDs include this string in the hash.",
    )
    parser.add_argument(
        "-out",
        dest="output_file",
        required=False,
        help="Full path with filename to save NIDM file.",
    )
    parser.add_argument(
        "-derivative",
        dest="derivative",
        required=False,
        help=(
            "Phase B (not yet active): software-metadata CSV path "
            "describing the tool that produced this derivative."
        ),
    )
    return parser


def csv2nidm_main(argv: Optional[list] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.nidm_file is None and args.output_file is None:
        print(
            "ERROR: You must supply either an existing -nidm file to add metadata to "
            "or the -out output NIDM filename!"
        )
        parser.print_help()
        sys.exit(1)

    if args.logfile is not None:
        logging.basicConfig(
            filename=join(
                args.logfile,
                "csv2nidm_" + os.path.splitext(basename(args.csv_file))[0] + ".log",
            ),
            level=logging.DEBUG,
        )
        _log.info("csv2nidm %s", args)

    json_map = _resolve_json_map(args)

    if args.derivative is not None:
        # Phase C: -derivative + software metadata.  Requires -nidm.
        if args.nidm_file is None:
            print(
                "ERROR: -derivative requires -nidm to identify the existing "
                "NIDM file the derivative data attaches to."
            )
            sys.exit(1)
        project, cde, rows_added = csv2nidm_add_derivative_to_existing(
            csv_file=args.csv_file,
            nidm_file=args.nidm_file,
            derivative_file=args.derivative,
            json_map=json_map,
            associate_concepts=not args.no_concepts,
            dataset_identifier=args.dataset_identifier,
        )
        if rows_added == 0:
            print(
                "No CSV rows matched any acquisition in the NIDM file; "
                "leaving the original file untouched."
            )
            return 0
        _write_existing_nidm_back(project, cde, args.nidm_file)
        return 0

    if args.nidm_file is not None:
        # Phase B path: add to existing NIDM file.
        project, cde, rows_added = csv2nidm_add_to_existing(
            csv_file=args.csv_file,
            nidm_file=args.nidm_file,
            json_map=json_map,
            associate_concepts=not args.no_concepts,
            dataset_identifier=args.dataset_identifier,
        )
        if rows_added == 0:
            print(
                "No CSV rows matched any existing subject in the NIDM file; "
                "leaving the original file untouched."
            )
            return 0
        _write_existing_nidm_back(project, cde, args.nidm_file)
        return 0

    project, cde = csv2nidm_project(
        csv_file=args.csv_file,
        output_file=args.output_file,
        json_map=json_map,
        associate_concepts=not args.no_concepts,
        dataset_identifier=args.dataset_identifier,
    )

    _write_nidm_graph(project=project, cde=cde, output_file=args.output_file)
    return 0


# Legacy alias.
main = csv2nidm_main


if __name__ == "__main__":
    raise SystemExit(csv2nidm_main())
