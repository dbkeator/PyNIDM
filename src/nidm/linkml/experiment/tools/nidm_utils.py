"""
nidm.linkml.experiment.tools.nidm_utils -- transitional shim re-exporting the
legacy ``nidm_utils`` console-script entry point (``main``), which provides the
``concat`` / ``visualize`` / ``jsonld`` subcommands.

``concat`` and ``jsonld`` are rdflib-native.  The ``visualize`` subcommand still
routes through ``Project.save_DotGraph`` (prov-based ``prov_to_dot``); the
prov-free renderer lands with ``nidm_visualize`` (task 53), after which this can
become a full native port.  For now the console-script is exposed under the
LinkML namespace via this shim.  The physical file moves here at cutover
(task 12).
"""
from nidm.experiment.tools.nidm_utils import main

__all__ = ["main"]
