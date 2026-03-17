from importlib.metadata import version

__version__ = version("pynidm")

try:
    import etelemetry

    etelemetry.check_available_version("incf-nidash/pynidm", __version__)
except ImportError:
    pass

try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:  # pragma: no cover
    from importlib_metadata import (  # for older Python if needed
        PackageNotFoundError,
        version,
    )

try:
    __version__ = version("pynidm")
except PackageNotFoundError:
    __version__ = "0+unknown"
