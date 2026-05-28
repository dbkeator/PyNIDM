"""
Slim BIDS -> NIDM-Experiment converter.

This is a *minimum-viable* port of the legacy
``nidm.experiment.tools.bidsmri2nidm`` rebuilt on the LinkML wrapper
layer.  It demonstrates that the new wrapper API supports an
end-to-end "real" tool and gives the parity harness something
tool-shaped to compare against once Part B lands.

Scope (slim)
------------
For each BIDS dataset directory, this tool produces a NIDM-Experiment
graph containing:

  * One ``Project`` (title pulled from ``dataset_description.json``).
  * One ``Collection`` typed as ``bids:Dataset`` carrying the BIDS
    version and license.
  * One ``Person`` and one ``Session`` per ``sub-XX/`` directory.
  * For each scan file under ``sub-XX/{anat,func,dwi,asl,pet}/``:
    - One ``MRAcquisition``/``PETAcquisition`` (linked into the Session).
    - One ``MRObject``/``PETObject`` carrying filename, image contrast
      type, and image usage type.
    - A ``prov:qualifiedAssociation`` from the Acquisition to the Person.
  * One ``SoftwareAgent`` and one ``ExportActivity`` recording the
    export-provenance of the tool run.

Deferred (NOT in this slim port)
---------------------------------
  * CDE attachment via ``add_attributes_with_cde``.
  * Interlex term mapping via ``map_variables_to_terms``.
  * Git-annex source tracking via ``addGitAnnexSources``.
  * Sidecar JSON descent (``RepetitionTime``, ``EchoTime``, ``FlipAngle``,
    ``Manufacturer``, ``ManufacturerModelName``, etc.).
  * ``participants.tsv`` variable mapping to NIDM personal data elements.
  * ``--per_subject`` output mode (one file per subject).
  * fMRI events.tsv handling.
  * DWI bval/bvec files.

Those are tracked as follow-up work in the [[pynidm-linkml-refactor]]
memory.  The slim port's purpose is to validate the wrapper API
end-to-end in tool context and let Part B of the parity harness land
once we're ready to compare legacy vs new tool output side-by-side.

CLI
---
::

    python -m nidm.linkml.experiment.tools.bidsmri2nidm \\
        --bids_dir /path/to/bids \\
        --output_file /path/to/out.ttl
"""
from __future__ import annotations
from argparse import ArgumentParser
import datetime
import json
import logging
import os
from pathlib import Path
import re
from typing import Optional, Union
from ..collection import Collection
from ..export_activity import ExportActivity
from ..mr_acquisition import MRAcquisition
from ..mr_object import MRObject
from ..person import Person
from ..pet_acquisition import PETAcquisition
from ..pet_object import PETObject
from ..project import Project
from ..session import Session
from ..software_agent import SoftwareAgent
from ...core.namespaces import BIDS, SIO
from ...generated.nidm_schema_pydantic import (
    ImageContrastTypeEnum,
    ImageUsageTypeEnum,
)

__version__ = "0.1.0"  # slim port version, distinct from legacy

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BIDS suffix / directory -> NIDM enum mapping
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


def _bids_filename(scan_path: Path, bids_root: Path) -> str:
    """Return a ``bids::``-prefixed relative path string."""
    rel = scan_path.resolve().relative_to(bids_root.resolve()).as_posix()
    return f"bids::{rel}"


def _suffix_from_filename(filename: str) -> Optional[str]:
    """Pull the BIDS suffix (e.g. 'T1w') out of a filename, or None."""
    m = _SCAN_FILE_RE.match(filename)
    return m.group("suffix") if m else None


# ---------------------------------------------------------------------------
# Programmatic entry point
# ---------------------------------------------------------------------------


