"""Reverse-shim: nidm.experiment.CDE now lives in nidm.linkml.experiment.cde.

Re-exported here so legacy ``nidm.experiment.CDE`` imports keep working during
the deprecation window (cutover step 4).
"""
from nidm.linkml.experiment import cde as _real  # noqa: E402
from nidm.linkml.experiment.cde import *  # noqa: F401,F403

__all__ = [_n for _n in dir(_real) if not _n.startswith("_")]

del _real
