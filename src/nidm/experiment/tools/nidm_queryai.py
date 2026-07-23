"""Reverse-shim: nidm.experiment.tools.nidm_queryai now lives in nidm.linkml.experiment.tools.nidm_queryai.

Re-exported here so legacy ``nidm.experiment.tools.nidm_queryai`` imports keep working during
the deprecation window (cutover step 4b).
"""
from nidm.linkml.experiment.tools import nidm_queryai as _real  # noqa: E402
from nidm.linkml.experiment.tools.nidm_queryai import *  # noqa: F401,F403

__all__ = [_n for _n in dir(_real) if not _n.startswith("_")]

del _real
