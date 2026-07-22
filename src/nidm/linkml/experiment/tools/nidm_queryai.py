"""
nidm.linkml.experiment.tools.nidm_queryai -- transitional shim exposing the
prov-free legacy ``queryai`` command under the LinkML ``pynidm`` group.

``nidm_queryai`` is already rdflib-native: it loads NIDM graphs with
``rdflib.Graph`` (optionally Oxigraph), builds/executes SPARQL directly, and its
only ``nidm`` imports are the click group and the ``-nl`` file-list resolver --
no prov-toolbox, no rewrite needed.  Rather than duplicate ~1400 lines (and have
to keep two copies in sync on every queryai change), we re-register the existing
command object on the LinkML cli group; a click ``Command`` can belong to more
than one group.

At cutover (task 12) the implementation file physically moves into this package
and the legacy module becomes a reverse-shim re-exporting from here.
"""
from nidm.experiment.tools.nidm_queryai import queryai
from nidm.linkml.experiment.tools.click_base import cli

# Register the legacy queryai command on the LinkML pynidm group.
cli.add_command(queryai)

__all__ = ["queryai"]
