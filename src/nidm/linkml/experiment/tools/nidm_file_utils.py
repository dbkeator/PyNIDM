"""
nidm.linkml.experiment.tools.nidm_file_utils -- transitional shim
re-exporting the prov-free ``-nl`` file-list resolver at
``nidm.experiment.tools.nidm_file_utils``.

Provides ``expand_nidm_file_list`` (files / directories recursed for
``**/nidm.ttl`` / manifests / globs / URLs) and ``bundled_cde_files``.
The physical file moves here at cutover (task 12).
"""
from __future__ import annotations
from nidm.experiment.tools import nidm_file_utils as _nfu  # noqa: E402
from nidm.experiment.tools.nidm_file_utils import *  # noqa: F401, F403

__all__ = [name for name in dir(_nfu) if not name.startswith("_")]

del _nfu
