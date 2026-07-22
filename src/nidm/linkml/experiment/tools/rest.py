"""
nidm.linkml.experiment.tools.rest -- transitional shim re-exporting the
prov-free legacy ``RestParser`` at ``nidm.experiment.tools.rest``.

The legacy REST layer constructs ``rdflib.Graph`` objects and runs
SPARQL directly (no prov-toolbox), so no rewrite is needed.  Tools port
by changing one import line; the physical file moves here at cutover
(task 12).
"""
from __future__ import annotations
from nidm.experiment.tools import rest as _rest  # noqa: E402
from nidm.experiment.tools.rest import *  # noqa: F401, F403

__all__ = [name for name in dir(_rest) if not name.startswith("_")]

del _rest
