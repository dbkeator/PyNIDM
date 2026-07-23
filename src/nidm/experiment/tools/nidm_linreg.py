"""Reverse-shim: nidm.experiment.tools.nidm_linreg now lives in nidm.linkml.experiment.tools.nidm_linreg.

Re-exported here so legacy ``nidm.experiment.tools.nidm_linreg`` imports keep working during
the deprecation window (cutover step 4b).
"""
from nidm.linkml.experiment.tools import nidm_linreg as _real  # noqa: E402
from nidm.linkml.experiment.tools.nidm_linreg import *  # noqa: F401,F403

__all__ = [_n for _n in dir(_real) if not _n.startswith("_")]

del _real