def bidsmri2project(
    bids_dir: Union[str, "os.PathLike[str]"],
    output_path: Optional[Union[str, "os.PathLike[str]"]] = None,
    *,
    project_uuid: Optional[str] = None,
    dataset_uuid: Optional[str] = None,
) -> Project:
    """
    Convert a BIDS dataset directory into a NIDM-Experiment graph.

    Parameters
    ----------
    bids_dir
        Path to the BIDS dataset root.
    output_path
        Optional path to write the resulting turtle file to.  If
        ``None``, the graph is built in-memory only and returned via
        ``Project.graph``.
    project_uuid, dataset_uuid
        Optional pre-generated UUIDs for the Project activity and BIDS
        Dataset collection (for repeatable runs / cross-file
        consistency).

    Returns
    -------
    Project
        The constructed ``nidm.linkml.experiment.Project`` wrapper.
        Use ``project.graph`` to access the underlying rdflib.Graph.
    """
    bids_root = Path(bids_dir).resolve()
    if not bids_root.is_dir():
        raise FileNotFoundError(f"BIDS directory does not exist: {bids_root}")

    # ------------------------------------------------------------------
    # Project + Collection from dataset_description.json
    # ------------------------------------------------------------------
    desc_path = bids_root / "dataset_description.json"
    description: dict = {}
    if desc_path.is_file():
        try:
            description = json.loads(desc_path.read_text())
        except json.JSONDecodeError as exc:
            _log.warning("malformed dataset_description.json (%s); ignoring", exc)

    project = Project(
        uuid=project_uuid,
        title=description.get("Name"),
        license=description.get("License"),
        author=", ".join(description.get("Authors", [])) or None,
        version=description.get("DatasetDOI") or description.get("HEDVersion"),
    )

    Collection(
        project,
        uuid=dataset_uuid,
        extra_types=[BIDS.Dataset],
        bids_version=description.get("BIDSVersion"),
        license=description.get("License"),
    )

    # ------------------------------------------------------------------
    # Per-subject Person + Session, then per-scan Acquisition + Object
    # ------------------------------------------------------------------
    for subject_dir in sorted(bids_root.glob("sub-*")):
        if not subject_dir.is_dir():
            continue
        subject_id = subject_dir.name  # "sub-01"

        person = Person(project, subject_id=subject_id)
        session = Session(project)

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
                    continue  # not a recognized scan file

                if modality == "PET":
                    acq = PETAcquisition(session)
                    # Construction registers the object on the acquisition.
                    PETObject(
                        acq,
                        filename=_bids_filename(scan_path, bids_root),
                    )
                else:  # MR (anat / func / dwi / asl / fmap)
                    acq = MRAcquisition(session)
                    contrast = _SUFFIX_TO_CONTRAST.get(suffix)
                    # Construction registers the object on the acquisition.
                    MRObject(
                        acq,
                        filename=_bids_filename(scan_path, bids_root),
                        image_contrast_type=contrast,
                        image_usage_type=image_usage,
                    )

                # Link the participant to this acquisition.
                acq.add_qualified_association(person, role=SIO.Subject)

    # ------------------------------------------------------------------
    # Export provenance: who made this file, with what tool, when.
    # ------------------------------------------------------------------
    agent = SoftwareAgent(
        project,
        name="PyNIDM",
        software_version=_pynidm_version(),
        command=f"python -m {__name__}",
        runtime_platform=_runtime_platform(),
    )
    ExportActivity(
        project,
        label="Create NIDM RDF from BIDS dataset (slim)",
        output_format="turtle",
        started_at_time=datetime.datetime.now(datetime.timezone.utc),
        was_associated_with=agent,
        used=str(project.identifier),
    )

    if output_path is not None:
        project.write(output_path)

    return project


# ---------------------------------------------------------------------------
# Lightweight helpers
# ---------------------------------------------------------------------------


def _pynidm_version() -> str:
    """Return the installed PyNIDM version, or 'unknown'."""
    try:
        from nidm import __version__ as v  # type: ignore[attr-defined]

        return str(v)
    except Exception:  # pragma: no cover -- defensive
        return "unknown"


def _runtime_platform() -> str:
    """Return e.g. 'Python 3.9.23' for the SoftwareAgent runtime_platform."""
    import platform

    return f"Python {platform.python_version()}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[list] = None) -> int:
    parser = ArgumentParser(
        description=(
            "Slim BIDS -> NIDM-Experiment converter (LinkML wrapper layer).  "
            "See the module docstring for the feature set vs the legacy tool."
        )
    )
    parser.add_argument(
        "--bids_dir", required=True, help="Path to the BIDS dataset root."
    )
    parser.add_argument(
        "--output_file",
        required=True,
        help="Output turtle file path.",
    )
    parser.add_argument("--project_uuid", default=None)
    parser.add_argument("--dataset_uuid", default=None)
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    bidsmri2project(
        bids_dir=args.bids_dir,
        output_path=args.output_file,
        project_uuid=args.project_uuid,
        dataset_uuid=args.dataset_uuid,
    )
    print(f"Wrote NIDM graph to {args.output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["bidsmri2project", "main", "__version__"]
