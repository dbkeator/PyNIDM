"""Reverse-shim: nidm.experiment.tools.rest now lives in nidm.linkml.experiment.tools.rest.

Re-exported here so legacy ``nidm.experiment.tools.rest`` imports keep working during
the deprecation window (cutover step 4).
"""
from nidm.linkml.experiment.tools import rest as _real  # noqa: E402
from nidm.linkml.experiment.tools.rest import *  # noqa: F401,F403

__all__ = [_n for _n in dir(_real) if not _n.startswith("_")]

del _real
