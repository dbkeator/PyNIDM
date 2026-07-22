"""
nidm.linkml.experiment.tools.nidm_linreg -- transitional shim exposing the
prov-free legacy ``linear_regression`` command under the LinkML ``pynidm``
group.

``nidm_linreg`` is already rdflib-native: it pulls project/participant data via
the (prov-free) query layer + REST parser and runs the regression with
statsmodels/sklearn.  Its only ``nidm`` dependencies are the query layer, the
REST parser, and a small ``Reporter`` helper -- none use prov-toolbox.  Rather
than duplicate ~740 lines, we re-register the existing command object on the
LinkML cli group.

At cutover (task 12) the implementation file physically moves into this package
and the legacy module becomes a reverse-shim re-exporting from here.
"""
from nidm.experiment.tools.nidm_linreg import linear_regression
from nidm.linkml.experiment.tools.click_base import cli

# Register the legacy linear-regression command on the LinkML pynidm group.
cli.add_command(linear_regression)

__all__ = ["linear_regression"]
