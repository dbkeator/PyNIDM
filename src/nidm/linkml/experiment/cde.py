"""
nidm.linkml.experiment.cde -- transitional shim re-exporting the
prov-free legacy CDE helpers at ``nidm.experiment.CDE``.

Like :mod:`nidm.linkml.experiment.query`, the legacy CDE layer is
already rdflib-native, so no rewrite is needed.  Tools port by changing
one import line:

    # before
    from nidm.experiment.CDE import getCDEs
    # after
    from nidm.linkml.experiment.cde import getCDEs

At cutover (task 12) the physical file moves into this package and the
legacy path becomes a reverse-shim re-exporting from here.
"""
from __future__ import annotations
from nidm.experiment import CDE as _CDE  # noqa: E402
from nidm.experiment.CDE import *  # noqa: F401, F403

__all__ = [name for name in dir(_CDE) if not name.startswith("_")]

del _CDE
