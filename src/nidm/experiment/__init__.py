"""
NIDM-Experiment Python API (legacy, prov-toolbox based).

The wrapper classes exposed here (``Project``, ``Session``, ``Acquisition``,
...) are the original prov-toolbox implementation and require the optional
``prov`` dependency::

    pip install pynidm[legacy]

They are imported eagerly **when ``prov`` is available**, so that legacy callers
keep working unchanged (the class names must shadow the same-named wrapper
submodules -- ``Acquisition`` the class vs ``Acquisition.py`` the module).  When
``prov`` is NOT installed the import is skipped, which keeps the prov-free
reverse-shim submodules -- ``nidm.experiment.Query`` / ``CDE`` / ``Navigate``
and ``nidm.experiment.tools.rest``, which re-export the relocated
implementations in ``nidm.linkml`` -- importable without pulling ``prov``.
New code should use ``nidm.linkml.experiment`` instead.
"""

# Names of the legacy wrapper classes (each lives in a same-named submodule and
# requires prov).  Used for a helpful error when accessed without the extra.
_WRAPPERS = (
    "Acquisition",
    "AcquisitionObject",
    "AssessmentAcquisition",
    "AssessmentObject",
    "Core",
    "DataElement",
    "DemographicsObject",
    "Derivative",
    "DerivativeObject",
    "MRAcquisition",
    "MRObject",
    "PETAcquisition",
    "PETObject",
    "Project",
    "Session",
)

try:
    # Eager imports bind the CLASS names (shadowing the same-named submodules)
    # exactly as legacy callers expect.  Requires prov.
    from .Acquisition import Acquisition  # noqa: F401
    from .AcquisitionObject import AcquisitionObject  # noqa: F401
    from .AssessmentAcquisition import AssessmentAcquisition  # noqa: F401
    from .AssessmentObject import AssessmentObject  # noqa: F401
    from .Core import Core  # noqa: F401
    from .DataElement import DataElement  # noqa: F401
    from .DemographicsObject import DemographicsObject  # noqa: F401
    from .Derivative import Derivative  # noqa: F401
    from .DerivativeObject import DerivativeObject  # noqa: F401
    from .MRAcquisition import MRAcquisition  # noqa: F401
    from .MRObject import MRObject  # noqa: F401
    from .PETAcquisition import PETAcquisition  # noqa: F401
    from .PETObject import PETObject  # noqa: F401
    from .Project import Project  # noqa: F401
    from .Session import Session  # noqa: F401

    __all__ = list(_WRAPPERS)
    _PROV_AVAILABLE = True
except ImportError:
    # prov (the [legacy] extra) is not installed.  The prov-free reverse-shim
    # submodules still import fine; the wrapper classes raise a helpful error on
    # access via __getattr__ below.
    __all__ = []
    _PROV_AVAILABLE = False


def __getattr__(name):
    """Give a helpful error when a legacy wrapper is accessed without prov."""
    if name in _WRAPPERS and not _PROV_AVAILABLE:
        raise ImportError(
            f"nidm.experiment.{name} is part of the legacy prov-toolbox API; "
            f"install it with `pip install pynidm[legacy]`. New code should use "
            f"nidm.linkml.experiment instead."
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
