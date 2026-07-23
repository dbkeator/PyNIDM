"""Reverse-shim: nidm.experiment.tools.nidm_file_utils now lives in nidm.linkml.experiment.tools.nidm_file_utils.

Re-exported here so legacy ``nidm.experiment.tools.nidm_file_utils`` imports keep working during
the deprecation window (cutover step 4b).
"""
from nidm.linkml.experiment.tools import nidm_file_utils as _real  # noqa: E402
from nidm.linkml.experiment.tools.nidm_file_utils import *  # noqa: F401,F403

__all__ = [_n for _n in dir(_real) if not _n.startswith("_")]

del _real
