"""
nidm.linkml.experiment.navigate -- transitional shim re-exporting
``nidm.experiment.Navigate``.

Same story as ``query``: the legacy Navigate module is already
rdflib-native (it builds on top of the Query layer), so no code
rewrite is needed.  This shim exposes the same functions under the
new namespace.

Public API
----------
All public names defined in ``nidm.experiment.Navigate`` are
re-exported.  Major entry points:

  * ``getProjects``, ``getSessions``, ``getAcquisitions`` -- walk
    the Project -> Session -> Acquisition hierarchy.
  * ``getSubject``, ``getSubjects``, ``getSubjectUUIDsfromID``,
    ``getSubjectIDfromUUID`` -- participant queries.
  * ``getActivities``, ``getActivityData`` -- inspect acquisition
    activities and their generated entities.
  * ``GetProjectAttributes``, ``GetAllPredicates``,
    ``GetDataelements``, ``GetDataelementDetails`` -- metadata
    introspection.

See the legacy module's docstrings for full signatures and return
types.
"""
from __future__ import annotations
from nidm.experiment import Navigate as _Navigate  # noqa: E402
from nidm.experiment.Navigate import *  # noqa: F401, F403

__all__ = [name for name in dir(_Navigate) if not name.startswith("_")]

del _Navigate
