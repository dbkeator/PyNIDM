"""Reverse-shim: nidm.experiment.Query now lives in nidm.linkml.experiment.query.

Re-exported here so legacy ``nidm.experiment.Query`` imports keep working during
the deprecation window (cutover step 4).
"""
from nidm.linkml.experiment import query as _real  # noqa: E402
from nidm.linkml.experiment.query import *  # noqa: F401,F403

__all__ = [_n for _n in dir(_real) if not _n.startswith("_")]

del _real
