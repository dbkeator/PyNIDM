"""Reverse-shim: nidm.experiment.Navigate now lives in nidm.linkml.experiment.navigate.

Re-exported here so legacy ``nidm.experiment.Navigate`` imports keep working during
the deprecation window (cutover step 4).
"""
from nidm.linkml.experiment import navigate as _real  # noqa: E402
from nidm.linkml.experiment.navigate import *  # noqa: F401,F403

__all__ = [_n for _n in dir(_real) if not _n.startswith("_")]

del _real
