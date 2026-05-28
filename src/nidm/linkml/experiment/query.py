"""
nidm.linkml.experiment.query -- transitional shim re-exporting the
existing rdflib-native query layer at ``nidm.experiment.Query``.

The legacy query layer is already prov-toolbox-free: it constructs
``rdflib.Graph`` objects directly and runs SPARQL via
``Graph.query()``.  No code rewrite is needed.  This shim makes the
same functions accessible under the new ``nidm.linkml.experiment``
namespace so downstream tools (task 8) port by changing one import
line:

    # before
    from nidm.experiment.Query import sparql_query_nidm

    # after
    from nidm.linkml.experiment.query import sparql_query_nidm

When the cutover lands (task 12), the physical file moves into this
package and the legacy path becomes a reverse-shim re-exporting from
here.

Public API
----------
All public names defined in ``nidm.experiment.Query`` are re-exported.
The full inventory is roughly 40 functions covering:

  * ``sparql_query_nidm`` -- arbitrary SPARQL over a NIDM file list.
  * ``GetProjectsUUID``, ``GetSessionUUID``, ``GetParticipantIDs`` --
    UUID / ID enumeration.
  * ``GetProjectsMetadata``, ``GetParticipantSessionsMetadata`` --
    metadata extraction.
  * ``GetDataElements``, ``GetBrainVolumes``, ``GetBrainThickness``,
    ``GetBrainSurfaceArea`` -- domain-specific extractors.
  * ``GetMergedGraph`` -- merge multiple NIDM files into one
    rdflib.Graph.
  * URI helpers: ``URITail``, ``trimWellKnownURIPrefix``,
    ``expandUUID``, ``expandNIDMAbbreviation``.

See the legacy module's docstrings for full signatures and return
types.
"""
from __future__ import annotations

# Build ``__all__`` from the source module's public names so tools that
# rely on ``from nidm.linkml.experiment.query import *`` see exactly
# the same surface they would from the legacy import.
from nidm.experiment import Query as _Query  # noqa: E402

# Re-export every public name from the legacy module.  We deliberately
# use a star-import so this shim doesn't have to be updated when new
# query helpers land in the source module before the cutover.
from nidm.experiment.Query import *  # noqa: F401, F403

__all__ = [name for name in dir(_Query) if not name.startswith("_")]

del _Query
