"""
nidm.linkml.experiment.tools.nidm_visualize -- transitional shim exposing the
legacy ``visualize`` command under the LinkML ``pynidm`` group.

Unlike the other tool shims, ``visualize`` is NOT yet prov-free: it renders via
``Project.save_DotGraph``, which uses ``prov.dot.prov_to_dot``.  The shim works
while the legacy ``prov`` stack is installed; a prov-free rdflib->graphviz
renderer (task 53) is required before the cutover (task 12) removes ``prov``.
Until then this re-registers the existing command so ``pynidm visualize`` is
available under the LinkML group.
"""
from nidm.experiment.tools.nidm_visualize import visualize
from nidm.linkml.experiment.tools.click_base import cli

# Register the legacy visualize command on the LinkML pynidm group.
cli.add_command(visualize)

__all__ = ["visualize"]
