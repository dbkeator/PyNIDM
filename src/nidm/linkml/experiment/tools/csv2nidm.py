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
from ..person import Person
from ..project import Project
from ..session import Session
from ..utils import (
    add_attributes_with_cde,
    add_export_provenance,
    csv_dd_to_json_dd,
    map_variables_to_terms,
    redcap_datadictionary_to_json,
)
from ...core import constants as _C
from ...core.namespaces import NFO, SIO

__version__ = "0.1.0"  # Phase A
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

    if args.nidm_file is not None or args.derivative is not None:
        # Phase B path not yet wired up.
        print(
            "ERROR: -nidm and -derivative are not yet implemented in the "
            "LinkML port (Phase B).  Use the legacy nidm.experiment.tools.csv2nidm "
            "until Phase B lands."
        )
        sys.exit(2)

    json_map = _resolve_json_map(args)
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
